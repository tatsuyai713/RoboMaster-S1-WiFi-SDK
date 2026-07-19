#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import multiprocessing as mp
import queue
import struct
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - optional GUI enhancement
    Image = None
    ImageTk = None

try:
    import av
except ImportError:  # pragma: no cover - optional video decoder
    av = None

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - optional microphone capture
    sd = None

from robomaster_wifi_qr_generator import (
    build_debug_text,
    decode_appid_from_header8,
    make_header8_from_appid,
    make_payload,
    make_qr_image,
    payload_to_qr_text,
    save_qr,
)
from robomaster import robot as sdk_robot_module
from robomaster_s1_sdk.protocol import (
    DEFAULT_CONTROL_HZ,
    DEFAULT_LOCAL_CONTROL_PORT,
    GimbalTelemetry,
    OdometryTelemetry,
    RobotStats as RobotStatsTelemetry,
    normalize_appid,
)



VIDEO_INPUT_BUFFER_CHUNKS = 512
VIDEO_OUTPUT_BUFFER_FRAMES = 64
VIDEO_GUI_BUFFER_FRAMES = 64
EVENT_COMMAND_BUFFER = 64
MIC_SAMPLE_RATE = 48000
VIDEO_RESOLUTION_ACTIONS = {
    "720p/30fps": "video_resolution_0403",
    "1080p/30fps": "video_resolution_0a03",
}
VIDEO_ANTIFLICKER_ACTIONS = {
    "50 Hz": "video_antiflicker_50",
    "60 Hz": "video_antiflicker_60",
}
VIDEO_3D_QUALITY_ACTIONS = {
    "Low": "video_3d_low",
    "Medium": "video_3d_medium",
    "High": "video_3d_high",
}
GUN_TYPE_ACTIONS = {
    "LED": "led",
    "Physical": "physical",
}
VOICE_LANGUAGE_IDS = {
    "English": 0x00,
    "日本語": 0x02,
    "Deutsch": 0x04,
    "Español": 0x05,
    "한국어": 0x06,
    "Français": 0x07,
    "русский": 0x08,
}
CONTROL_SENSITIVITY_PRESETS = {
    "Default": (40, 50),
    "Custom": None,
}
SPEED_PRESET_PAYLOADS = {
    "Slow": "03",
    "Medium": "02",
    "Fast": "01",
    "Custom": "04",
}
CUSTOM_SPEED_PARAMS = (
    ("forward_speed", "Forward Speed (m/s)", "810636fe", 1.50),
    ("backward_speed", "Backward Speed (m/s)", "d9980ced", 1.50),
    ("starting_accel", "Starting Acceleration", "1b175310", 50.0),
    ("braking_accel", "Braking Acceleration", "e96d5133", 50.0),
    ("lateral_speed", "Lateral Speed (m/s)", "6fe6a05e", 1.50),
    ("lateral_starting_accel", "Lateral Starting Acceleration", "0e1a53a0", 50.0),
    ("lateral_braking_accel", "Lateral Braking Acceleration", "dc7051c3", 50.0),
)


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def audio_level_percent(data: bytes) -> int:
    if len(data) < 2:
        return 0
    if len(data) & 1:
        data = data[:-1]
    sample_count = len(data) // 2
    if sample_count == 0:
        return 0
    total = 0
    for (sample,) in struct.iter_unpack("<h", data):
        total += sample * sample
    rms = (total / sample_count) ** 0.5
    return _clamp_int(round((rms / 32768.0) * 100), 0, 100)


@dataclass(frozen=True)
class AppEvent:
    kind: str
    message: str = ""
    packets: int = 0
    duss: int = 0
    video_packets: int = 0
    video_bytes: int = 0
    video_drops: int = 0
    robot_ip: str = ""
    robot_state: str = ""
    robot_mac: str = ""
    robot_appid: str = ""
    raw_hex: str = ""
    decrypted_hex: str = ""
    gimbal: GimbalTelemetry | None = None
    odometry: OdometryTelemetry | None = None
    robot_stats: RobotStatsTelemetry | None = None
    audio_tx_level: int | None = None
    audio_rx_level: int | None = None
    image: object | None = None


class H264Decoder:
    def __init__(self) -> None:
        self.enabled = av is not None and Image is not None
        self.codec = av.CodecContext.create("h264", "r") if self.enabled else None
        self.decode_errors = 0
        self.started = False
        self.pending = bytearray()
        self.consecutive_errors = 0

    def decode(self, data: bytes) -> list[object]:
        if self.codec is None:
            return []
        if not self.started:
            self.pending.extend(data)
            if len(self.pending) > 2_000_000:
                del self.pending[: len(self.pending) - 2_000_000]
            start = self._find_parameter_set_start(self.pending)
            if start is None:
                return []
            data = bytes(self.pending[start:])
            self.pending.clear()
            self.started = True
        frames = []
        try:
            for packet in self.codec.parse(data):
                frames.extend(self.codec.decode(packet))
            self.consecutive_errors = 0
        except Exception:
            self.decode_errors += 1
            self.consecutive_errors += 1
            if self.consecutive_errors >= 30:
                self.codec = av.CodecContext.create("h264", "r") if self.enabled else None
                self.started = False
                self.pending.clear()
                self.consecutive_errors = 0
            return []
        return frames

    @staticmethod
    def _iter_nals(data: bytes):
        pos = 0
        while True:
            candidates = []
            for marker in (b"\x00\x00\x00\x01", b"\x00\x00\x01"):
                index = data.find(marker, pos)
                if index != -1:
                    candidates.append((index, len(marker)))
            if not candidates:
                return
            index, marker_len = min(candidates)
            nal = index + marker_len
            if nal < len(data):
                yield index, data[nal] & 0x1F
            pos = nal + 1

    @classmethod
    def _find_parameter_set_start(cls, data: bytes) -> int | None:
        first_sps = None
        has_pps = False
        for index, nal_type in cls._iter_nals(data):
            if nal_type == 7 and first_sps is None:
                first_sps = index
            elif nal_type == 8 and first_sps is not None:
                has_pps = True
                break
        return first_sps if first_sps is not None and has_pps else None


def h264_decode_process(input_queue, output_queue, stop_event) -> None:
    decoder = H264Decoder()
    while not stop_event.is_set():
        try:
            h264 = input_queue.get(timeout=0.05)
        except queue.Empty:
            continue
        if h264 is None:
            break
        for frame in decoder.decode(h264):
            if Image is None:
                continue
            image = frame.to_image()
            source_size = (image.width, image.height)
            image.thumbnail((760, 430))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=80)
            while not stop_event.is_set():
                try:
                    output_queue.put((buffer.getvalue(), source_size), timeout=0.05)
                    break
                except queue.Full:
                    continue


class SdkS1Worker(threading.Thread):
    """GUI worker that routes robot commands through the SDK facade only."""

    def __init__(
        self,
        events: queue.Queue[AppEvent],
        video_events: queue.Queue[bytes],
        commands: queue.Queue[str],
        motion_commands: queue.Queue[str],
        stop_commands: queue.Queue[str],
        stop_event: threading.Event,
        *,
        appid: str,
        robot_ip: str,
        local_ip: str,
        appid_bind_ip: str,
        local_port: int,
        previous_session: bytes | None,
        debug_enabled: threading.Event,
        save_h264_path: Path,
    ) -> None:
        super().__init__(daemon=True)
        self.events = events
        self.video_events = video_events
        self.commands = commands
        self.motion_commands = motion_commands
        self.stop_commands = stop_commands
        self.stop_event = stop_event
        self.appid = appid
        self.robot_ip = robot_ip
        self.local_ip = local_ip
        self.appid_bind_ip = appid_bind_ip
        self.local_port = local_port
        self.previous_session = previous_session
        self.debug_enabled = debug_enabled
        self.save_h264_path = save_h264_path
        self.finished = threading.Event()
        self.robot = None
        self.video_packets = 0
        self.video_bytes = 0
        self.video_queue_drops = 0
        self.duss_frames = 0
        self.packets = 0
        self.video_input_queue = None
        self.video_output_queue = None
        self.video_stop_event = None
        self.video_process = None
        self.h264_file = None
        self.mic_active = False
        self.audio_rx_queue: queue.Queue[bytes | None] = queue.Queue(
            maxsize=32
        )
        self.audio_rx_stop_event = threading.Event()
        self.audio_rx_thread: threading.Thread | None = None

    def log(self, message: str) -> None:
        if self.debug_enabled.is_set():
            self.events.put(AppEvent("log", message=message))

    def status(self, message: str) -> None:
        self.events.put(AppEvent("status", message=message))

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            if not self.stop_event.is_set():
                self.events.put(AppEvent("error", message=str(exc)))
        finally:
            self.finished.set()

    def _run(self) -> None:
        self._start_video_process()
        self.h264_file = self.save_h264_path.open("wb")
        try:
            self.robot = sdk_robot_module.Robot(
                appid=normalize_appid(self.appid),
                robot_ip=self.robot_ip,
                local_ip=self.local_ip or "0.0.0.0",
                appid_bind_ip=self.appid_bind_ip or "0.0.0.0",
                local_port=self.local_port,
                control_hz=DEFAULT_CONTROL_HZ,
                debug=False,
            )
            self._install_callbacks()
            self.robot.initialize(enter_solo=False)
            if self.robot.info.ip:
                self.events.put(
                    AppEvent(
                        "robot",
                        robot_ip=self.robot.info.ip,
                        robot_state=self.robot.info.state,
                        robot_mac=self.robot.info.mac,
                        robot_appid=self.robot.info.appid,
                    )
                )
            self.events.put(AppEvent("session", message=self.robot.envelope.session.hex()))
            self.status("Control connected; press Solo")
            next_stats = time.monotonic() + 1.0
            while not self.stop_event.is_set():
                self._consume_commands()
                now = time.monotonic()
                if now >= next_stats:
                    self.events.put(
                        AppEvent(
                            "stats",
                            packets=self.packets,
                            duss=self.duss_frames,
                            video_packets=self.video_packets,
                            video_bytes=self.video_bytes,
                            video_drops=self.video_queue_drops,
                        )
                    )
                    next_stats = now + 1.0
                time.sleep(0.002)
        finally:
            self._stop_mic_stream()
            self._stop_audio_rx_playback()
            if self.robot is not None:
                try:
                    self.robot.close()
                except Exception as exc:
                    self.log(f"[sdk] close failed: {exc}")
                self.robot = None
            if self.h264_file is not None:
                self.h264_file.close()
                self.h264_file = None
            self._stop_video_process()
            self.status("Disconnected")

    def _install_callbacks(self) -> None:
        assert self.robot is not None
        self.robot.on("video", self._on_video)
        self.robot.on("duss", self._on_duss)
        self.robot.on("gimbal", lambda value: self.events.put(AppEvent("gimbal", gimbal=value)))
        self.robot.on("odometry", self._on_odometry)
        self.robot.on("stats", lambda value: self.events.put(AppEvent("robot_stats", robot_stats=value)))
        self.robot.on("audio_rx", self._on_audio_rx)
        self.robot.on("armor_damage", self._on_armor_damage)

    def _on_duss(self, _frame) -> None:
        self.duss_frames += 1

    def _on_odometry(self, value) -> None:
        self.events.put(AppEvent("odometry", odometry=value))
        if getattr(value, "battery_percent", None) is not None:
            self.events.put(AppEvent("robot_stats", robot_stats=RobotStatsTelemetry(battery_percent=value.battery_percent)))

    def _on_audio_rx(self, payload: bytes) -> None:
        if self.robot is None:
            return
        pcm = self.robot.camera.decode_audio_opus(payload)
        if not pcm:
            return
        self.events.put(
            AppEvent(
                "audio_level",
                audio_rx_level=audio_level_percent(pcm),
            )
        )
        self._queue_audio_rx_pcm(pcm)

    def _queue_audio_rx_pcm(self, pcm: bytes) -> None:
        if not pcm:
            return
        if self.audio_rx_thread is None or not self.audio_rx_thread.is_alive():
            if sd is None:
                return
            self.audio_rx_stop_event.clear()
            self.audio_rx_thread = threading.Thread(
                target=self._audio_rx_output_loop,
                name="robomaster-s1-sdk-audio-rx",
                daemon=True,
            )
            self.audio_rx_thread.start()
        try:
            self.audio_rx_queue.put_nowait(pcm)
        except queue.Full:
            try:
                self.audio_rx_queue.get_nowait()
                self.audio_rx_queue.put_nowait(pcm)
            except (queue.Empty, queue.Full):
                pass

    def _audio_rx_output_loop(self) -> None:
        assert sd is not None
        try:
            stream = sd.RawOutputStream(
                samplerate=MIC_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=0,
            )
            stream.start()
        except Exception as exc:
            self.events.put(
                AppEvent("error", message=f"Audio RX output failed: {exc}")
            )
            return
        try:
            while (
                not self.stop_event.is_set()
                and not self.audio_rx_stop_event.is_set()
            ):
                try:
                    pcm = self.audio_rx_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if pcm is None:
                    break
                stream.write(pcm)
        finally:
            stream.stop()
            stream.close()

    def _stop_audio_rx_playback(self) -> None:
        self.audio_rx_stop_event.set()
        try:
            self.audio_rx_queue.put_nowait(None)
        except queue.Full:
            try:
                self.audio_rx_queue.get_nowait()
                self.audio_rx_queue.put_nowait(None)
            except (queue.Empty, queue.Full):
                pass
        if self.audio_rx_thread is not None:
            self.audio_rx_thread.join(timeout=1.0)
        self.audio_rx_thread = None

    def _on_armor_damage(self, event) -> None:
        self.events.put(AppEvent("log", message=f"[armor] {event.source} armor={event.armor} payload={event.payload_hex}"))

    def _on_video(self, data: bytes) -> None:
        self.packets += 1
        self.video_packets += 1
        self.video_bytes += len(data)
        if self.h264_file is not None:
            self.h264_file.write(data)
        if self.video_input_queue is None:
            return
        try:
            self.video_input_queue.put_nowait(data)
        except queue.Full:
            self.video_queue_drops += 1

    def _start_video_process(self) -> None:
        if av is None or Image is None:
            return
        self.video_input_queue = mp.Queue(maxsize=VIDEO_INPUT_BUFFER_CHUNKS)
        self.video_output_queue = mp.Queue(maxsize=VIDEO_OUTPUT_BUFFER_FRAMES)
        self.video_stop_event = mp.Event()
        self.video_process = mp.Process(
            target=h264_decode_process,
            args=(self.video_input_queue, self.video_output_queue, self.video_stop_event),
            daemon=True,
        )
        self.video_process.start()
        threading.Thread(target=self._video_event_loop, daemon=True).start()

    def _stop_video_process(self) -> None:
        if self.video_stop_event is not None:
            self.video_stop_event.set()
        if self.video_input_queue is not None:
            try:
                self.video_input_queue.put(None, timeout=0.2)
            except Exception:
                pass
        if self.video_process is not None:
            self.video_process.join(timeout=1.0)
            if self.video_process.is_alive():
                self.video_process.terminate()
                self.video_process.join(timeout=1.0)
        self.video_input_queue = None
        self.video_output_queue = None
        self.video_stop_event = None
        self.video_process = None

    def _video_event_loop(self) -> None:
        while not self.stop_event.is_set():
            if self.video_output_queue is None:
                time.sleep(0.05)
                continue
            try:
                image_bytes = self.video_output_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            while True:
                try:
                    self.video_events.put(image_bytes, timeout=0.05)
                    break
                except queue.Full:
                    if self.stop_event.is_set():
                        return
            while True:
                try:
                    image_bytes = self.video_output_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    self.video_events.put_nowait(image_bytes)
                except queue.Full:
                    self.video_queue_drops += 1

    def _consume_commands(self) -> None:
        assert self.robot is not None
        priority_stop = None
        while True:
            try:
                priority_stop = self.stop_commands.get_nowait()
            except queue.Empty:
                break
        if priority_stop is not None:
            self._execute_command(priority_stop)

        latest_motion = None
        while True:
            try:
                latest_motion = self.motion_commands.get_nowait()
            except queue.Empty:
                break
        if latest_motion is not None:
            self._execute_command(latest_motion)
        for _ in range(8):
            try:
                name = self.commands.get_nowait()
            except queue.Empty:
                return
            self._execute_command(name)

    def _execute_command(self, name: str) -> None:
        assert self.robot is not None
        if name == "enter_solo":
            self.robot.enter_solo()
            self.events.put(AppEvent("solo_state", message="1"))
            return
        if name == "exit_solo":
            self.robot.exit_solo()
            self.events.put(AppEvent("solo_state", message="0"))
            return
        if name.startswith("video_setting:"):
            self.robot.settings.send_named_action(name.split(":", 1)[1])
            return
        if name.startswith("led_color:"):
            _, r_text, g_text, b_text = name.split(":", 3)
            self.robot.led.set_color(int(r_text), int(g_text), int(b_text))
            return
        if name.startswith("gun_type:"):
            self.robot.blaster.set_type(name.split(":", 1)[1])
            return
        if name.startswith("voice_language:"):
            self.robot.settings.set_voice_language_id(int(name.split(":", 1)[1]))
            return
        if name.startswith("volume:"):
            self.robot.settings.set_volume(int(name.split(":", 1)[1]))
            return
        if name == "mic_start":
            self._start_mic_stream()
            return
        if name == "mic_stop":
            self._stop_mic_stream()
            return
        if name == "audio_rx_request":
            self.robot.audio.request_rx()
            return
        if name.startswith("speed:"):
            parts = name.split(":")
            preset = parts[1]
            if preset == "Custom":
                custom_values: dict[str, float] = {}
                if len(parts) > 2 and parts[2]:
                    for item in parts[2].split(","):
                        key, value_text = item.split("=", 1)
                        custom_values[key] = float(value_text)
                self.robot.settings.set_custom_speed(**custom_values)
            else:
                self.robot.settings.set_speed_preset(preset)
            return
        if name.startswith("control_sensitivity:"):
            _, pitch_text, yaw_text = name.split(":", 2)
            self.robot.gimbal.set_control_sensitivity(int(pitch_text), int(yaw_text))
            return
        if name.startswith("trigger_button"):
            self.robot.blaster.fire()
            return
        control_actions = {
            "forward": self.robot.chassis.forward,
            "back": self.robot.chassis.backward,
            "left": self.robot.chassis.left,
            "right": self.robot.chassis.right,
            "stop": self.robot.chassis.stop,
            "gimbal_left": self.robot.gimbal.left,
            "gimbal_right": self.robot.gimbal.right,
            "gimbal_up": self.robot.gimbal.up,
            "gimbal_down": self.robot.gimbal.down,
            "gimbal_stop": self.robot.gimbal.stop,
        }
        action = control_actions.get(name)
        if action is not None:
            action()

    def _start_mic_stream(self) -> None:
        if self.robot is None:
            return
        if self.mic_active:
            return
        self.robot.audio.start_microphone(
            callback=lambda data: self.events.put(
                AppEvent(
                    "audio_level",
                    audio_tx_level=audio_level_percent(data),
                )
            )
        )
        self.mic_active = True

    def _stop_mic_stream(self) -> None:
        if self.mic_active and self.robot is not None:
            try:
                self.robot.audio.stop_microphone()
            except Exception:
                pass
        self.mic_active = False


class UnifiedApp(tk.Tk):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self.title("RoboMaster S1 Unified App")
        self.geometry("1280x900")
        self.minsize(1100, 760)

        self.args = args
        self.events: queue.Queue[AppEvent] = queue.Queue()
        self.video_events: queue.Queue[bytes] = queue.Queue(maxsize=VIDEO_GUI_BUFFER_FRAMES)
        self.commands: queue.Queue[str] = queue.Queue(maxsize=EVENT_COMMAND_BUFFER)
        self.motion_commands: queue.Queue[str] = queue.Queue(maxsize=1)
        self.stop_commands: queue.Queue[str] = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.debug_enabled = threading.Event()
        self.worker: SdkS1Worker | None = None
        self.previous_session: bytes | None = None
        self.current_action_group: str | None = None
        self.last_sent_action = ""
        self.qr_text = ""
        self.qr_photo = None
        self.video_photo = None
        self.audio_rx_clear_job = None
        self.audio_tx_clear_job = None

        self.ssid_var = tk.StringVar(value=args.ssid)
        self.password_var = tk.StringVar(value=args.password)
        self.appid_var = tk.StringVar(value=args.appid)
        self.header8_var = tk.StringVar(value=make_header8_from_appid(args.appid) if args.appid else "")
        self.robot_ip_var = tk.StringVar(value=args.robot_ip)
        self.local_ip_var = tk.StringVar(value=args.local_ip)
        self.status_var = tk.StringVar(value="Ready")
        self.stats_var = tk.StringVar(value="Packets 0  DUSS 0  Video 0 / 0 bytes")
        self.video_resolution_var = tk.StringVar(value="1080p/30fps")
        self.video_antiflicker_var = tk.StringVar(value="60 Hz")
        self.video_3d_quality_var = tk.StringVar(value="Low")
        self.video_size_var = tk.StringVar(value="Stream - / Applied -")
        self.speed_preset_var = tk.StringVar(value="Medium")
        self.control_sensitivity_preset_var = tk.StringVar(value="Default")
        self.control_sensitivity_custom_var = tk.BooleanVar(value=False)
        self.gimbal_pitch_sensitivity_var = tk.StringVar(value="40")
        self.gimbal_yaw_sensitivity_var = tk.StringVar(value="50")
        self.custom_speed_vars = {
            key: tk.StringVar(value=f"{default_value:.2f}" if "speed" in key else f"{default_value:.0f}")
            for key, _label, _param_id, default_value in CUSTOM_SPEED_PARAMS
        }
        self.gun_type_var = tk.StringVar(value="LED")
        self.led_r_var = tk.StringVar(value="255")
        self.led_g_var = tk.StringVar(value="0")
        self.led_b_var = tk.StringVar(value="0")
        self.voice_language_var = tk.StringVar(value="日本語")
        self.volume_var = tk.StringVar(value="10")
        self.audio_tx_level_var = tk.IntVar(value=0)
        self.audio_rx_level_var = tk.IntVar(value=0)
        self.solo_mode_var = tk.BooleanVar(value=False)
        self.debug_var = tk.BooleanVar(value=False)

        self.robot_vars = {key: tk.StringVar(value="-") for key in ("ip", "state", "mac", "appid")}
        self.gimbal_vars = {key: tk.StringVar(value="-") for key in ("raw0", "raw1", "raw2", "raw3", "deg0", "deg1", "deg2", "deg3", "flag")}
        self.odom_vars = {key: tk.StringVar(value="-") for key in ("i0", "i1", "i2", "heading", "f0", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8")}
        self.robot_stat_vars = {key: tk.StringVar(value="-") for key in ("distance_m", "time_min", "time_sec", "battery")}

        self._build_ui()
        self.after(15, self._poll_video)
        self.after(30, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        self._build_top(root).grid(row=0, column=0, columnspan=2, sticky="ew")
        self._build_left(root).grid(row=1, column=0, sticky="nsw", pady=(10, 0), padx=(0, 10))
        self._build_center(root).grid(row=1, column=1, sticky="nsew", pady=(10, 0))

        bottom = ttk.Frame(root)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="ew")
        ttk.Label(bottom, textvariable=self.stats_var, anchor="e").grid(row=0, column=1, sticky="e")

    def _build_top(self, parent: ttk.Frame) -> ttk.Frame:
        top = ttk.LabelFrame(parent, text="Connection", padding=8)
        ttk.Label(top, text="Robot IP").grid(row=0, column=0, padx=(0, 4))
        ttk.Entry(top, textvariable=self.robot_ip_var, width=16).grid(row=0, column=1, padx=(0, 10))
        ttk.Label(top, text="Local IP").grid(row=0, column=2, padx=(0, 4))
        ttk.Entry(top, textvariable=self.local_ip_var, width=16).grid(row=0, column=3, padx=(0, 10))
        ttk.Label(top, text="AppID").grid(row=0, column=4, padx=(0, 4))
        ttk.Entry(top, textvariable=self.appid_var, width=10).grid(row=0, column=5, padx=(0, 10))
        self.connect_button = ttk.Button(top, text="Connect", command=self.connect)
        self.connect_button.grid(row=0, column=6, padx=(0, 4))
        self.disconnect_button = ttk.Button(top, text="Disconnect", command=self.disconnect, state="disabled")
        self.disconnect_button.grid(row=0, column=7, padx=(0, 4))
        self.solo_button = ttk.Checkbutton(top, text="Solo", variable=self.solo_mode_var, command=self.toggle_solo, state="disabled")
        self.solo_button.grid(row=0, column=8, padx=(0, 12))
        ttk.Checkbutton(top, text="Debug log", variable=self.debug_var, command=self._toggle_debug).grid(row=0, column=9, padx=(0, 8))
        return top

    def _build_left(self, parent: ttk.Frame) -> ttk.Frame:
        left = ttk.Frame(parent)
        left.columnconfigure(0, weight=1)
        self._build_qr_panel(left).grid(row=0, column=0, sticky="ew")
        self._build_controller(left).grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self._build_control_sensitivity_panel(left).grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self._build_speed_panel(left).grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self._build_voice_panel(left).grid(row=4, column=0, sticky="ew", pady=(10, 0))
        self._build_robot_panel(left).grid(row=5, column=0, sticky="ew", pady=(10, 0))
        return left

    def _build_qr_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Wi-Fi QR", padding=8)
        panel.columnconfigure(1, weight=1)
        rows = (("SSID", self.ssid_var, False), ("Password", self.password_var, True), ("Header8", self.header8_var, False))
        for row, (label, var, secret) in enumerate(rows):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(panel, textvariable=var, width=28, show="*" if secret else None).grid(row=row, column=1, sticky="ew", pady=2)
        buttons = ttk.Frame(panel)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        buttons.columnconfigure(0, weight=1)
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Generate QR", command=self.generate_qr).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(buttons, text="Save PNG", command=self.save_qr_png).grid(row=0, column=1, sticky="ew", padx=(4, 0))
        return panel

    def _build_controller(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Controller", padding=8)
        panel.columnconfigure(0, weight=1)
        control_grid = ttk.Frame(panel)
        control_grid.grid(row=0, column=0, sticky="ew")
        mapping = [
            ("Forward", "forward", 0, 1),
            ("Left", "back", 1, 0),
            ("Stop", "stop", 1, 1),
            ("Right", "right", 1, 2),
            ("Back", "left", 2, 1),
            ("Gimbal Up", "gimbal_down", 3, 1),
            ("Gimbal Left", "gimbal_left", 4, 0),
            ("Gimbal Stop", "gimbal_stop", 4, 1),
            ("Gimbal Right", "gimbal_right", 4, 2),
            ("Gimbal Down", "gimbal_up", 5, 1),
            ("GUN", "trigger_button", 6, 1),
        ]
        for text, action, row, col in mapping:
            button = ttk.Button(control_grid, text=text)
            button.grid(row=row, column=col, sticky="ew", padx=3, pady=3)
            button.bind("<ButtonPress-1>", lambda _e, name=action: self.press_action(name))
            button.bind("<ButtonRelease-1>", lambda _e, name=action: self.release_action(name))
            button.bind("<Leave>", lambda _e, name=action: self.release_action(name))
        for col in range(3):
            control_grid.columnconfigure(col, weight=1)

        settings = ttk.Frame(panel)
        settings.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Gun").grid(row=0, column=0, sticky="w", padx=(3, 8), pady=3)
        gun_type_frame = ttk.Frame(settings)
        gun_type_frame.grid(row=0, column=1, sticky="w", pady=3)
        for col, label in enumerate(GUN_TYPE_ACTIONS):
            ttk.Radiobutton(
                gun_type_frame,
                text=label,
                value=label,
                variable=self.gun_type_var,
            ).grid(row=0, column=col, sticky="w", padx=(0, 8))
        ttk.Button(settings, text="Apply", command=self.apply_gun_type, width=7).grid(row=0, column=2, sticky="e", padx=(6, 3), pady=3)

        ttk.Label(settings, text="LED").grid(row=1, column=0, sticky="w", padx=(3, 8), pady=3)
        led_frame = ttk.Frame(settings)
        led_frame.grid(row=1, column=1, sticky="w", pady=3)
        for col, (label, var) in enumerate((("R", self.led_r_var), ("G", self.led_g_var), ("B", self.led_b_var))):
            ttk.Label(led_frame, text=label).grid(row=0, column=col * 2, padx=(0, 2))
            ttk.Entry(led_frame, textvariable=var, width=4).grid(row=0, column=col * 2 + 1, padx=(0, 6))
        ttk.Button(settings, text="Apply", command=self.apply_led_color, width=7).grid(row=1, column=2, sticky="e", padx=(6, 3), pady=3)
        return panel

    def _build_control_sensitivity_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Control Sensitivity", padding=8)
        panel.columnconfigure(1, weight=1)

        ttk.Checkbutton(
            panel,
            text="Custom",
            variable=self.control_sensitivity_custom_var,
            command=self._control_sensitivity_preset_changed,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(panel, text="Gimbal Pitch").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(panel, textvariable=self.gimbal_pitch_sensitivity_var, width=6).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(panel, text="Gimbal Yaw").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Entry(panel, textvariable=self.gimbal_yaw_sensitivity_var, width=6).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Button(panel, text="Apply", command=self.apply_control_sensitivity, width=7).grid(row=1, column=2, rowspan=2, sticky="e", padx=(6, 0), pady=2)
        return panel

    def _build_speed_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Speed", padding=8)
        panel.columnconfigure(0, weight=1)

        presets = ttk.Frame(panel)
        presets.grid(row=0, column=0, sticky="ew")
        for col, label in enumerate(SPEED_PRESET_PAYLOADS):
            ttk.Radiobutton(
                presets,
                text=label,
                value=label,
                variable=self.speed_preset_var,
            ).grid(row=0, column=col, sticky="w", padx=(0, 8))
        ttk.Button(presets, text="Apply", command=self.apply_speed_setting, width=7).grid(row=0, column=len(SPEED_PRESET_PAYLOADS), sticky="e")

        custom = ttk.Frame(panel)
        custom.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        custom.columnconfigure(1, weight=1)
        custom.columnconfigure(3, weight=1)
        for index, (key, label, _param_id, _default_value) in enumerate(CUSTOM_SPEED_PARAMS):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(custom, text=label).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=2)
            ttk.Entry(custom, textvariable=self.custom_speed_vars[key], width=7).grid(row=row, column=col + 1, sticky="w", padx=(0, 10), pady=2)
        return panel

    def _build_voice_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Voice", padding=8)
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="Language").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Combobox(
            panel,
            textvariable=self.voice_language_var,
            values=tuple(VOICE_LANGUAGE_IDS),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Button(panel, text="Apply", command=self.apply_voice_language, width=7).grid(row=0, column=2, sticky="e", padx=(6, 0), pady=2)

        ttk.Label(panel, text="Volume").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Spinbox(panel, from_=0, to=80, increment=1, textvariable=self.volume_var, width=6).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Button(panel, text="Apply", command=self.apply_volume, width=7).grid(row=1, column=2, sticky="e", padx=(6, 0), pady=2)

        ttk.Label(panel, text="Mic").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=2)
        mic_button = ttk.Button(panel, text="Hold to Talk")
        mic_button.grid(row=2, column=1, sticky="ew", pady=2)
        mic_button.bind("<ButtonPress-1>", lambda _e: self.press_mic())
        mic_button.bind("<ButtonRelease-1>", lambda _e: self.release_mic())
        mic_button.bind("<Leave>", lambda _e: self.release_mic())
        ttk.Button(panel, text="RX Request", command=self.request_audio_rx, width=10).grid(row=2, column=2, sticky="e", padx=(6, 0), pady=2)

        ttk.Label(panel, text="TX level").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Progressbar(panel, variable=self.audio_tx_level_var, maximum=100).grid(row=3, column=1, columnspan=2, sticky="ew", pady=2)
        ttk.Label(panel, text="RX level").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=2)
        ttk.Progressbar(panel, variable=self.audio_rx_level_var, maximum=100).grid(row=4, column=1, columnspan=2, sticky="ew", pady=2)
        return panel


    def _build_robot_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Robot Broadcast", padding=8)
        panel.columnconfigure(1, weight=1)
        for row, key in enumerate(("ip", "state", "mac", "appid")):
            ttk.Label(panel, text=key).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Label(panel, textvariable=self.robot_vars[key], anchor="w").grid(row=row, column=1, sticky="ew", pady=2)
        return panel

    def _build_center(self, parent: ttk.Frame) -> ttk.Frame:
        center = ttk.Frame(parent)
        center.columnconfigure(0, weight=3)
        center.columnconfigure(1, weight=2)
        center.rowconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)

        video = ttk.LabelFrame(center, text="H.264 Camera", padding=8)
        video.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        video.rowconfigure(0, weight=1)
        video.columnconfigure(0, weight=1)
        self.video_label = ttk.Label(video, text="No video frame decoded", anchor="center")
        self.video_label.grid(row=0, column=0, sticky="nsew")
        video_controls = ttk.Frame(video)
        video_controls.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        video_controls.columnconfigure(1, weight=1)
        self._build_radio_row(video_controls, 0, "Video Resolution", VIDEO_RESOLUTION_ACTIONS, self.video_resolution_var)
        self._build_radio_row(video_controls, 1, "Anti-Flickering", VIDEO_ANTIFLICKER_ACTIONS, self.video_antiflicker_var)
        self._build_radio_row(video_controls, 2, "3D Quality", VIDEO_3D_QUALITY_ACTIONS, self.video_3d_quality_var)
        ttk.Button(video_controls, text="Apply", command=self.apply_video_settings, width=7).grid(row=0, column=2, rowspan=3, sticky="e", padx=(8, 0))
        ttk.Label(video_controls, textvariable=self.video_size_var, anchor="e").grid(row=3, column=0, columnspan=3, sticky="e", pady=(4, 0))

        telemetry = ttk.Frame(center)
        telemetry.grid(row=0, column=1, sticky="nsew")
        telemetry.columnconfigure(0, weight=1)
        self._build_gimbal_panel(telemetry).grid(row=0, column=0, sticky="ew")
        self._build_odom_panel(telemetry).grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._build_robot_stats_panel(telemetry).grid(row=2, column=0, sticky="ew", pady=(8, 0))

        log_panel = ttk.LabelFrame(center, text="Debug Log", padding=8)
        log_panel.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        log_panel.rowconfigure(0, weight=1)
        log_panel.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_panel, height=10, wrap="none")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")
        return center

    def _build_radio_row(self, parent: ttk.Frame, row: int, title: str, choices: dict[str, str], variable: tk.StringVar) -> None:
        ttk.Label(parent, text=title).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=1)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="w", pady=1)
        for col, label in enumerate(choices):
            ttk.Radiobutton(frame, text=label, value=label, variable=variable).grid(row=0, column=col, sticky="w", padx=(0, 8))

    def _build_gimbal_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Gimbal Telemetry", padding=8)
        for row, key in enumerate(("raw0", "raw1", "raw2", "raw3", "deg0", "deg1", "deg2", "deg3", "flag")):
            ttk.Label(panel, text=key).grid(row=row, column=0, sticky="w")
            ttk.Label(panel, textvariable=self.gimbal_vars[key], anchor="e").grid(row=row, column=1, sticky="ew")
        panel.columnconfigure(1, weight=1)
        return panel

    def _build_odom_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Odometry Telemetry", padding=8)
        keys = ("i0", "i1", "i2", "heading", "f0", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8")
        for row, key in enumerate(keys):
            ttk.Label(panel, text=key).grid(row=row, column=0, sticky="w")
            ttk.Label(panel, textvariable=self.odom_vars[key], anchor="e").grid(row=row, column=1, sticky="ew")
        panel.columnconfigure(1, weight=1)
        return panel

    def _build_robot_stats_panel(self, parent: ttk.Frame) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Robot Stats", padding=8)
        labels = (
            ("Driving Distance (m)", "distance_m"),
            ("Driving Time (min)", "time_min"),
            ("Driving Time (sec)", "time_sec"),
            ("Battery (%)", "battery"),
        )
        for row, (label, key) in enumerate(labels):
            ttk.Label(panel, text=label).grid(row=row, column=0, sticky="w")
            ttk.Label(panel, textvariable=self.robot_stat_vars[key], anchor="e").grid(row=row, column=1, sticky="ew")
        panel.columnconfigure(1, weight=1)
        return panel

    def generate_qr(self) -> None:
        try:
            appid = normalize_appid(self.appid_var.get())
            self.header8_var.set(make_header8_from_appid(appid))
            payload = make_payload(self.ssid_var.get(), self.password_var.get(), self.header8_var.get())
            self.qr_text = payload_to_qr_text(payload)
            debug = build_debug_text(self.ssid_var.get(), self.password_var.get(), payload)
            self._append_log("[qr]\n" + debug + f"\npayload={payload.hex()}\nqr={self.qr_text}")
            self._show_qr_window()
            self.status_var.set(f"QR generated AppID={decode_appid_from_header8(self.header8_var.get())}")
        except Exception as exc:
            messagebox.showerror("QR generate failed", str(exc))

    def _show_qr_window(self) -> None:
        window = tk.Toplevel(self)
        window.title("RoboMaster Wi-Fi QR")
        window.resizable(False, False)
        if ImageTk is not None:
            img = make_qr_image(self.qr_text, box_size=10, border=4)
            self.qr_photo = ImageTk.PhotoImage(img)
            window.qr_photo = self.qr_photo
            ttk.Label(window, image=self.qr_photo).grid(row=0, column=0, padx=12, pady=12)
        else:
            ttk.Label(window, text=self.qr_text, wraplength=520, justify="left").grid(row=0, column=0, padx=12, pady=12)

    def save_qr_png(self) -> None:
        if not self.qr_text:
            self.generate_qr()
        if not self.qr_text:
            return
        filename = filedialog.asksaveasfilename(defaultextension=".png", initialfile="robomaster_wifi_qr.png")
        if not filename:
            return
        try:
            save_qr(self.qr_text, Path(filename))
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.status_var.set(f"QR saved: {filename}")

    def connect(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        self.worker = None
        while True:
            try:
                self.commands.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self.motion_commands.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self.stop_commands.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self.video_events.get_nowait()
            except queue.Empty:
                break
        self.last_sent_action = ""
        try:
            appid = normalize_appid(self.appid_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid AppID", str(exc))
            return
        self.stop_event.clear()
        self.worker = SdkS1Worker(
            self.events,
            self.video_events,
            self.commands,
            self.motion_commands,
            self.stop_commands,
            self.stop_event,
            appid=appid,
            robot_ip=self.robot_ip_var.get().strip(),
            local_ip=self.local_ip_var.get().strip() or "0.0.0.0",
            appid_bind_ip=self.args.appid_bind_ip,
            local_port=self.args.local_port,
            previous_session=self.previous_session,
            debug_enabled=self.debug_enabled,
            save_h264_path=Path(self.args.h264_output),
        )
        self.worker.start()
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.solo_mode_var.set(False)
        self.solo_button.configure(state="normal")
        self.status_var.set("Connecting")

    def toggle_solo(self) -> None:
        if self.worker is None:
            self.solo_mode_var.set(False)
            self.status_var.set("Connect before changing Solo")
            return
        if self.solo_mode_var.get():
            self._queue_event_command("enter_solo")
            self.status_var.set("Entering Solo")
        else:
            self._queue_event_command("exit_solo")
            self.status_var.set("Leaving Solo")
        self.solo_button.configure(state="disabled")

    def disconnect(self) -> None:
        if self.worker is None:
            return
        worker = self.worker
        self.stop_event.set()
        worker.join(timeout=2.0)
        if worker.is_alive():
            self.status_var.set("Disconnecting")
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="disabled")
            self.solo_button.configure(state="disabled")
            self.after(100, lambda: self._finish_disconnect(worker))
            return
        self._finish_disconnect(worker)

    def _finish_disconnect(self, worker: SdkS1Worker) -> None:
        if worker.is_alive():
            self.after(100, lambda: self._finish_disconnect(worker))
            return
        if self.worker is worker:
            self.worker = None
        self.last_sent_action = ""
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.solo_mode_var.set(False)
        self.solo_button.configure(state="disabled")
        self.status_var.set("Disconnected")

    def send_action(self, name: str) -> None:
        if self.worker is None:
            return
        if name == self.last_sent_action and not name.startswith("trigger_button"):
            return
        self.last_sent_action = name
        if name.startswith("trigger_button"):
            try:
                self.commands.put_nowait(name)
            except queue.Full:
                self.status_var.set("Command queue busy; trigger was not sent")
            return
        while True:
            try:
                self.motion_commands.put_nowait(name)
                return
            except queue.Full:
                try:
                    self.motion_commands.get_nowait()
                except queue.Empty:
                    return

    def _queue_event_command(self, command: str) -> bool:
        try:
            self.commands.put_nowait(command)
            return True
        except queue.Full:
            self.status_var.set("Command queue busy; command was not sent")
            return False

    def _queue_stop_command(self, command: str) -> None:
        while True:
            try:
                self.stop_commands.put_nowait(command)
                return
            except queue.Full:
                try:
                    self.stop_commands.get_nowait()
                except queue.Empty:
                    return

    def apply_video_settings(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying video settings")
            return
        selections = (
            (VIDEO_RESOLUTION_ACTIONS, self.video_resolution_var.get()),
            (VIDEO_ANTIFLICKER_ACTIONS, self.video_antiflicker_var.get()),
            (VIDEO_3D_QUALITY_ACTIONS, self.video_3d_quality_var.get()),
        )
        actions: list[str] = []
        for mapping, label in selections:
            action = mapping.get(label)
            if action is None:
                self.status_var.set("Unknown video setting")
                return
            actions.append(action)
        for action in actions:
            self._queue_event_command(f"video_setting:{action}")
        current_stream = self.video_size_var.get().split(" / ", 1)[0]
        label = f"{self.video_resolution_var.get()}, {self.video_antiflicker_var.get()}, 3D {self.video_3d_quality_var.get()}"
        self.video_size_var.set(f"{current_stream} / Applied {label}")
        self.status_var.set(f"Sending video settings {label}")

    def apply_led_color(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying LED color")
            return
        try:
            r = _clamp_int(int(self.led_r_var.get(), 0), 0, 255)
            g = _clamp_int(int(self.led_g_var.get(), 0), 0, 255)
            b = _clamp_int(int(self.led_b_var.get(), 0), 0, 255)
        except ValueError:
            messagebox.showerror("Invalid LED RGB", "RGB values must be integers from 0 to 255.")
            return
        self.led_r_var.set(str(r))
        self.led_g_var.set(str(g))
        self.led_b_var.set(str(b))
        self._queue_event_command(f"led_color:{r}:{g}:{b}")
        self.status_var.set(f"Sending LED RGB {r},{g},{b}")

    def apply_gun_type(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying gun type")
            return
        label = self.gun_type_var.get()
        gun_type = GUN_TYPE_ACTIONS.get(label)
        if gun_type is None:
            self.status_var.set("Unknown gun type")
            return
        self._queue_event_command(f"gun_type:{gun_type}")
        self.status_var.set(f"Sending gun type {label}")

    def apply_voice_language(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying voice language")
            return
        label = self.voice_language_var.get()
        language_id = VOICE_LANGUAGE_IDS.get(label)
        if language_id is None:
            self.status_var.set("Unknown voice language")
            return
        self._queue_event_command(f"voice_language:{language_id}")
        self.status_var.set(f"Sending voice language {label}")

    def apply_volume(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying volume")
            return
        try:
            volume = _clamp_int(int(self.volume_var.get(), 0), 0, 80)
        except ValueError:
            messagebox.showerror("Invalid volume", "Volume は 0..80 の整数で入力してください。")
            return
        self.volume_var.set(str(volume))
        self._queue_event_command(f"volume:{volume}")
        self.status_var.set(f"Sending volume {volume}")

    def press_mic(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before using Mic")
            return
        if self.audio_tx_clear_job is not None:
            try:
                self.after_cancel(self.audio_tx_clear_job)
            except tk.TclError:
                pass
            self.audio_tx_clear_job = None
        self._queue_event_command("mic_start")
        self.status_var.set("Mic start")

    def release_mic(self) -> None:
        if self.worker is None:
            return
        self._queue_event_command("mic_stop")
        if self.audio_tx_clear_job is not None:
            try:
                self.after_cancel(self.audio_tx_clear_job)
            except tk.TclError:
                pass
        self.audio_tx_clear_job = self.after(250, lambda: self.audio_tx_level_var.set(0))
        self.status_var.set("Mic stop")

    def request_audio_rx(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before requesting audio RX")
            return
        self._queue_event_command("audio_rx_request")
        self.status_var.set("Requesting audio RX")

    def apply_speed_setting(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying speed")
            return
        preset = self.speed_preset_var.get()
        if preset not in SPEED_PRESET_PAYLOADS:
            self.status_var.set("Unknown speed preset")
            return
        encoded_values: list[str] = []
        for key, label, _param_id, _default_value in CUSTOM_SPEED_PARAMS:
            try:
                value = float(self.custom_speed_vars[key].get())
            except ValueError:
                messagebox.showerror("Invalid speed value", f"{label} must be a number.")
                return
            self.custom_speed_vars[key].set(f"{value:.2f}" if "speed" in key else f"{value:.0f}")
            encoded_values.append(f"{key}={value:.6g}")
        suffix = ",".join(encoded_values) if preset == "Custom" else ""
        self._queue_event_command(f"speed:{preset}:{suffix}")
        self.status_var.set(f"Sending speed {preset}")

    def _control_sensitivity_preset_changed(self) -> None:
        preset_name = "Custom" if self.control_sensitivity_custom_var.get() else "Default"
        self.control_sensitivity_preset_var.set(preset_name)
        preset = CONTROL_SENSITIVITY_PRESETS.get(preset_name)
        if preset is None:
            return
        pitch, yaw = preset
        self.gimbal_pitch_sensitivity_var.set(str(pitch))
        self.gimbal_yaw_sensitivity_var.set(str(yaw))

    def apply_control_sensitivity(self) -> None:
        if self.worker is None:
            self.status_var.set("Connect before applying control sensitivity")
            return
        preset = "Custom" if self.control_sensitivity_custom_var.get() else "Default"
        self.control_sensitivity_preset_var.set(preset)
        if preset not in CONTROL_SENSITIVITY_PRESETS:
            self.status_var.set("Unknown control sensitivity preset")
            return
        default_values = CONTROL_SENSITIVITY_PRESETS[preset]
        if default_values is not None:
            pitch, yaw = default_values
            self.gimbal_pitch_sensitivity_var.set(str(pitch))
            self.gimbal_yaw_sensitivity_var.set(str(yaw))
        else:
            try:
                pitch = _clamp_int(int(self.gimbal_pitch_sensitivity_var.get(), 0), 0, 100)
                yaw = _clamp_int(int(self.gimbal_yaw_sensitivity_var.get(), 0), 0, 100)
            except ValueError:
                messagebox.showerror("Invalid control sensitivity", "Control sensitivity values must be integers from 0 to 100.")
                return
            self.gimbal_pitch_sensitivity_var.set(str(pitch))
            self.gimbal_yaw_sensitivity_var.set(str(yaw))
        self._queue_event_command(f"control_sensitivity:{pitch}:{yaw}")
        self.status_var.set(f"Control sensitivity {preset} pitch={pitch} yaw={yaw}")

    def press_action(self, name: str) -> None:
        group = "gimbal" if name.startswith("gimbal_") else "chassis"
        if name.startswith("trigger_button"):
            group = "trigger"
        if (
            self.current_action_group is not None
            and self.current_action_group != group
        ):
            self._queue_stop_command(
                "gimbal_stop"
                if self.current_action_group == "gimbal"
                else "stop"
            )
        self.current_action_group = group
        self.send_action(name)

    def release_action(self, name: str) -> None:
        group = self.current_action_group
        self.current_action_group = None
        if name.startswith("trigger_button"):
            return
        self.send_action("gimbal_stop" if group == "gimbal" else "stop")

    def _toggle_debug(self) -> None:
        if self.debug_var.get():
            self.debug_enabled.set()
        else:
            self.debug_enabled.clear()

    def _poll_events(self) -> None:
        processed = 0
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            processed += 1
            self._handle_event(event)
        self.after(1 if processed else 30, self._poll_events)

    def _poll_video(self) -> None:
        processed = 0
        while True:
            try:
                frame = self.video_events.get_nowait()
            except queue.Empty:
                break
            self._handle_video_frame(frame)
            processed += 1
        self.after(1 if processed else 15, self._poll_video)

    def _handle_video_frame(self, frame_data) -> None:
        if ImageTk is None or Image is None:
            return
        if isinstance(frame_data, tuple):
            image_bytes, source_size = frame_data
            try:
                width, height = source_size
                applied = "-"
                current = self.video_size_var.get()
                if " / Applied " in current:
                    applied = current.split(" / Applied ", 1)[1]
                self.video_size_var.set(f"Stream {width}x{height} / Applied {applied}")
            except (TypeError, ValueError):
                self.video_size_var.set("Stream - / Applied -")
        else:
            image_bytes = frame_data
        image = Image.open(io.BytesIO(image_bytes))
        max_width = max(1, self.video_label.winfo_width() - 8)
        max_height = max(1, self.video_label.winfo_height() - 8)
        if max_width > 20 and max_height > 20:
            image.thumbnail((max_width, max_height))
        self.video_photo = ImageTk.PhotoImage(image)
        self.video_label.configure(image=self.video_photo, text="")

    def _handle_event(self, event: AppEvent) -> None:
        if event.kind == "error":
            self.disconnect()
            messagebox.showerror("RoboMaster S1", event.message)
            self.status_var.set("Error")
        elif event.kind == "status":
            self.status_var.set(event.message)
        elif event.kind == "log":
            self._append_log(event.message)
        elif event.kind == "solo_state":
            self.solo_mode_var.set(event.message == "1")
            if self.worker is not None:
                self.solo_button.configure(state="normal")
        elif event.kind == "session":
            try:
                self.previous_session = bytes.fromhex(event.message)
            except ValueError:
                pass
        elif event.kind == "stats":
            self.stats_var.set(
                f"Packets {event.packets}  DUSS {event.duss}  "
                f"Video {event.video_packets} / {event.video_bytes} bytes  Drops {event.video_drops}"
            )
            if av is None:
                self.video_label.configure(text=f"H.264 receiving: {event.video_packets} packets / {event.video_bytes} bytes")
        elif event.kind == "robot":
            self.robot_vars["ip"].set(event.robot_ip)
            self.robot_vars["state"].set(event.robot_state)
            self.robot_vars["mac"].set(event.robot_mac)
            self.robot_vars["appid"].set(event.robot_appid)
            if event.robot_ip:
                self.robot_ip_var.set(event.robot_ip)
        elif event.kind == "gimbal" and event.gimbal is not None:
            raws = [event.gimbal.raw0, event.gimbal.raw1, event.gimbal.raw2, event.gimbal.raw3]
            for idx, raw in enumerate(raws):
                self.gimbal_vars[f"raw{idx}"].set(str(raw))
                self.gimbal_vars[f"deg{idx}"].set(f"{raw / 10.0:.1f}")
            self.gimbal_vars["flag"].set(f"0x{event.gimbal.flag:02x}")
        elif event.kind == "odometry" and event.odometry is not None:
            self.odom_vars["i0"].set(str(event.odometry.i0))
            self.odom_vars["i1"].set(str(event.odometry.i1))
            self.odom_vars["i2"].set(str(event.odometry.i2))
            self.odom_vars["heading"].set(f"{event.odometry.heading_like:.6f}")
            for idx, value in enumerate(event.odometry.floats):
                self.odom_vars[f"f{idx}"].set(f"{value:.6f}")
        elif event.kind == "robot_stats" and event.robot_stats is not None:
            stats = event.robot_stats
            if stats.driving_distance_m is not None:
                self.robot_stat_vars["distance_m"].set(str(stats.driving_distance_m))
            if stats.driving_time_sec is not None:
                self.robot_stat_vars["time_sec"].set(str(stats.driving_time_sec))
                self.robot_stat_vars["time_min"].set(f"{stats.driving_time_sec / 60.0:.2f}")
            if stats.battery_percent is not None:
                self.robot_stat_vars["battery"].set(str(stats.battery_percent))
        elif event.kind == "audio_level":
            if event.audio_tx_level is not None:
                self.audio_tx_level_var.set(event.audio_tx_level)
            if event.audio_rx_level is not None:
                self.audio_rx_level_var.set(event.audio_rx_level)
                if self.audio_rx_clear_job is not None:
                    try:
                        self.after_cancel(self.audio_rx_clear_job)
                    except tk.TclError:
                        pass
                self.audio_rx_clear_job = self.after(300, lambda: self.audio_rx_level_var.set(0))

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        self.stop_event.set()
        self.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified RoboMaster S1 Wi-Fi QR / control / telemetry / H.264 app.")
    parser.add_argument("--robot-ip", default="")
    parser.add_argument("--local-ip", default="0.0.0.0")
    parser.add_argument("--appid", default="b6359877")
    parser.add_argument("--ssid", default="WirelessLAN")
    parser.add_argument("--password", default="")
    parser.add_argument("--appid-bind-ip", default="0.0.0.0")
    parser.add_argument("--local-port", type=int, default=DEFAULT_LOCAL_CONTROL_PORT)
    parser.add_argument("--h264-output", default="robomaster_s1_live.h264")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = UnifiedApp(args)
    app.mainloop()
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
