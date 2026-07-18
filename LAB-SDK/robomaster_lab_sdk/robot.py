from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys
import threading
import time
from typing import Callable

from .bridge import DEFAULT_CONTROL_PORT, DEFAULT_TELEMETRY_PORT, LabBridge, LabTelemetry
from .config import DEFAULT_CONFIG, LabSdkConfig
from .program import build_lab_bridge_dsp, upload_lab_dsp

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
            command_timeout_sec=base_config.command_timeout_sec,
            command_decay_per_tick=base_config.command_decay_per_tick,
            command_zero_epsilon=base_config.command_zero_epsilon,
            command_angular_zero_epsilon=base_config.command_angular_zero_epsilon,
            max_chassis_speed=base_config.max_chassis_speed,
            max_chassis_yaw_speed=base_config.max_chassis_yaw_speed,
            max_gimbal_speed=base_config.max_gimbal_speed,
        )
        self.robot_ip = robot_ip
        self.local_ip = local_ip
        self.appid = appid
        self.debug = debug
        self.base = BaseRobot(robot_ip=robot_ip, local_ip=local_ip, appid=appid, debug=debug)
        self.bridge = LabBridge(
            robot_ip=robot_ip,
            control_port=self.config.control_port,
            telemetry_port=self.config.telemetry_port,
            debug=debug,
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
        self._command_thread: threading.Thread | None = None
        self._last_dsp_md5 = ""
        self._last_guid = ""
        self._last_sign = ""
        self._last_full_marker = 0
        self._last_guid_marker = 0

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
    def info(self):
        return self.base.info

    def send_duss(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self.base.send_duss(*args, **kwargs)

    def initialize(self, conn_type: str = "sta", proto_type: str = "udp", sn: str | None = None, **kwargs) -> bool:
        auto_lab = bool(kwargs.pop("auto_lab", True))
        self.base.on("video", lambda payload: self._emit("video", payload))
        self.base.initialize(conn_type=conn_type, proto_type=proto_type, sn=sn, **kwargs)
        self.robot_ip = self.base.robot_ip
        self.bridge.robot_ip = self.robot_ip
        if auto_lab:
            self.enter_lab()
            self.upload_lab_bridge()
            self.start_lab_bridge()
        return True

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

    def on(self, event: str, callback: Callable[[object], None]) -> None:
        self._callbacks[event].append(callback)

    def _emit(self, event: str, value: object) -> None:
        for callback in tuple(self._callbacks.get(event, ())):
            callback(value)

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
        self._last_dsp_md5 = upload_lab_dsp(self.robot_ip, dsp)
        return self._last_dsp_md5

    def start_lab_bridge(self) -> None:
        if not self._last_dsp_md5:
            self.upload_lab_bridge()
        self.base.send_duss(0x02, 0xA9, 0x40, 0x3F, 0xA2, b"\x01\x00" + bytes.fromhex(self._last_dsp_md5))
        time.sleep(0.02)
        self._send_lab_metadata(self._last_guid, self._last_sign, 0x52)
        time.sleep(0.02)
        self._send_lab_runtime_notify()
        self.bridge.on_telemetry(self._handle_telemetry)
        self.bridge.start()
        self.start_command_stream()

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
        self._command_thread = None

    def stop_command_stream(self) -> None:
        self._command_stop.set()
        if self._command_thread is not None:
            self._command_thread.join(timeout=1.0)
        self._command_thread = None
        try:
            self.bridge.send(stop=True, x=0.0, y=0.0, z=0.0, gimbal_pitch=0.0, gimbal_yaw=0.0)
        except Exception:
            pass

    def update_command(self, **values: float) -> None:
        with self._command_lock:
            self._command.update(values)
        try:
            self.bridge.send(**values)
        except Exception:
            pass

    def send_once(self, **values: object) -> None:
        self.bridge.send(_event=True, **values)

    def send_fire(self, gun_type: str = "physical") -> None:
        self.bridge.fire(gun_type)

    def set_robot_mode(self, mode: str = "free") -> bool:
        self.bridge.set_robot_mode(mode)
        return True

    def _handle_telemetry(self, telemetry: LabTelemetry) -> None:
        self._emit("telemetry", telemetry)
        values = telemetry.values
        self._emit("position", (values.get("x"), values.get("y"), values.get("chassis_rotate")))
        self._emit("velocity", (values.get("vx"), values.get("vy"), None))
        self._emit("attitude", (values.get("yaw"), None, None))
        self._emit("gimbal_angle", (values.get("gimbal_pitch"), values.get("gimbal_yaw")))
