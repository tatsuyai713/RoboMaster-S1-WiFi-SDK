from __future__ import annotations

from collections import defaultdict
import ftplib
from pathlib import Path
import sys
import threading
import time
from typing import Callable

from .bridge import DEFAULT_CONTROL_PORT, DEFAULT_TELEMETRY_PORT, LabBridge, LabTelemetry
from .config import DEFAULT_CONFIG, LabSdkConfig
from .program import build_lab_bridge_dsp, upload_lab_dsp
from .action import ImmediateAction
from .unsupported import unsupported

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_SDK_DIR = PROJECT_ROOT / "SDK"
if str(BASE_SDK_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_SDK_DIR))

from robomaster_s1_sdk import Robot as BaseRobot  # noqa: E402


class Robot:
    def __init__(
        self,
        robot_ip: str = "",
        local_ip: str = "0.0.0.0",
        appid: str = "b6359877",
        control_port: int = DEFAULT_CONTROL_PORT,
        telemetry_port: int = DEFAULT_TELEMETRY_PORT,
        config: LabSdkConfig | None = None,
        debug: bool = False,
    ) -> None:
        base_config = config or DEFAULT_CONFIG
        self.config = LabSdkConfig(
            control_port=int(control_port),
            telemetry_port=int(telemetry_port),
            control_period_sec=base_config.control_period_sec,
            telemetry_period_sec=base_config.telemetry_period_sec,
            command_timeout_sec=base_config.command_timeout_sec,
            command_decay_per_tick=base_config.command_decay_per_tick,
            command_zero_epsilon=base_config.command_zero_epsilon,
            command_angular_zero_epsilon=base_config.command_angular_zero_epsilon,
            max_chassis_speed=base_config.max_chassis_speed,
            max_chassis_yaw_speed=base_config.max_chassis_yaw_speed,
            max_gimbal_speed=base_config.max_gimbal_speed,
            connect_settle_sec=base_config.connect_settle_sec,
            lab_mode_settle_sec=base_config.lab_mode_settle_sec,
            upload_settle_sec=base_config.upload_settle_sec,
            program_start_settle_sec=base_config.program_start_settle_sec,
            upload_retry_timeout_sec=base_config.upload_retry_timeout_sec,
            bridge_ready_timeout_sec=base_config.bridge_ready_timeout_sec,
            bridge_probe_interval_sec=base_config.bridge_probe_interval_sec,
        )
        self.robot_ip = robot_ip
        self.local_ip = local_ip
        self.appid = appid
        self.debug = debug
        self.conn_type = ""
        self.proto_type = ""
        self.base = BaseRobot(robot_ip=robot_ip, local_ip=local_ip, appid=appid, debug=debug)
        self.bridge = LabBridge(
            robot_ip=robot_ip,
            control_port=self.config.control_port,
            telemetry_port=self.config.telemetry_port,
            debug=debug,
            require_session_id=True,
        )
        self._callbacks: dict[str, list[Callable[[object], None]]] = defaultdict(list)
        self._command = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "gimbal_pitch": 0.0,
            "gimbal_yaw": 0.0,
        }
        self._command_lock = threading.RLock()
        self._command_stop = threading.Event()
        self._command_wake = threading.Event()
        self._command_thread: threading.Thread | None = None
        self._telemetry_requests: dict[str, tuple[set[str], int]] = {}
        self._telemetry_cache: dict[str, object] = {}
        self._last_dsp_md5 = ""
        self._last_guid = ""
        self._last_sign = ""
        self._last_full_marker = 0
        self._last_guid_marker = 0
        self._base_events_bound = False

        from .chassis import Chassis
        from .gimbal import Gimbal
        from .blaster import Blaster
        from .led import LED
        from .camera import Camera
        from .battery import Battery
        from .armor import Armor
        from .sensor import DistanceSensor
        from .sensor_adaptor import SensorAdaptor
        from .servo import Servo
        from .robotic_arm import RoboticArm
        from .gripper import Gripper
        from .vision import Vision
        from .uart import Uart
        from .ai_module import AiModule
        from .media import Media

        self.chassis = Chassis(self)
        self.gimbal = Gimbal(self)
        self.blaster = Blaster(self)
        self.led = LED(self)
        self.camera = Camera(self)
        self.battery = Battery(self)
        self.armor = Armor(self)
        self.sensor = DistanceSensor(self)
        self.sensor_adaptor = SensorAdaptor(self)
        self.servo = Servo(self)
        self.robotic_arm = RoboticArm(self)
        self.gripper = Gripper(self)
        self.vision = Vision(self)
        self.uart = Uart(self)
        self.ai_module = AiModule(self)
        self.media = Media(self)

    @property
    def connected(self) -> bool:
        return self.base.connected

    @property
    def is_initialized(self) -> bool:
        return self.connected

    @property
    def ip(self) -> str:
        return self.robot_ip

    @property
    def info(self):
        return self.base.info

    def send_duss(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self.base.send_duss(*args, **kwargs)

    def initialize(self, conn_type: str = "sta", proto_type: str = "udp", sn: str | None = None, **kwargs) -> bool:
        auto_lab = bool(kwargs.pop("auto_lab", True))
        self.conn_type = conn_type
        self.proto_type = proto_type
        if not self._base_events_bound:
            for event in ("video", "audio_rx", "armor_damage", "stats", "duss"):
                self.base.on(event, lambda value, event=event: self._emit(event, value))
            self._base_events_bound = True
        initialized = self.base.initialize(
            conn_type=conn_type,
            proto_type=proto_type,
            sn=sn,
            **kwargs,
        )
        if not initialized:
            return False
        self.robot_ip = self.base.robot_ip
        self.bridge.robot_ip = self.robot_ip
        if auto_lab:
            try:
                time.sleep(self.config.connect_settle_sec)
                self.enter_lab()
                time.sleep(self.config.lab_mode_settle_sec)
                self.upload_lab_bridge()
                time.sleep(self.config.upload_settle_sec)
                self.start_lab_bridge()
            except Exception:
                try:
                    self.bridge.close()
                finally:
                    self.base.close()
                raise
        return True

    def get_module(self, name: str):
        modules = {
            "chassis": self.chassis,
            "gimbal": self.gimbal,
            "blaster": self.blaster,
            "led": self.led,
            "camera": self.camera,
            "battery": self.battery,
            "armor": self.armor,
            "sensor": self.sensor,
            "sensor_adaptor": self.sensor_adaptor,
            "servo": self.servo,
            "robotic_arm": self.robotic_arm,
            "gripper": self.gripper,
            "vision": self.vision,
            "uart": self.uart,
            "ai_module": self.ai_module,
        }
        return modules.get(str(name))

    def reset(self) -> bool:
        self.chassis.stop()
        self.gimbal.stop()
        return self.set_robot_mode("free")

    def reset_robot_mode(self) -> bool:
        return self.set_robot_mode("gimbal_lead")

    def get_robot_mode(self) -> str:
        return getattr(self, "_robot_mode", "free")

    def get_version(self) -> str:
        return unsupported("firmware version query")

    def get_sn(self) -> str:
        return unsupported("serial-number query")

    def play_sound(self, sound_id: int, times: int = 1) -> ImmediateAction:
        accepted = True
        for _ in range(max(1, int(times))):
            accepted = self.media.play_sound(sound_id) and accepted
        return ImmediateAction(accepted=accepted)

    def play_audio(self, filename: str) -> ImmediateAction:
        return unsupported("host audio-file playback")

    def close(self) -> None:
        self.stop_command_stream()
        try:
            self.bridge.close()
        except Exception:
            pass
        try:
            if self._last_guid and self._last_sign:
                self._send_lab_metadata(self._last_guid, self._last_sign, 0x05)
                time.sleep(0.02)
                self._send_lab_runtime_notify()
                time.sleep(0.02)
            self._stop_lab_program()
        except Exception:
            pass
        self.base.close()

    def on(self, event: str, callback: Callable[[object], None]) -> Callable[[object], None]:
        self._callbacks[event].append(callback)
        if event == "telemetry":
            self._set_telemetry_request(
                "raw_telemetry",
                {"x", "y", "yaw", "vx", "vy", "gimbal_yaw", "gimbal_pitch"},
                50,
            )
        return callback

    def off(self, event: str, callback: Callable[[object], None] | None = None) -> bool:
        callbacks = self._callbacks.get(event)
        if not callbacks:
            return False
        if callback is None:
            callbacks.clear()
            if event == "telemetry":
                self._clear_telemetry_request("raw_telemetry")
            return True
        try:
            callbacks.remove(callback)
            if event == "telemetry" and not callbacks:
                self._clear_telemetry_request("raw_telemetry")
            return True
        except ValueError:
            return False

    def _emit(self, event: str, value: object) -> None:
        for callback in tuple(self._callbacks.get(event, ())):
            try:
                callback(value)
            except Exception as exc:
                if self.debug:
                    print(f"[lab-callback] {event} failed: {exc}")

    def enter_lab(self) -> None:
        self.base.reset_control_state()
        self.base.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, bytes.fromhex("020302"))
        self.base._next_mode_keepalive = float("inf")
        time.sleep(0.02)
        payload = bytes.fromhex(
            "05000000"
            "ea03000000000000"
            "ef0300000a000000"
            "f003000000000000"
            "f1030000b80b0000"
            "f2030000dc050000"
            "0000000000000000"
        )
        self.base.send_duss(0x02, 0x09, 0x40, 0x3F, 0x09, payload)
        time.sleep(0.02)
        self.base.send_duss(0x02, 0x09, 0x40, 0x3F, 0x57, b"")

    def send_lab_runtime_notify(self) -> None:
        self._send_lab_runtime_notify()

    def send_lab_metadata(self, guid: str, sign: str, marker: int = 0x51) -> None:
        self._send_lab_metadata(guid, sign, marker)

    def send_lab_guid_metadata(self, guid: str, marker: int = 0x9D) -> None:
        self._send_lab_guid_metadata(guid, marker)

    def send_lab_upload_size(self, byte_count: int) -> None:
        self._send_lab_upload_size(byte_count)

    def start_lab_program(self, dsp_md5_hex: str) -> None:
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA2, b"\x01\x00" + bytes.fromhex(dsp_md5_hex))

    def stop_lab_program(self) -> None:
        self._stop_lab_program()

    def upload_lab_bridge(self) -> str:
        dsp, identity = build_lab_bridge_dsp(config=self.config)
        self._last_guid = identity.guid
        self._last_sign = identity.sign
        self._last_full_marker = identity.full_marker
        self._last_guid_marker = identity.guid_marker
        upload_size = len(dsp.encode("utf-8"))
        if identity.full_marker == 0x21:
            self.base.send_duss(0x02, 0x09, 0x40, 0x3F, 0x4C, b"\x00")
            time.sleep(0.02)
        self._send_lab_metadata(identity.guid, identity.sign, identity.full_marker)
        time.sleep(0.02)
        self._send_lab_guid_metadata(identity.guid, identity.guid_marker)
        time.sleep(0.02)
        if identity.full_marker == 0x21:
            self._send_lab_upload_size(upload_size)
            time.sleep(0.02)
        deadline = time.monotonic() + self.config.upload_retry_timeout_sec
        while True:
            try:
                self._last_dsp_md5 = upload_lab_dsp(self.robot_ip, dsp)
                break
            except (OSError, EOFError, ftplib.Error):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(
                    min(
                        self.config.bridge_probe_interval_sec,
                        max(0.0, deadline - time.monotonic()),
                    )
                )
        return self._last_dsp_md5

    def start_lab_bridge(self) -> None:
        if not self._last_dsp_md5:
            self.upload_lab_bridge()
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA2, b"\x01\x00" + bytes.fromhex(self._last_dsp_md5))
        time.sleep(0.02)
        self._send_lab_metadata(self._last_guid, self._last_sign, 0x52)
        time.sleep(0.02)
        self._send_lab_runtime_notify()
        time.sleep(self.config.program_start_settle_sec)
        self.bridge.on_telemetry(self._handle_telemetry)
        self.bridge.start()
        try:
            self._wait_for_lab_bridge()
        except Exception:
            try:
                self._stop_lab_program()
            except Exception:
                pass
            raise
        self._sync_telemetry_requests()
        self.start_command_stream()

    def _wait_for_lab_bridge(self) -> None:
        timeout = self.config.bridge_ready_timeout_sec
        deadline = time.monotonic() + timeout
        probe_interval = max(0.01, self.config.bridge_probe_interval_sec)
        while True:
            self.bridge.prime(count=1, interval=0.0)
            self.bridge.send(
                _event=True,
                module="system",
                method="set_telemetry",
                params={
                    "fields": ["yaw"],
                    "freq": 1,
                    "rates": {"yaw": 1},
                },
            )
            remaining = deadline - time.monotonic()
            if self.bridge.wait_for_telemetry(
                min(probe_interval, max(0.0, remaining))
            ):
                return
            if remaining <= 0.0:
                self.bridge.close()
                raise TimeoutError(
                    "Lab program did not return telemetry after Start"
                )

    def _send_lab_runtime_notify(self) -> None:
        self.base.send_duss(0x42, 0xC9, 0x80, 0x3F, 0xBA, b"\x00")
        time.sleep(0.02)
        self.base.send_duss(0x02, 0xC9, 0x80, 0x3F, 0xAB, b"\x01")

    def _send_lab_metadata(self, guid: str, sign: str, marker: int) -> None:
        payload = bytes([marker & 0xFF]) + (guid + sign).encode("ascii")
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA3, payload)

    def _send_lab_guid_metadata(self, guid: str, marker: int) -> None:
        payload = bytes([marker & 0xFF]) + guid.encode("ascii") + b"\x00\x00"
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA3, payload)

    def _send_lab_upload_size(self, byte_count: int) -> None:
        payload = b"\x01\x00\x04\x00" + int(byte_count).to_bytes(4, "little")
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA1, payload)

    def _stop_lab_program(self) -> None:
        self.base.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, bytes.fromhex("000300"))
        time.sleep(0.01)
        self.base.send_duss(0x02, 0x09, 0x40, 0x3F, 0x77, bytes.fromhex("010300"))
        time.sleep(0.01)
        self.base.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, bytes.fromhex("000300"))

    def start_command_stream(self) -> None:
        if self._command_thread is not None:
            if self._command_thread.is_alive():
                return
            self._command_thread = None
        with self._command_lock:
            self._command.update(
                {
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "gimbal_pitch": 0.0,
                    "gimbal_yaw": 0.0,
                }
            )
        self.bridge.prime(count=1)
        self._command_stop.clear()
        self._command_wake.set()
        self._command_thread = threading.Thread(
            target=self._command_loop,
            name="robomaster-lab-command",
            daemon=True,
        )
        self._command_thread.start()

    def _command_loop(self) -> None:
        period = self.config.control_period_sec
        deadline = time.monotonic() + period
        motion_active = False
        next_telemetry_sync = time.monotonic()
        while not self._command_stop.is_set():
            now = time.monotonic()
            motion_timeout = max(0.0, deadline - now)
            telemetry_timeout = max(0.0, next_telemetry_sync - now)
            timeout = (
                min(motion_timeout, telemetry_timeout)
                if motion_active
                else telemetry_timeout
            )
            woke = self._command_wake.wait(timeout)
            self._command_wake.clear()
            if self._command_stop.is_set():
                break
            now = time.monotonic()
            if now >= next_telemetry_sync:
                self._sync_telemetry_requests()
                next_telemetry_sync += 1.0
                if next_telemetry_sync <= now:
                    next_telemetry_sync += int(now - next_telemetry_sync) + 1
            if not woke and not motion_active:
                continue
            with self._command_lock:
                command = dict(self._command)
            try:
                self.bridge.send(**command)
            except Exception:
                if self.debug:
                    import traceback

                    traceback.print_exc()
            motion_active = any(
                abs(float(command.get(name, 0.0))) > 0.0
                for name in (
                    "x",
                    "y",
                    "z",
                    "gimbal_pitch",
                    "gimbal_yaw",
                )
            )
            now = time.monotonic()
            if woke or not motion_active:
                deadline = now + period
            else:
                deadline += period
                if deadline <= now:
                    deadline += (int((now - deadline) / period) + 1) * period

    def stop_command_stream(self) -> None:
        self._command_stop.set()
        self._command_wake.set()
        if self._command_thread is not None:
            self._command_thread.join(timeout=1.0)
        self._command_thread = None
        try:
            self.bridge.send(stop=True, x=0.0, y=0.0, z=0.0, gimbal_pitch=0.0, gimbal_yaw=0.0)
        except Exception:
            pass

    def update_command(self, **values: float) -> bool:
        with self._command_lock:
            self._command.update(values)
        if self._command_thread is not None and self._command_thread.is_alive():
            self._command_wake.set()
            return True
        try:
            return self.bridge.send(**values)
        except Exception:
            return False

    def send_once(self, **values: object) -> bool:
        return self.bridge.send(_event=True, **values)

    def _set_telemetry_request(
        self,
        key: str,
        fields: set[str],
        freq: int,
    ) -> None:
        self._telemetry_requests[str(key)] = (set(fields), int(freq))
        self._sync_telemetry_requests()

    def _clear_telemetry_request(self, key: str) -> None:
        self._telemetry_requests.pop(str(key), None)
        self._sync_telemetry_requests()

    def _sync_telemetry_requests(self) -> bool:
        fields: set[str] = set()
        frequency = 1
        rates: dict[str, int] = {}
        for requested_fields, requested_frequency in self._telemetry_requests.values():
            fields.update(requested_fields)
            frequency = max(frequency, int(requested_frequency))
            for field in requested_fields:
                rates[field] = max(
                    rates.get(field, 1),
                    int(requested_frequency),
                )
        return self.bridge.send(
            _event=True,
            module="system",
            method="set_telemetry",
            params={
                "fields": sorted(fields),
                "freq": frequency,
                "rates": rates,
            },
        )

    def send_fire(self, gun_type: str = "physical") -> bool:
        return self.bridge.fire(gun_type)

    def set_robot_mode(self, mode: str = "gimbal_lead") -> bool:
        key = str(mode).lower()
        if key not in {"free", "gimbal_follow", "gimbal_lead", "follow", "chassis_follow", "chassis_lead"}:
            raise ValueError("mode must be free, gimbal_follow, or chassis_follow")
        bridge_mode = {
            "gimbal_lead": "gimbal_follow",
            "chassis_lead": "chassis_follow",
        }.get(key, key)
        accepted = self.bridge.set_robot_mode(bridge_mode)
        if accepted:
            self._robot_mode = {
                "gimbal_lead": "gimbal_lead",
                "follow": "gimbal_follow",
                "chassis_follow": "chassis_lead",
            }.get(key, key)
        return accepted

    def _handle_telemetry(self, telemetry: LabTelemetry) -> None:
        values = telemetry.values
        for field in (
            "x",
            "y",
            "yaw",
            "vx",
            "vy",
            "gimbal_yaw",
            "gimbal_pitch",
        ):
            if field in values:
                self._telemetry_cache[field] = values[field]
        cached = self._telemetry_cache
        value_keys = set(values)
        if self._callbacks.get("telemetry"):
            self._emit("telemetry", telemetry)
        if self._callbacks.get("position") and value_keys.intersection(
            {"x", "y", "yaw"}
        ):
            self._emit(
                "position",
                (cached.get("x"), cached.get("y"), cached.get("yaw")),
            )
        if self._callbacks.get("velocity") and value_keys.intersection(
            {"vx", "vy"}
        ):
            self._emit(
                "velocity",
                (None, None, None, cached.get("vx"), cached.get("vy"), None),
            )
        if self._callbacks.get("attitude") and "yaw" in value_keys:
            self._emit("attitude", (cached.get("yaw"), None, None))
        if self._callbacks.get("gimbal_angle") and value_keys.intersection(
            {"gimbal_pitch", "gimbal_yaw"}
        ):
            self._emit(
                "gimbal_angle",
                (cached.get("gimbal_pitch"), cached.get("gimbal_yaw")),
            )
