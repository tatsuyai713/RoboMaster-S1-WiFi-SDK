#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import deque
import io
import multiprocessing as mp
import queue
import select
import socket
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

from robomaster_s1_designed_motion import (
    CONTROL_PAYLOADS,
    DUSS_ACTIONS,
    DEFAULT_PAIR_HASH1,
    DEFAULT_PAIR_HASH2,
    GEL_GUN_CONFIG,
    IR_GUN_INIT_COMMANDS,
    IR_GUN_CONFIG,
    LED_GUN_TRIGGER_NEUTRAL_PAYLOAD,
    NEUTRAL_PAYLOAD,
    PRE_GUN_PREROLL_COMMANDS,
    SUCCESS_SOLO_SETUP_SEND_ORDER,
    SUCCESS_SOLO_SETUP_SEQUENCE,
    Dc68Envelope,
    build_control,
    build_duss,
    increment_session,
    make_session,
    make_tick_seed,
    parse_duss_frames,
    parse_robot_broadcast,
)
from robomaster_wifi_qr_generator import (
    build_debug_text,
    decode_appid_from_header8,
    make_header8_from_appid,
    make_payload,
    make_qr_image,
    payload_to_qr_text,
    save_qr,
)

LED_GUN_NEUTRAL_SEQUENCE = (LED_GUN_TRIGGER_NEUTRAL_PAYLOAD,) * 6


def looks_like_stream_fragment(payload: bytes) -> bool:
    if len(payload) < 28:
        return False
    if payload[0] & 0x80 == 0:
        return False
    return payload[2:4] != b"\x00\x00" and payload[20:24] != b"\x55\x00\x00\x00"


APP_PORT = 45678
ROBOT_APP_PORT = 56789
ROBOT_CONTROL_PORT = 10607
DEFAULT_LOCAL_CONTROL_PORT = 10609
DEFAULT_INIT_SEQ = 10072
DEFAULT_CONTROL_HZ = 50.0
CONTROL_AFTER_APPID_DELAY = 0.20
PRECONNECT_TIMEOUT_SECONDS = 5.0
PRECONNECT_INTERVAL_SECONDS = 0.20
VIDEO_INPUT_BUFFER_CHUNKS = 512
VIDEO_OUTPUT_BUFFER_FRAMES = 64
VIDEO_GUI_BUFFER_FRAMES = 64
TX_BUFFER_PACKETS = 64
EVENT_COMMAND_BUFFER = 64
MIC_SAMPLE_RATE = 48000
MIC_CHANNELS = 1
MIC_SAMPLE_WIDTH_BYTES = 2
MIC_BLOCK_FRAMES = 480
MIC_AUDIO_CHUNK_BYTES = MIC_BLOCK_FRAMES * MIC_CHANNELS * MIC_SAMPLE_WIDTH_BYTES
MIC_AUDIO_QUEUE_CHUNKS = 256
RX_AUDIO_SAMPLE_RATE = 48000
RX_AUDIO_CHANNELS = 1
RX_AUDIO_QUEUE_CHUNKS = 512
MIC_START_PAYLOAD = bytes.fromhex("00000001000500d2110000000000000000")
MIC_STOP_PAYLOAD = bytes.fromhex("0200000000000000000000000000000000")
CHASSIS_ACTIONS = {"forward", "back", "left", "right"}
GIMBAL_ACTIONS = {"gimbal_left", "gimbal_right", "gimbal_up", "gimbal_down", "gimbal_stop"}
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


def build_chassis_velocity_payload(linear_x: float, linear_y: float, angular_z: float = 0.0) -> bytes:
    lx = _clamp_int(round(1024 + 256 * linear_x), 0, 2047)
    ly = _clamp_int(round(1024 + 256 * linear_y), 0, 2047)
    yaw = _clamp_int(round(256 * angular_z), -1024, 1023) & 0x0FFF
    data = bytearray(bytes.fromhex("0004200001084000000000000000"))
    data[0] = ly & 0xFF
    data[1] = ((lx << 3) & 0xF8) | ((ly >> 8) & 0x07)
    data[2] = (data[2] & 0xC0) | ((lx >> 5) & 0x3F)
    data[5] = ((yaw << 4) & 0xF0) | 0x08
    data[6] = (yaw >> 4) & 0xFF
    data[8] = 0x02 | ((yaw << 2) & 0xFF)
    data[9] = (yaw >> 6) & 0xFF
    data[10] = 0x04
    data[11] = 0x0C
    data[12] = 0x00
    data[13] = 0x04
    return bytes(data)


def build_gimbal_velocity_payload(pitch: float, yaw: float) -> bytes:
    pitch_raw = _clamp_int(round(-1024 * pitch), -1024, 1023)
    yaw_raw = _clamp_int(round(-1024 * yaw), -1024, 1023)
    return bytes.fromhex("0805") + struct.pack("<hh", pitch_raw, yaw_raw)


@dataclass(frozen=True)
class GimbalTelemetry:
    raw0: int
    raw1: int
    raw2: int
    raw3: int
    flag: int
    payload_hex: str


@dataclass(frozen=True)
class OdometryTelemetry:
    i0: int
    i1: int
    i2: int
    battery_percent: int
    heading_like: float
    floats: tuple[float, ...]
    payload_hex: str


@dataclass(frozen=True)
class RobotStatsTelemetry:
    driving_distance_m: int | None = None
    driving_time_sec: int | None = None
    battery_percent: int | None = None
    payload_hex: str = ""


@dataclass
class TxPacket:
    packet: bytes
    target: tuple[str, int]
    done: threading.Event
    error: BaseException | None = None


def int16_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def float32_le(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def decode_4808(payload: bytes) -> GimbalTelemetry | OdometryTelemetry | None:
    if len(payload) == 11 and payload[:2] == b"\x00\x0a":
        return GimbalTelemetry(
            raw0=int16_le(payload, 2),
            raw1=int16_le(payload, 4),
            raw2=int16_le(payload, 6),
            raw3=int16_le(payload, 8),
            flag=payload[10],
            payload_hex=payload.hex(),
        )
    if len(payload) == 62:
        floats = tuple(float32_le(payload, offset) for offset in range(26, 62, 4))
        return OdometryTelemetry(
            i0=int16_le(payload, 2),
            i1=int16_le(payload, 4),
            i2=int16_le(payload, 6),
            battery_percent=payload[10],
            heading_like=float32_le(payload, 12),
            floats=floats,
            payload_hex=payload.hex(),
        )
    return None


def decode_3f03(payload: bytes) -> RobotStatsTelemetry | None:
    if len(payload) < 12:
        return None
    distance_m = int.from_bytes(payload[4:8], "little", signed=False)
    time_sec = int.from_bytes(payload[8:12], "little", signed=False)
    return RobotStatsTelemetry(
        driving_distance_m=distance_m,
        driving_time_sec=time_sec,
        payload_hex=payload.hex(),
    )


def normalize_appid(value: str) -> str:
    appid = value.strip().lower()
    if len(appid) != 8 or any(ch not in "0123456789abcdef" for ch in appid):
        raise ValueError("AppID は8桁のhex文字で入力してください。例: b6359877")
    return appid


def format_payload_preview(data: bytes, limit: int = 96) -> str:
    suffix = "..." if len(data) > limit else ""
    return f"{data[:limit].hex()}{suffix}"


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


def iter_solo_setup(pair_hash1: str, pair_hash2: str):
    hash1 = pair_hash1.encode("ascii").hex()
    hash2 = pair_hash2.encode("ascii").hex()
    for name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix in SUCCESS_SOLO_SETUP_SEQUENCE:
        yield (
            name,
            kind,
            sender,
            receiver,
            attr,
            cmdset,
            cmdid,
            payload_hex.format(hash1=hash1, hash2=hash2),
            reference_prefix,
        )


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


class S1Worker(threading.Thread):
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

        self.packets = 0
        self.duss_frames = 0
        self.video_packets = 0
        self.video_bytes = 0
        self.video_decode_errors = 0
        self.video_queue_drops = 0
        self.seq = DEFAULT_INIT_SEQ
        self.control_payload = NEUTRAL_PAYLOAD
        self.control_name = "stop"
        self.control_sequence: deque[bytes] = deque(maxlen=128)
        self.gimbal_pitch_sensitivity = 40
        self.gimbal_yaw_sensitivity = 50
        self.last_fire = 0.0
        self.envelope: Dc68Envelope | None = None
        self.envelope_lock = threading.Lock()
        self.connect_setup_done = False
        self.solo_initialized = False
        self.video_input_queue = None
        self.video_output_queue = None
        self.video_stop_event = None
        self.video_process = None
        self.tx_queue: queue.Queue[TxPacket | None] | None = None
        self.tx_thread: threading.Thread | None = None
        self.tx_stop_event = threading.Event()
        self.mic_stream = None
        self.mic_audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=MIC_AUDIO_QUEUE_CHUNKS)
        self.mic_active = False
        self.mic_block_index = 0
        self.audio_rx_decoder = None
        self.audio_rx_resampler = None
        self.audio_rx_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=RX_AUDIO_QUEUE_CHUNKS)
        self.audio_rx_thread: threading.Thread | None = None
        self.audio_rx_stop_event = threading.Event()
        self.audio_rx_unavailable_reported = False
        self.finished = threading.Event()

    def log(self, message: str) -> None:
        if self.debug_enabled.is_set():
            self.events.put(AppEvent("log", message=message))

    def status(self, message: str) -> None:
        self.events.put(AppEvent("status", message=message))

    @staticmethod
    def _is_would_block(exc: OSError) -> bool:
        return isinstance(exc, BlockingIOError) or getattr(exc, "winerror", None) == 10035 or getattr(exc, "errno", None) in (10035, 11)

    def _send_direct(self, sock: socket.socket, packet: bytes, target: tuple[str, int]) -> None:
        deadline = time.monotonic() + 1.0
        while not self.stop_event.is_set():
            try:
                sock.sendto(packet, target)
                return
            except OSError as exc:
                if not self._is_would_block(exc):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError("UDP send timed out while waiting for socket write readiness") from exc
                select.select([], [sock], [], 0.01)

    def _start_tx_thread(self, sock: socket.socket) -> None:
        self.tx_queue = queue.Queue(maxsize=TX_BUFFER_PACKETS)
        self.tx_stop_event.clear()
        self.tx_thread = threading.Thread(target=self._tx_loop, args=(sock,), daemon=True)
        self.tx_thread.start()
        self.log(f"[tx] FIFO sender started buffer={TX_BUFFER_PACKETS}")

    def _stop_tx_thread(self) -> None:
        self.tx_stop_event.set()
        if self.tx_queue is not None:
            while True:
                try:
                    self.tx_queue.put(None, timeout=0.05)
                    break
                except queue.Full:
                    if self.tx_thread is None or not self.tx_thread.is_alive():
                        break
                    continue
        if self.tx_thread is not None:
            self.tx_thread.join(timeout=1.0)
        self.tx_thread = None
        self.tx_queue = None

    def _tx_loop(self, sock: socket.socket) -> None:
        assert self.tx_queue is not None
        while not self.stop_event.is_set() and not self.tx_stop_event.is_set():
            try:
                item = self.tx_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if item is None:
                return
            try:
                self._send_direct(sock, item.packet, item.target)
            except BaseException as exc:
                item.error = exc
            finally:
                item.done.set()

    def _sendto(self, sock: socket.socket, packet: bytes, target: tuple[str, int]) -> None:
        if self.tx_queue is None:
            self._send_direct(sock, packet, target)
            return
        item = TxPacket(packet=packet, target=target, done=threading.Event())
        while not self.stop_event.is_set():
            try:
                self.tx_queue.put(item, timeout=0.05)
                break
            except queue.Full:
                continue
        while not self.stop_event.is_set():
            if item.done.wait(timeout=0.05):
                if item.error is not None:
                    raise item.error
                return

    def run(self) -> None:
        try:
            self._run()
        except Exception as exc:
            if not self.stop_event.is_set():
                self.events.put(AppEvent("error", message=str(exc)))
        finally:
            self.finished.set()

    def _run(self) -> None:
        self.appid = normalize_appid(self.appid)
        if not self._connect_appid():
            return
        time.sleep(CONTROL_AFTER_APPID_DELAY)

        sock = self._open_control_socket()
        session = increment_session(self.previous_session) if self.previous_session is not None else make_session()
        tick_seed = make_tick_seed()
        self.envelope = Dc68Envelope(session=session, tick_seed=tick_seed)
        self.status(
            f"control connected session={session.hex()} tick_seed={struct.pack('<H', tick_seed).hex()}"
        )
        self.log(f"[session] session={session.hex()} tick_seed=0x{tick_seed:04x}")

        target = (self.robot_ip, ROBOT_CONTROL_PORT)
        try:
            self._send_preconnect_until_accepted(sock, target)
            if self.stop_event.is_set():
                return
            self._send_connect_setup(sock, target)
            if self.stop_event.is_set():
                return
            self.status("Control connected; press Solo")
            self._main_loop(sock, target)
        finally:
            self._stop_tx_thread()
            sock.close()
            self.status("Disconnected")

    def _open_control_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
        sock.bind((self.local_ip, self.local_port))
        sock.setblocking(False)
        self._start_tx_thread(sock)
        return sock

    def _connect_appid(self) -> bool:
        appid_bytes = self.appid.encode("ascii")
        selected_robot_ip = self.robot_ip
        saw_broadcast = False
        deadline = time.monotonic() + 20.0
        broadcast_probe_deadline = time.monotonic() + 4.0 if selected_robot_ip else deadline
        last_claim = 0.0

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((self.appid_bind_ip, APP_PORT))
            sock.setblocking(False)
            self.status(f"waiting AppID broadcast for {self.appid}")

            if selected_robot_ip:
                self._sendto(sock, appid_bytes, (selected_robot_ip, ROBOT_APP_PORT))
                last_claim = time.monotonic()
                self.log(f"[appid] initial claim {self.appid} -> {selected_robot_ip}:{ROBOT_APP_PORT}")

            while time.monotonic() < deadline and not self.stop_event.is_set():
                now = time.monotonic()
                if selected_robot_ip and not saw_broadcast and now >= broadcast_probe_deadline:
                    self.robot_ip = selected_robot_ip
                    self.status(f"reconnect using Robot IP {selected_robot_ip}")
                    return True
                if selected_robot_ip and saw_broadcast and now - last_claim >= 1.0:
                    self._sendto(sock, appid_bytes, (selected_robot_ip, ROBOT_APP_PORT))
                    last_claim = now
                    self.log(f"[appid] repeat claim {self.appid} -> {selected_robot_ip}:{ROBOT_APP_PORT}")

                readable, _, _ = select.select([sock], [], [], 0.25)
                for ready in readable:
                    try:
                        data, addr = ready.recvfrom(65535)
                    except OSError as exc:
                        if self._is_would_block(exc):
                            continue
                        raise
                    broadcast = parse_robot_broadcast(data)
                    if broadcast is None:
                        self.log(f"[appid-rx] {addr[0]}:{addr[1]} len={len(data)} hex={data.hex()}")
                        continue
                    saw_broadcast = True
                    selected_robot_ip = self.robot_ip or addr[0]
                    self.robot_ip = selected_robot_ip
                    state = "pairing" if broadcast.is_pairing else "idle"
                    robot_appid = broadcast.appid_text
                    self.events.put(
                        AppEvent(
                            "robot",
                            robot_ip=broadcast.robot_ip,
                            robot_state=state,
                            robot_mac=broadcast.robot_mac,
                            robot_appid=robot_appid,
                            raw_hex=broadcast.raw.hex(),
                            decrypted_hex=broadcast.decrypted.hex(),
                        )
                    )
                    self.log(
                        f"[broadcast] {addr[0]}:{addr[1]} state={state} "
                        f"ip={broadcast.robot_ip} mac={broadcast.robot_mac} appid={robot_appid}"
                    )
                    if broadcast.appid_bytes == appid_bytes:
                        self._sendto(sock, appid_bytes, (addr[0], ROBOT_APP_PORT))
                        self.status(f"AppID matched {self.appid}")
                        self.log(
                            f"[appid] matched ack {self.appid} -> {addr[0]}:{ROBOT_APP_PORT}"
                        )
                        return True
                    if broadcast.appid_bytes == b"\x00" * 8 or broadcast.is_pairing:
                        self._sendto(sock, appid_bytes, (addr[0], ROBOT_APP_PORT))
                        last_claim = time.monotonic()
                        self.log(f"[appid] claim {self.appid} -> {addr[0]}:{ROBOT_APP_PORT}")

            if self.stop_event.is_set():
                return False
            self.events.put(AppEvent("error", message="AppID connect timed out"))
            return False
        finally:
            sock.close()

    def _send_setup_entries(
        self,
        sock: socket.socket,
        target: tuple[str, int],
        *,
        solo_entries: bool,
    ) -> None:
        assert self.envelope is not None
        setup_entries = {
            DEFAULT_INIT_SEQ + index: entry
            for index, entry in enumerate(iter_solo_setup(DEFAULT_PAIR_HASH1, DEFAULT_PAIR_HASH2))
        }
        for seq in SUCCESS_SOLO_SETUP_SEND_ORDER:
            if self.stop_event.is_set():
                return
            name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = setup_entries[seq]
            is_solo_entry = seq >= DEFAULT_INIT_SEQ + 19
            if is_solo_entry != solo_entries:
                continue
            duss_seq = self.seq
            duss = build_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex), duss_seq)
            self.seq = (self.seq + 1) & 0xFFFF
            if kind == "control":
                packet = self.envelope.wrap_control(duss)
            else:
                packet = self.envelope.wrap_direct(duss, bytes.fromhex(reference_prefix)[18:20])
            self._sendto(sock, packet, target)
            self.log(
                f"[tx setup] {name} seq={duss_seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} "
                f"len={len(packet)} hex={format_payload_preview(packet)}"
            )
            self._drain(sock, 6)
            time.sleep((1.0 / DEFAULT_CONTROL_HZ) if kind == "control" else 0.006)

    def _send_connect_setup(self, sock: socket.socket, target: tuple[str, int]) -> None:
        if self.connect_setup_done:
            return
        self._send_setup_entries(sock, target, solo_entries=False)
        if self.stop_event.is_set():
            return
        self.connect_setup_done = True

    def _send_solo_setup(self, sock: socket.socket, target: tuple[str, int]) -> None:
        self._send_setup_entries(sock, target, solo_entries=True)

    def _send_solo_entry_effect(self, sock: socket.socket, target: tuple[str, int]) -> None:
        sequence = (
            ("control", None),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010301")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010401")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010201")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0xB3, "05049012516a00000000")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010401")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010201")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x5B, "01")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG)),
            ("duss", (0x02, 0x09, 0x00, 0x3F, 0x04, "010301")),
            ("duss", (0x02, 0x07, 0x40, 0x07, 0x17, "")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x59, "02")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG)),
            ("duss", (0x02, 0x09, 0x00, 0x3F, 0x04, "010301")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x0A, "0100")),
            ("duss", (0x02, 0x01, 0x40, 0x02, 0x34, "0900006400")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x59, "02")),
            ("duss", (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000")),
            ("duss", (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000")),
        )
        for kind, command in sequence:
            if self.stop_event.is_set():
                return
            if kind == "control":
                self._send_neutral_control(sock, target)
                time.sleep(1.0 / DEFAULT_CONTROL_HZ)
                continue
            assert command is not None
            sender, receiver, attr, cmdset, cmdid, payload_hex = command
            self._send_dynamic_duss(
                sock,
                target,
                sender,
                receiver,
                attr,
                cmdset,
                cmdid,
                bytes.fromhex(payload_hex),
                "solo-effect",
            )
            time.sleep(0.01)

    def _send_solo_exit_sequence(self, sock: socket.socket, target: tuple[str, int]) -> None:
        sequence = (
            ("control", None),
            ("duss", (0x02, 0x01, 0x40, 0x02, 0x34, "0900006400")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x59, "00")),
            ("duss", (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0xB3, "06040000000000000000")),
            ("control", None),
            ("duss", (0x02, 0x09, 0x00, 0x3F, 0x04, "000300")),
            ("duss", (0x02, 0x09, 0x40, 0x3F, 0x77, "010300")),
            ("duss", (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000")),
        )
        for kind, command in sequence:
            if self.stop_event.is_set():
                return
            if kind == "control":
                self._send_neutral_control(sock, target)
                time.sleep(1.0 / DEFAULT_CONTROL_HZ)
                continue
            assert command is not None
            sender, receiver, attr, cmdset, cmdid, payload_hex = command
            self._send_dynamic_duss(
                sock,
                target,
                sender,
                receiver,
                attr,
                cmdset,
                cmdid,
                bytes.fromhex(payload_hex),
                "solo-exit",
            )
            time.sleep(0.01)

    def _send_designed_motion_preroll(self, sock: socket.socket, target: tuple[str, int]) -> None:
        assert self.envelope is not None
        for name in ("pcap_mode_010201", "pcap_mode_010301", "pcap_mode_010401", "pcap_cmd_3f57", "pcap_cmd_3f1f"):
            if self.stop_event.is_set():
                return
            self._send_named_duss(sock, target, name)
            time.sleep(0.05)

        while self.seq < 10204 and not self.stop_event.is_set():
            command = PRE_GUN_PREROLL_COMMANDS.get(self.seq)
            if command is None:
                duss = build_control(NEUTRAL_PAYLOAD, self.seq)
                packet = self.envelope.wrap_control(duss)
                label = "neutral"
            else:
                sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = command
                duss = build_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex), self.seq)
                packet = self.envelope.wrap_direct(duss, bytes.fromhex(reference_prefix)[18:20])
                label = f"cmd=0x{cmdset:02x}/0x{cmdid:02x} payload={payload_hex}"
            self._sendto(sock, packet, target)
            self.log(f"[tx preroll] seq={self.seq} {label} len={len(packet)}")
            self.seq = (self.seq + 1) & 0xFFFF
            self._drain(sock, 3)
            time.sleep(1.0 / DEFAULT_CONTROL_HZ)

        for sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix in IR_GUN_INIT_COMMANDS:
            if self.stop_event.is_set():
                return
            payload = bytes.fromhex(payload_hex)
            duss = build_duss(sender, receiver, attr, cmdset, cmdid, payload, self.seq)
            packet = self.envelope.wrap_direct(duss, bytes.fromhex(reference_prefix)[18:20])
            self._sendto(sock, packet, target)
            self.log(
                f"[tx gun-init] seq={self.seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} "
                f"payload={payload_hex} len={len(packet)}"
            )
            self.seq = (self.seq + 1) & 0xFFFF
            self._drain(sock, 5)
            time.sleep(0.006)

    def _enter_solo_mode(self, sock: socket.socket, target: tuple[str, int]) -> None:
        if self.solo_initialized:
            self.status("Solo already initialized")
            self.events.put(AppEvent("solo_state", message="1"))
            return
        self.status("Entering Solo")
        if not self.connect_setup_done:
            self._send_connect_setup(sock, target)
            if self.stop_event.is_set():
                return
        self.control_payload = NEUTRAL_PAYLOAD
        self.control_name = "stop"
        self.control_sequence.clear()
        self._send_solo_setup(sock, target)
        if self.stop_event.is_set():
            return
        self._send_solo_entry_effect(sock, target)
        if self.stop_event.is_set():
            return
        self.solo_initialized = True
        self.events.put(AppEvent("solo_state", message="1"))
        self.status("Solo/control initialized")

    def _exit_solo_mode(self, sock: socket.socket, target: tuple[str, int]) -> None:
        if not self.solo_initialized:
            self.events.put(AppEvent("solo_state", message="0"))
            self.status("Solo already off")
            return
        self.status("Leaving Solo")
        self.control_payload = NEUTRAL_PAYLOAD
        self.control_name = "stop"
        self.control_sequence.clear()
        self._send_solo_exit_sequence(sock, target)
        if self.stop_event.is_set():
            return
        self.solo_initialized = False
        self.events.put(AppEvent("solo_state", message="0"))
        self.status("Solo off")

    def _send_named_duss(self, sock: socket.socket, target: tuple[str, int], name: str) -> None:
        assert self.envelope is not None
        sender, receiver, attr, cmdset, cmdid, payload_hex = DUSS_ACTIONS[name]
        payload = bytes.fromhex(payload_hex)
        duss = build_duss(sender, receiver, attr, cmdset, cmdid, payload, self.seq)
        packet = self.envelope.wrap_direct(duss, attr)
        self._sendto(sock, packet, target)
        self.log(
            f"[tx prep] {name} seq={self.seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} "
            f"payload={payload_hex} len={len(packet)}"
        )
        self.seq = (self.seq + 1) & 0xFFFF
        self._drain(sock, 5)

    def _send_dynamic_duss(
        self,
        sock: socket.socket,
        target: tuple[str, int],
        sender: int,
        receiver: int,
        attr: int,
        cmdset: int,
        cmdid: int,
        payload: bytes,
        label: str,
    ) -> None:
        assert self.envelope is not None
        duss = build_duss(sender, receiver, attr, cmdset, cmdid, payload, self.seq)
        packet = self.envelope.wrap_direct(duss, attr)
        self._sendto(sock, packet, target)
        self.log(
            f"[tx {label}] seq={self.seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} "
            f"payload={payload.hex()} len={len(packet)}"
        )
        self.seq = (self.seq + 1) & 0xFFFF
        self._drain(sock, 5)

    def _send_led_color(self, sock: socket.socket, target: tuple[str, int], r: int, g: int, b: int) -> None:
        payload = bytes((_clamp_int(r, 0, 255), _clamp_int(g, 0, 255), _clamp_int(b, 0, 255), 0x00))
        self._send_dynamic_duss(sock, target, 0x02, 0x09, 0x40, 0x3F, 0x34, payload, "led")

    def _send_voice_language(self, sock: socket.socket, target: tuple[str, int], language_id: int) -> None:
        payload = bytes((_clamp_int(language_id, 0, 255),))
        self._send_dynamic_duss(sock, target, 0x02, 0x09, 0x40, 0x3F, 0x16, payload, "voice-language")

    def _send_volume(self, sock: socket.socket, target: tuple[str, int], volume: int) -> None:
        payload = bytes((_clamp_int(volume, 0, 80),))
        self._send_dynamic_duss(sock, target, 0x02, 0x09, 0x40, 0x3F, 0x1B, payload, "volume")

    def _send_audio_rx_request(self, sock: socket.socket, target: tuple[str, int]) -> None:
        self._send_dynamic_duss(sock, target, 0x02, 0x01, 0x40, 0x3F, 0x1E, b"\x01", "audio-rx-start")

    def _send_mic_start(self, sock: socket.socket, target: tuple[str, int]) -> None:
        self._send_dynamic_duss(sock, target, 0x02, 0x09, 0x40, 0x3F, 0x5F, MIC_START_PAYLOAD, "mic-start")

    def _send_mic_stop(self, sock: socket.socket, target: tuple[str, int]) -> None:
        self._send_dynamic_duss(sock, target, 0x02, 0x09, 0x40, 0x3F, 0x5F, MIC_STOP_PAYLOAD, "mic-stop")

    def _mic_callback(self, indata, frames: int, time_info, status) -> None:  # noqa: ANN001
        if status:
            self.log(f"[mic] capture status={status}")
        data = bytes(indata)
        if not data:
            return
        self.events.put(AppEvent("audio_level", audio_tx_level=audio_level_percent(data)))
        if len(data) <= MIC_AUDIO_CHUNK_BYTES:
            chunks = (data,)
        else:
            chunks = tuple(data[offset : offset + MIC_AUDIO_CHUNK_BYTES] for offset in range(0, len(data), MIC_AUDIO_CHUNK_BYTES))
        for chunk in chunks:
            try:
                self.mic_audio_queue.put_nowait(chunk)
            except queue.Full:
                try:
                    self.mic_audio_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self.mic_audio_queue.put_nowait(chunk)
                except queue.Full:
                    pass

    def _start_mic_stream(self, sock: socket.socket, target: tuple[str, int]) -> None:
        if self.mic_active:
            return
        if sd is None:
            self.events.put(AppEvent("error", message="PC microphone capture requires: pip install sounddevice"))
            return
        while True:
            try:
                self.mic_audio_queue.get_nowait()
            except queue.Empty:
                break
        self.mic_block_index = 0
        self._send_mic_start(sock, target)
        self.mic_stream = sd.RawInputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
            dtype="int16",
            blocksize=MIC_BLOCK_FRAMES,
            callback=self._mic_callback,
        )
        self.mic_stream.start()
        self.mic_active = True
        self.status("Mic streaming")
        self.log(
            f"[mic] started samplerate={MIC_SAMPLE_RATE} channels={MIC_CHANNELS} "
            f"chunk={MIC_AUDIO_CHUNK_BYTES}"
        )

    def _stop_mic_stream(self, sock: socket.socket | None = None, target: tuple[str, int] | None = None) -> None:
        if self.mic_stream is not None:
            try:
                self.mic_stream.stop()
                self.mic_stream.close()
            except Exception as exc:
                self.log(f"[mic] close error: {exc}")
            self.mic_stream = None
        was_active = self.mic_active
        self.mic_active = False
        if was_active and sock is not None and target is not None and not self.stop_event.is_set():
            self._send_mic_stop(sock, target)
            self.status("Mic stopped")
            self.log("[mic] stopped")

    def _ensure_audio_rx_decoder(self) -> bool:
        if self.audio_rx_decoder is not None and self.audio_rx_resampler is not None:
            return True
        if av is None:
            if not self.audio_rx_unavailable_reported:
                self.events.put(AppEvent("error", message="Audio RX playback requires: pip install av"))
                self.audio_rx_unavailable_reported = True
            return False
        try:
            decoder = av.CodecContext.create("opus", "r")
            decoder.sample_rate = RX_AUDIO_SAMPLE_RATE
            decoder.layout = "mono"
            self.audio_rx_decoder = decoder
            self.audio_rx_resampler = av.AudioResampler(format="s16", layout="mono", rate=RX_AUDIO_SAMPLE_RATE)
            return True
        except Exception as exc:
            if not self.audio_rx_unavailable_reported:
                self.events.put(AppEvent("error", message=f"Audio RX decoder init failed: {exc}"))
                self.audio_rx_unavailable_reported = True
            return False

    def _start_audio_rx_playback(self) -> None:
        if self.audio_rx_thread is not None and self.audio_rx_thread.is_alive():
            return
        if sd is None:
            if not self.audio_rx_unavailable_reported:
                self.events.put(AppEvent("error", message="Audio RX playback requires: pip install sounddevice"))
                self.audio_rx_unavailable_reported = True
            return
        self.audio_rx_stop_event.clear()
        self.audio_rx_thread = threading.Thread(target=self._audio_rx_output_loop, daemon=True)
        self.audio_rx_thread.start()

    def _stop_audio_rx_playback(self) -> None:
        self.audio_rx_stop_event.set()
        try:
            self.audio_rx_queue.put_nowait(None)
        except queue.Full:
            pass
        if self.audio_rx_thread is not None:
            self.audio_rx_thread.join(timeout=1.0)
        self.audio_rx_thread = None
        while True:
            try:
                self.audio_rx_queue.get_nowait()
            except queue.Empty:
                break

    def _audio_rx_output_loop(self) -> None:
        try:
            stream = sd.RawOutputStream(
                samplerate=RX_AUDIO_SAMPLE_RATE,
                channels=RX_AUDIO_CHANNELS,
                dtype="int16",
                blocksize=0,
            )
            stream.start()
        except Exception as exc:
            self.events.put(AppEvent("error", message=f"Audio RX output failed: {exc}"))
            return
        try:
            while not self.stop_event.is_set() and not self.audio_rx_stop_event.is_set():
                try:
                    pcm = self.audio_rx_queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                if pcm is None:
                    break
                if pcm:
                    stream.write(pcm)
        finally:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def _decode_audio_rx_payload(self, payload: bytes) -> bytes:
        if not self._ensure_audio_rx_decoder():
            return b""
        assert self.audio_rx_decoder is not None
        assert self.audio_rx_resampler is not None
        try:
            frames = self.audio_rx_decoder.decode(av.Packet(payload))
        except Exception as exc:
            self.log(f"[audio-rx] opus decode failed: {exc}")
            return b""
        chunks: list[bytes] = []
        for frame in frames:
            try:
                out_frames = self.audio_rx_resampler.resample(frame)
            except Exception as exc:
                self.log(f"[audio-rx] resample failed: {exc}")
                continue
            for out in out_frames:
                byte_count = out.samples * RX_AUDIO_CHANNELS * MIC_SAMPLE_WIDTH_BYTES
                chunks.append(bytes(out.planes[0])[:byte_count])
        return b"".join(chunks)

    def _queue_audio_rx_pcm(self, pcm: bytes) -> None:
        if not pcm:
            return
        self._start_audio_rx_playback()
        try:
            self.audio_rx_queue.put_nowait(pcm)
        except queue.Full:
            try:
                self.audio_rx_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.audio_rx_queue.put_nowait(pcm)
            except queue.Full:
                pass

    def _send_mic_audio_block(self, sock: socket.socket, target: tuple[str, int], audio: bytes) -> None:
        assert self.envelope is not None
        if not audio:
            return
        payload = (
            struct.pack("<I", self.mic_block_index & 0xFFFFFFFF)
            + b"\x00"
            + struct.pack("<H", len(audio))
            + audio
        )
        duss = build_duss(0x02, 0x09, 0x00, 0x00, 0x09, payload, self.seq)
        seq_start = self.seq
        self.seq = (self.seq + 1) & 0xFFFF
        self.mic_block_index = (self.mic_block_index + 1) & 0xFFFFFFFF
        with self.envelope_lock:
            packet = self.envelope.wrap_direct(duss, 0x00)
        self._sendto(sock, packet, target)
        self.log(
            f"[tx mic-audio] seq={seq_start} block={self.mic_block_index - 1} "
            f"audio_len={len(audio)} udp_len={len(packet)}"
        )

    def _consume_mic_audio(self, sock: socket.socket, target: tuple[str, int]) -> None:
        if not self.mic_active:
            return
        for _ in range(8):
            try:
                audio = self.mic_audio_queue.get_nowait()
            except queue.Empty:
                return
            self._send_mic_audio_block(sock, target, audio)

    def _send_gun_type(self, sock: socket.socket, target: tuple[str, int], gun_type: str) -> None:
        if gun_type == "physical":
            sequence = (
                (0x02, 0x09, 0x40, 0x3F, 0x5B, "01"),
                (0x02, 0x09, 0x40, 0x3F, 0x09, GEL_GUN_CONFIG),
                (0x02, 0x09, 0x40, 0x3F, 0x59, "02"),
                (0x02, 0x09, 0x40, 0x3F, 0x09, GEL_GUN_CONFIG),
                (0x02, 0x09, 0x40, 0x3F, 0x59, "02"),
            )
        else:
            sequence = (
                (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG),
                (0x02, 0x09, 0x40, 0x3F, 0x59, "02"),
            )
        for sender, receiver, attr, cmdset, cmdid, payload_hex in sequence:
            if self.stop_event.is_set():
                return
            self._send_dynamic_duss(
                sock,
                target,
                sender,
                receiver,
                attr,
                cmdset,
                cmdid,
                bytes.fromhex(payload_hex),
                f"gun-type:{gun_type}",
            )
            time.sleep(0.006)

    def _send_speed_setting(self, sock: socket.socket, target: tuple[str, int], preset: str, custom_values: dict[str, float]) -> None:
        payload_hex = SPEED_PRESET_PAYLOADS[preset]
        self._send_dynamic_duss(
            sock,
            target,
            0x02,
            0x09,
            0x40,
            0x3F,
            0x3F,
            bytes.fromhex(payload_hex),
            f"speed:{preset.lower()}",
        )
        if preset != "Custom":
            return
        for key, _label, param_id, default_value in CUSTOM_SPEED_PARAMS:
            if self.stop_event.is_set():
                return
            value = custom_values.get(key, default_value)
            payload = bytes.fromhex(param_id) + struct.pack("<f", float(value))
            self._send_dynamic_duss(
                sock,
                target,
                0x02,
                0x09,
                0x40,
                0x03,
                0xF9,
                payload,
                f"speed-custom:{key}",
            )
            time.sleep(0.006)

    def _send_preconnect_until_accepted(self, sock: socket.socket, target: tuple[str, int]) -> None:
        assert self.envelope is not None
        deadline = time.monotonic() + PRECONNECT_TIMEOUT_SECONDS
        last_send = 0.0
        seen_sessions: set[bytes] = set()
        last_other_session: bytes | None = None

        while time.monotonic() < deadline and not self.stop_event.is_set():
            now = time.monotonic()
            if now - last_send >= PRECONNECT_INTERVAL_SECONDS:
                preconnect = self.envelope.build_preconnect()
                self._sendto(sock, preconnect, target)
                self.log(f"[tx setup] preconnect len={len(preconnect)} hex={preconnect.hex()}")
                last_send = now

            readable, _, _ = select.select([sock], [], [], 0.03)
            for ready in readable:
                try:
                    data, _ = ready.recvfrom(65535)
                except OSError as exc:
                    if self._is_would_block(exc):
                        continue
                    raise
                packet_session = data[2:4] if len(data) >= 4 else None
                if packet_session == self.envelope.session:
                    is_preconnect_ack = len(data) >= 8 and data[0] == 0x09 and data[1] == 0x80
                    self.log(
                        f"[session] accepted {self.envelope.session.hex()} "
                        f"via {'preconnect-ack' if is_preconnect_ack else 'rx'} len={len(data)}"
                    )
                    self.events.put(AppEvent("session", message=self.envelope.session.hex()))
                    self._handle_rx(data, None)
                    return
                if packet_session is None:
                    continue
                last_other_session = packet_session
                if packet_session not in seen_sessions:
                    seen_sessions.add(packet_session)
                    self.log(
                        f"[rx preconnect-wait] session={packet_session.hex()} "
                        f"expected={self.envelope.session.hex()} len={len(data)}"
                    )
                candidate = increment_session(packet_session)
                if candidate != self.envelope.session:
                    self.log(
                        f"[session] adjust from inbound {packet_session.hex()} "
                        f"to {candidate.hex()}"
                    )
                    self.envelope.session = candidate
                    self.events.put(AppEvent("session", message=self.envelope.session.hex()))
                    last_send = 0.0
                    seen_sessions.clear()
                    break

        if self.stop_event.is_set():
            return
        detail = f"; last inbound session={last_other_session.hex()}" if last_other_session else ""
        self.log(f"[session] preconnect ACK timeout for {self.envelope.session.hex()}{detail}; continuing")
        self.events.put(AppEvent("session", message=self.envelope.session.hex()))

    def _main_loop(self, sock: socket.socket, target: tuple[str, int]) -> None:
        next_control = time.monotonic()
        next_stats = time.monotonic() + 1.0
        rx_stop = threading.Event()
        self._start_video_process()
        rx_thread = threading.Thread(target=self._rx_loop, args=(sock, rx_stop), daemon=True)
        video_event_thread = threading.Thread(target=self._video_event_loop, args=(rx_stop,), daemon=True)
        rx_thread.start()
        video_event_thread.start()
        try:
            while not self.stop_event.is_set():
                self._consume_commands(sock, target)
                self._consume_mic_audio(sock, target)
                now = time.monotonic()
                if now >= next_control and (self.solo_initialized or self.connect_setup_done):
                    if self.solo_initialized:
                        self._send_control(sock, target, self.control_payload)
                    else:
                        self._send_neutral_control(sock, target)
                    control_period = 1.0 / DEFAULT_CONTROL_HZ
                    next_control += control_period
                    if next_control <= now:
                        next_control += (
                            int((now - next_control) / control_period) + 1
                        ) * control_period

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
                    next_stats += 1.0
                    if next_stats <= now:
                        next_stats += int(now - next_stats) + 1
                time.sleep(0.002)
        finally:
            self._stop_mic_stream(sock, target)
            self._stop_audio_rx_playback()
            rx_stop.set()
            rx_thread.join(timeout=1.0)
            video_event_thread.join(timeout=1.0)
            self._stop_video_process()

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
        self.log(f"[video] decoder process pid={self.video_process.pid}")

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
        for attr in ("video_input_queue", "video_output_queue"):
            q = getattr(self, attr)
            if q is not None:
                try:
                    q.close()
                except Exception:
                    pass
        self.video_input_queue = None
        self.video_output_queue = None
        self.video_stop_event = None
        self.video_process = None

    def _rx_loop(self, sock: socket.socket, rx_stop: threading.Event) -> None:
        h264_file = self.save_h264_path.open("wb")
        try:
            while not self.stop_event.is_set() and not rx_stop.is_set():
                readable, _, _ = select.select([sock], [], [], 0.02)
                if not readable:
                    continue
                while not self.stop_event.is_set() and not rx_stop.is_set():
                    try:
                        data, _ = sock.recvfrom(65535)
                    except OSError as exc:
                        if not self._is_would_block(exc):
                            raise
                        break
                    self._handle_rx(data, h264_file)
        finally:
            h264_file.close()

    def _video_event_loop(self, rx_stop: threading.Event) -> None:
        while not self.stop_event.is_set() and not rx_stop.is_set():
            if self.video_output_queue is None:
                time.sleep(0.1)
                continue
            try:
                image_bytes = self.video_output_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            while True:
                while not self.stop_event.is_set() and not rx_stop.is_set():
                    try:
                        self.video_events.put(image_bytes, timeout=0.05)
                        break
                    except queue.Full:
                        continue
                try:
                    image_bytes = self.video_output_queue.get_nowait()
                except queue.Empty:
                    break

    def _consume_commands(self, sock: socket.socket, target: tuple[str, int]) -> None:
        priority_stop = None
        while True:
            try:
                priority_stop = self.stop_commands.get_nowait()
            except queue.Empty:
                break
        if priority_stop is not None:
            self.control_payload = CONTROL_PAYLOADS.get(
                priority_stop, NEUTRAL_PAYLOAD
            )
            self.control_name = priority_stop

        latest_motion = None
        while True:
            try:
                latest_motion = self.motion_commands.get_nowait()
            except queue.Empty:
                break
        if latest_motion is not None:
            self.control_payload = CONTROL_PAYLOADS.get(
                latest_motion, NEUTRAL_PAYLOAD
            )
            self.control_name = latest_motion
            self.log(
                f"[control] selected={latest_motion} "
                f"payload={self.control_payload.hex()}"
            )

        for _ in range(8):
            try:
                name = self.commands.get_nowait()
            except queue.Empty:
                return
            if name == "enter_solo":
                self._enter_solo_mode(sock, target)
                continue
            if name == "exit_solo":
                self._exit_solo_mode(sock, target)
                continue
            if name.startswith("video_setting:"):
                action = name.split(":", 1)[1]
                self._send_named_duss(sock, target, action)
                self.log(f"[video] setting action sent {action}")
                continue
            if name.startswith("led_color:"):
                _, r_text, g_text, b_text = name.split(":", 3)
                self._send_led_color(sock, target, int(r_text), int(g_text), int(b_text))
                continue
            if name.startswith("gun_type:"):
                gun_type = name.split(":", 1)[1]
                self._send_gun_type(sock, target, gun_type)
                self.log(f"[gun] type selected {gun_type}")
                continue
            if name.startswith("voice_language:"):
                language_id = int(name.split(":", 1)[1])
                self._send_voice_language(sock, target, language_id)
                self.log(f"[voice] language id={language_id}")
                continue
            if name.startswith("volume:"):
                volume = int(name.split(":", 1)[1])
                self._send_volume(sock, target, volume)
                self.log(f"[voice] volume={volume}")
                continue
            if name == "mic_start":
                self._start_mic_stream(sock, target)
                continue
            if name == "mic_stop":
                self._stop_mic_stream(sock, target)
                continue
            if name == "audio_rx_request":
                self._send_audio_rx_request(sock, target)
                self.log("[audio-rx] request sent")
                continue
            if name.startswith("speed:"):
                parts = name.split(":")
                preset = parts[1]
                custom_values: dict[str, float] = {}
                if len(parts) > 2 and parts[2]:
                    for item in parts[2].split(","):
                        key, value_text = item.split("=", 1)
                        custom_values[key] = float(value_text)
                self._send_speed_setting(sock, target, preset, custom_values)
                self.log(f"[speed] preset={preset} custom={custom_values}")
                continue
            if name.startswith("control_sensitivity:"):
                _, pitch_text, yaw_text = name.split(":", 2)
                pitch_sensitivity = _clamp_int(int(pitch_text), 0, 100)
                yaw_sensitivity = _clamp_int(int(yaw_text), 0, 100)
                self.gimbal_pitch_sensitivity = pitch_sensitivity
                self.gimbal_yaw_sensitivity = yaw_sensitivity
                self.log(f"[control-sensitivity] local pitch={pitch_sensitivity} yaw={yaw_sensitivity}")
                continue
            if name.startswith("trigger_button"):
                now = time.monotonic()
                self.control_sequence.extend(LED_GUN_NEUTRAL_SEQUENCE)
                self.last_fire = now
                self.log(f"[control] LED GUN neutral sequence queued commands={len(LED_GUN_NEUTRAL_SEQUENCE)}")
                continue
            self.control_payload = CONTROL_PAYLOADS.get(name, NEUTRAL_PAYLOAD)
            self.control_name = name
            self.log(f"[control] selected={name} payload={self.control_payload.hex()}")

    def _send_control(self, sock: socket.socket, target: tuple[str, int], payload: bytes) -> None:
        assert self.envelope is not None
        if self.control_sequence:
            payload = self.control_sequence.popleft()
            duss = build_control(payload, self.seq)
            seq_start = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            with self.envelope_lock:
                packet = self.envelope.wrap_control(duss)
            self._sendto(sock, packet, target)
            self.log(f"[tx control] seq={seq_start} payload={payload.hex()} udp={format_payload_preview(packet, 64)}")
            return
        if self.control_name in CHASSIS_ACTIONS:
            payload = CONTROL_PAYLOADS[self.control_name]
            duss = build_control(payload, self.seq)
            seq_start = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            with self.envelope_lock:
                packet = self.envelope.wrap_control(duss)
            self._sendto(sock, packet, target)
            self.log(f"[tx chassis-control] {self.control_name} seq={seq_start} payload={payload.hex()} udp={format_payload_preview(packet, 64)}")
            return
        if self.control_name in GIMBAL_ACTIONS:
            pitch_gain = max(0.0, self.gimbal_pitch_sensitivity / 50.0)
            yaw_gain = max(0.0, self.gimbal_yaw_sensitivity / 50.0)
            vectors = {
                "gimbal_left": (0.0, 0.6 * yaw_gain),
                "gimbal_right": (0.0, -0.6 * yaw_gain),
                "gimbal_up": (0.6 * pitch_gain, 0.0),
                "gimbal_down": (-0.6 * pitch_gain, 0.0),
                "gimbal_stop": (0.0, 0.0),
            }
            pitch, yaw = vectors[self.control_name]
            duss_payload = build_gimbal_velocity_payload(pitch, yaw)
            duss = build_duss(0x02, 0x04, 0x00, 0x04, 0x69, duss_payload, self.seq)
            seq_start = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            with self.envelope_lock:
                packet = self.envelope.wrap_direct(duss, 0x00)
            self._sendto(sock, packet, target)
            self.log(f"[tx gimbal] {self.control_name} seq={seq_start} payload={duss_payload.hex()} udp={format_payload_preview(packet, 64)}")
            return
        if self.control_name == "stop":
            chassis_payload = NEUTRAL_PAYLOAD
            duss = build_control(chassis_payload, self.seq)
            chassis_seq = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            with self.envelope_lock:
                packet = self.envelope.wrap_control(duss)
            self._sendto(sock, packet, target)
            self.log(f"[tx chassis-control] stop seq={chassis_seq} payload={chassis_payload.hex()} udp={format_payload_preview(packet, 64)}")

            gimbal_payload = build_gimbal_velocity_payload(0.0, 0.0)
            duss = build_duss(0x02, 0x04, 0x00, 0x04, 0x69, gimbal_payload, self.seq)
            gimbal_seq = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            with self.envelope_lock:
                packet = self.envelope.wrap_direct(duss, 0x00)
            self._sendto(sock, packet, target)
            self.log(f"[tx gimbal] stop seq={gimbal_seq} payload={gimbal_payload.hex()} udp={format_payload_preview(packet, 64)}")
            return
        payload = NEUTRAL_PAYLOAD
        duss = build_control(payload, self.seq)
        seq_start = self.seq
        self.seq = (self.seq + 1) & 0xFFFF
        with self.envelope_lock:
            packet = self.envelope.wrap_control(duss)
        self._sendto(sock, packet, target)
        self.log(f"[tx control] seq={seq_start} payload={payload.hex()} udp={format_payload_preview(packet, 64)}")

    def _send_neutral_control(self, sock: socket.socket, target: tuple[str, int]) -> None:
        assert self.envelope is not None
        duss = build_control(NEUTRAL_PAYLOAD, self.seq)
        seq_start = self.seq
        self.seq = (self.seq + 1) & 0xFFFF
        with self.envelope_lock:
            packet = self.envelope.wrap_control(duss)
        self._sendto(sock, packet, target)
        self.log(f"[tx neutral] seq={seq_start} payload={NEUTRAL_PAYLOAD.hex()} udp={format_payload_preview(packet, 64)}")

    @staticmethod
    def _with_fire_bit(payload: bytes) -> bytes:
        if len(payload) != 11:
            return CONTROL_PAYLOADS["trigger_button"]
        data = bytearray(payload)
        data[10] |= 0x20
        return bytes(data)

    def _drain(self, sock: socket.socket, max_packets: int) -> None:
        for _ in range(max_packets):
            if self.stop_event.is_set():
                return
            readable, _, _ = select.select([sock], [], [], 0.02)
            if not readable:
                return
            try:
                data, _ = sock.recvfrom(65535)
            except OSError as exc:
                if self._is_would_block(exc):
                    return
                raise
            self._handle_rx(data, None)

    def _handle_rx(self, data: bytes, h264_file) -> None:
        assert self.envelope is not None
        with self.envelope_lock:
            expected_session = self.envelope.session
            if len(data) >= 4 and data[2:4] != expected_session:
                self.log(
                    f"[rx ignored-session] session={data[2:4].hex()} "
                    f"expected={expected_session.hex()} len={len(data)}"
                )
                return

        frames = parse_duss_frames(data)
        if len(data) >= 34:
            inner_len = int.from_bytes(data[32:34], "little")
            if 34 + inner_len <= len(data):
                frames.extend(parse_duss_frames(data[34 : 34 + inner_len]))
        unique_frames = []
        seen_frames = set()
        for frame in frames:
            if not (frame["header_crc_ok"] and frame["body_crc_ok"]):
                continue
            key = (
                frame.get("sender"),
                frame.get("receiver"),
                frame.get("seq"),
                frame.get("cmdset"),
                frame.get("cmdid"),
                bytes(frame.get("payload", b"")).hex() if isinstance(frame.get("payload"), bytes) else "",
            )
            if key in seen_frames:
                continue
            seen_frames.add(key)
            unique_frames.append(frame)

        if unique_frames:
            with self.envelope_lock:
                self.envelope.observe_inbound(data)
            self.packets += 1
            self.log(f"[rx] len={len(data)} hex={format_payload_preview(data, 80)}")
            for frame in unique_frames:
                self.duss_frames += 1
                payload = frame["payload"]
                assert isinstance(payload, bytes)
                self.log(
                    f"[duss] sender=0x{frame['sender']:02x} recv=0x{frame['receiver']:02x} "
                    f"seq={frame['seq']} attr=0x{frame['attr']:02x} "
                    f"cmd=0x{frame['cmdset']:02x}/0x{frame['cmdid']:02x} payload={payload.hex()}"
                )
                if frame["cmdset"] == 0x48 and frame["cmdid"] == 0x08:
                    decoded = decode_4808(payload)
                    if isinstance(decoded, GimbalTelemetry):
                        self.events.put(AppEvent("gimbal", gimbal=decoded))
                    elif isinstance(decoded, OdometryTelemetry):
                        self.events.put(AppEvent("odometry", odometry=decoded))
                        self.events.put(
                            AppEvent(
                                "robot_stats",
                                robot_stats=RobotStatsTelemetry(
                                    battery_percent=decoded.battery_percent,
                                    payload_hex=decoded.payload_hex,
                                ),
                            )
                        )
                elif frame["cmdset"] == 0x3F and frame["cmdid"] == 0x03:
                    decoded_stats = decode_3f03(payload)
                    if decoded_stats is not None:
                        self.events.put(AppEvent("robot_stats", robot_stats=decoded_stats))
                elif frame["cmdset"] == 0x3F and frame["cmdid"] == 0x1D:
                    pcm = self._decode_audio_rx_payload(payload)
                    if pcm:
                        self._queue_audio_rx_pcm(pcm)
                        self.events.put(AppEvent("audio_level", audio_rx_level=audio_level_percent(pcm)))
            return

        is_video_packet = looks_like_stream_fragment(data)
        with self.envelope_lock:
            if is_video_packet and len(data) >= 12:
                candidate = int.from_bytes(data[10:12], "little")
                if candidate:
                    self.envelope.control_tx_tick = candidate
            else:
                self.envelope.observe_inbound(data)
        self.packets += 1
        if is_video_packet:
            if self.video_packets == 0 or self.video_packets % 100 == 0:
                self.log(f"[rx video] packets={self.video_packets + 1} len={len(data)} hex={format_payload_preview(data, 40)}")
        else:
            self.log(f"[rx] len={len(data)} hex={format_payload_preview(data, 80)}")

        if is_video_packet:
            h264 = data[20:]
            self.video_packets += 1
            self.video_bytes += len(h264)
            if h264_file is not None:
                h264_file.write(h264)
            if self.video_input_queue is not None:
                while not self.stop_event.is_set():
                    try:
                        self.video_input_queue.put(h264, timeout=0.05)
                        break
                    except queue.Full:
                        continue
            return


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
        self.worker: S1Worker | None = None
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
        self.worker = S1Worker(
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

    def _finish_disconnect(self, worker: S1Worker) -> None:
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
            and self.current_action_group != "trigger"
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
