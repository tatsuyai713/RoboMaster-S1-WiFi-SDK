from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import queue
import select
import socket
import threading
import time
from typing import Callable

from robomaster_s1_designed_motion import (
    CONTROL_PAYLOADS,
    DEFAULT_PAIR_HASH1,
    DEFAULT_PAIR_HASH2,
    DUSS_ACTIONS,
    IR_GUN_INIT_COMMANDS,
    IR_GUN_CONFIG,
    LED_GUN_TRIGGER_NEUTRAL_PAYLOAD,
    NEUTRAL_PAYLOAD,
    PRE_GUN_PREROLL_COMMANDS,
    SUCCESS_SOLO_SETUP_SEND_ORDER,
    SUCCESS_SOLO_SETUP_SEQUENCE,
)

from . import protocol
from .chassis import Chassis
from .gimbal import Gimbal
from .blaster import Blaster
from .led import LED
from .camera import Camera
from .audio import Audio
from .armor import Armor
from .battery import Battery
from .settings import Settings


@dataclass
class RobotInfo:
    ip: str = ""
    mac: str = ""
    appid: str = ""
    state: str = ""
    source: tuple[str, int] | None = None


class Robot:
    """RoboMaster S1 Windows-App-compatible SDK facade."""

    def __init__(
        self,
        robot_ip: str = "",
        local_ip: str = "0.0.0.0",
        appid_bind_ip: str = "0.0.0.0",
        appid: str = "b6359877",
        local_port: int = protocol.DEFAULT_LOCAL_CONTROL_PORT,
        control_hz: float = protocol.DEFAULT_CONTROL_HZ,
        debug: bool = False,
    ) -> None:
        self.robot_ip = robot_ip
        self.local_ip = local_ip
        self.appid_bind_ip = appid_bind_ip
        self.appid = protocol.normalize_appid(appid)
        self.local_port = local_port
        self.control_hz = min(max(control_hz, 5.0), 60.0)
        self.debug = debug

        self.info = RobotInfo()
        self.seq = protocol.DEFAULT_INIT_SEQ
        self.envelope = protocol.Dc68Envelope(protocol.make_session(), protocol.make_tick_seed())
        self.sock: socket.socket | None = None
        self.target = (self.robot_ip, protocol.ROBOT_CONTROL_PORT)
        self._lock = threading.RLock()
        self._tx_lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._control_name = "stop"
        self._control_payload = NEUTRAL_PAYLOAD
        self._control_deadline: float | None = None
        self._control_sequence: deque[bytes] = deque()
        self.gimbal_pitch_sensitivity = 40
        self.gimbal_yaw_sensitivity = 50
        self._solo = False
        self._connected = False
        self._next_mode_keepalive = 0.0
        self._last_armor_damage_key: tuple[str, int, str] | None = None
        self._last_armor_damage_time = 0.0
        self._last_stats: protocol.RobotStats | None = None
        self._last_gimbal: protocol.GimbalTelemetry | None = None
        self._last_odometry: protocol.OdometryTelemetry | None = None

        self._callbacks: dict[str, list[Callable[[object], None]]] = {
            "gimbal": [],
            "odometry": [],
            "stats": [],
            "video": [],
            "audio_rx": [],
            "armor_damage": [],
            "duss": [],
        }

        self.chassis = Chassis(self)
        self.gimbal = Gimbal(self)
        self.blaster = Blaster(self)
        self.led = LED(self)
        self.camera = Camera(self)
        self.armor = Armor(self)
        self.battery = Battery(self)
        self.audio = Audio(self)
        self.settings = Settings(self)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def solo_enabled(self) -> bool:
        return self._solo

    def log(self, message: str) -> None:
        if self.debug:
            print(message)

    def on(self, event: str, callback: Callable[[object], None]) -> None:
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def _emit(self, event: str, value: object) -> None:
        for callback in self._callbacks.get(event, ()):
            try:
                callback(value)
            except Exception as exc:  # pragma: no cover - user callback
                self.log(f"[callback] {event} failed: {exc}")

    def initialize(
        self,
        conn_type: str = "sta",
        proto_type: str = "udp",
        sn: str | None = None,
        enter_solo: bool = False,
        timeout: float = 20.0,
        **_kw,
    ) -> bool:
        if self._connected:
            return True
        self._claim_appid(timeout=timeout)
        self._open_control_session()
        self._connected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        if enter_solo:
            self.enter_solo()
        return True

    def _open_control_session(self, reuse_envelope: bool = False, preconnect_timeout: float = 5.0) -> None:
        self.sock = protocol.open_udp(self.local_ip, self.local_port)
        self.sock.setblocking(False)
        self.target = (self.robot_ip, protocol.ROBOT_CONTROL_PORT)
        if not reuse_envelope:
            self.envelope = protocol.Dc68Envelope(protocol.make_session(), protocol.make_tick_seed())
        self._preconnect(timeout=preconnect_timeout)
        self._send_connect_setup()

    def close(self) -> None:
        try:
            if self._solo:
                self.exit_solo()
        finally:
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=1.0)
            self._thread = None
            if self.sock is not None:
                self.sock.close()
            self.sock = None
            self._connected = False

    def set_robot_mode(self, mode: str = "free") -> bool:
        key = str(mode).lower()
        if key in {"free", "solo", "gimbal_lead", "chassis_lead"}:
            self.enter_solo()
        elif key in {"idle", "off", "exit"}:
            self.exit_solo()
        else:
            raise ValueError("mode must be free/solo/gimbal_lead/chassis_lead or idle/off/exit")
        return True

    def get_robot_mode(self) -> str:
        return "free" if self._solo else "idle"

    def get_battery(self) -> int | None:
        return self.battery.get_battery()

    def get_version(self) -> str:
        raise NotImplementedError("Version query is not mapped for the S1 Wi-Fi protocol yet")

    def get_sn(self) -> str:
        return ""

    def play_sound(self, sound_id: int, times: int = 1) -> bool:
        raise NotImplementedError("Official sound_id mapping is not established for the S1 Wi-Fi protocol yet")

    def play_audio(self, filename: str) -> bool:
        raise NotImplementedError("Robot-side file playback is not mapped for the S1 Wi-Fi protocol yet")

    def poweroff(self) -> None:
        if not self._connected:
            raise RuntimeError("Robot is not initialized")
        self.settings.poweroff()
        time.sleep(0.05)
        self._solo = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self._connected = False

    def __enter__(self) -> Robot:
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self.close()

    def _claim_appid(self, timeout: float) -> bool:
        appid_bytes = self.appid.encode("ascii")
        sock = protocol.open_udp(self.appid_bind_ip or "0.0.0.0", protocol.APP_PORT, broadcast=True)
        deadline = time.monotonic() + timeout
        selected_robot_ip = self.robot_ip.strip()
        saw_broadcast = False
        broadcast_probe_deadline = time.monotonic() + 4.0 if selected_robot_ip else deadline
        last_claim = 0.0
        try:
            if selected_robot_ip:
                sock.sendto(appid_bytes, (selected_robot_ip, protocol.ROBOT_APP_PORT))
                last_claim = time.monotonic()
                self.log(f"[appid] initial claim {self.appid} -> {selected_robot_ip}:{protocol.ROBOT_APP_PORT}")
            while time.monotonic() < deadline:
                now = time.monotonic()
                if selected_robot_ip and not saw_broadcast and now >= broadcast_probe_deadline:
                    self.robot_ip = selected_robot_ip
                    self.info = RobotInfo(ip=selected_robot_ip, appid=self.appid, state="reconnect")
                    self.log(f"[appid] reconnect using Robot IP {selected_robot_ip}")
                    return True
                if selected_robot_ip and saw_broadcast and now - last_claim >= 1.0:
                    sock.sendto(appid_bytes, (selected_robot_ip, protocol.ROBOT_APP_PORT))
                    last_claim = now
                    self.log(f"[appid] repeat claim {self.appid} -> {selected_robot_ip}:{protocol.ROBOT_APP_PORT}")
                readable, _, _ = select.select([sock], [], [], 0.20)
                for ready in readable:
                    data, addr = ready.recvfrom(65535)
                    broadcast = protocol.parse_robot_broadcast(data)
                    if broadcast is None:
                        continue
                    saw_broadcast = True
                    selected_robot_ip = broadcast.robot_ip or addr[0]
                    self.robot_ip = selected_robot_ip
                    self.info = RobotInfo(
                        ip=selected_robot_ip,
                        mac=broadcast.robot_mac,
                        appid=broadcast.appid_text,
                        state="pairing" if broadcast.is_pairing else "idle",
                        source=addr,
                    )
                    if broadcast.appid_text == self.appid:
                        sock.sendto(appid_bytes, (selected_robot_ip, protocol.ROBOT_APP_PORT))
                        self.log(f"[appid] matched ack {self.appid} -> {selected_robot_ip}:{protocol.ROBOT_APP_PORT}")
                        return broadcast.is_pairing
                    if broadcast.appid_bytes == b"\x00" * 8 or broadcast.is_pairing:
                        sock.sendto(appid_bytes, (selected_robot_ip, protocol.ROBOT_APP_PORT))
                        last_claim = time.monotonic()
                        self.log(f"[appid] claim {self.appid} -> {selected_robot_ip}:{protocol.ROBOT_APP_PORT}")
            raise TimeoutError(f"AppID claim timed out for {self.appid}")
        finally:
            sock.close()

    def _preconnect(self, timeout: float) -> None:
        assert self.sock is not None
        deadline = time.monotonic() + timeout
        last_send = 0.0
        last_other_session: bytes | None = None
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now - last_send >= 0.20:
                packet = self.envelope.build_preconnect()
                self.sock.sendto(packet, self.target)
                self.log(f"[preconnect] {packet.hex()}")
                last_send = now
            readable, _, _ = select.select([self.sock], [], [], 0.03)
            for ready in readable:
                data, _addr = ready.recvfrom(65535)
                if len(data) >= 4 and data[2:4] == self.envelope.session:
                    self.envelope.observe_inbound(data)
                    return
                if len(data) >= 4:
                    other = data[2:4]
                    last_other_session = other
                    candidate = protocol.increment_session(other)
                    self.envelope.session = candidate
                    last_send = 0.0
                    break
        detail = f"; last inbound session={last_other_session.hex()}" if last_other_session else ""
        self.log(f"[preconnect] no ACK for session {self.envelope.session.hex()}{detail}; continuing")

    def _next_seq(self) -> int:
        with self._lock:
            seq = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            return seq

    @staticmethod
    def _is_would_block(exc: OSError) -> bool:
        return isinstance(exc, BlockingIOError) or getattr(exc, "winerror", None) == 10035 or getattr(exc, "errno", None) in (10035, 11)

    def _send_packet(self, packet: bytes) -> None:
        if self.sock is None:
            raise RuntimeError("Robot is not initialized")
        deadline = time.monotonic() + 1.0
        with self._tx_lock:
            while not self._stop.is_set():
                try:
                    self.sock.sendto(packet, self.target)
                    return
                except OSError as exc:
                    if not self._is_would_block(exc):
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError("UDP send timed out while waiting for socket write readiness") from exc
                    select.select([], [self.sock], [], 0.01)

    def send_duss(self, sender: int, receiver: int, attr: int, cmdset: int, cmdid: int, payload: bytes = b"") -> int:
        seq = self._next_seq()
        duss = protocol.build_duss(sender, receiver, attr, cmdset, cmdid, payload, seq)
        with self._lock:
            packet = self.envelope.wrap_direct(duss, attr)
        self._send_packet(packet)
        self.log(f"[duss] seq={seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} payload={payload.hex()}")
        return seq

    def send_control_payload(self, payload: bytes) -> int:
        seq = self._next_seq()
        duss = protocol.build_control(payload, seq)
        with self._lock:
            packet = self.envelope.wrap_control(duss)
        self._send_packet(packet)
        return seq

    def set_control_payload(self, payload: bytes, timeout: float | None = 5.0) -> None:
        with self._lock:
            self._control_name = ""
            self._control_payload = payload
            self._control_deadline = None if timeout is None else time.monotonic() + max(0.02, timeout)

    def set_control_action(self, name: str, timeout: float | None = None) -> None:
        with self._lock:
            self._control_name = name
            self._control_payload = CONTROL_PAYLOADS.get(name, NEUTRAL_PAYLOAD)
            self._control_deadline = None if timeout is None else time.monotonic() + max(0.02, timeout)

    def queue_control_sequence(self, payloads: tuple[bytes, ...] | list[bytes]) -> None:
        with self._lock:
            self._control_sequence.extend(payloads)

    def pulse_control_payload(self, payload: bytes, seconds: float = 0.20) -> None:
        frames = max(1, round(max(0.02, seconds) * self.control_hz))
        with self._lock:
            self._control_payload = NEUTRAL_PAYLOAD
            self._control_deadline = None
            self._control_sequence.clear()
            self._control_name = "stop"
            self._control_sequence.extend([payload] * frames)
            self._control_sequence.append(NEUTRAL_PAYLOAD)

    def reset_control_state(self) -> None:
        with self._lock:
            self._control_name = "stop"
            self._control_payload = NEUTRAL_PAYLOAD
            self._control_deadline = None
            self._control_sequence.clear()

    def _send_named(self, name: str) -> None:
        sender, receiver, attr, cmdset, cmdid, payload_hex = DUSS_ACTIONS[name]
        self.send_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex))
        time.sleep(0.006)

    def _setup_entries(self):
        hash1 = DEFAULT_PAIR_HASH1.encode("ascii").hex()
        hash2 = DEFAULT_PAIR_HASH2.encode("ascii").hex()
        entries = {}
        for index, entry in enumerate(SUCCESS_SOLO_SETUP_SEQUENCE):
            name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = entry
            entries[protocol.DEFAULT_INIT_SEQ + index] = (
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
        return entries

    def _send_setup_entries(self, solo_entries: bool) -> None:
        entries = self._setup_entries()
        for seq_ref in SUCCESS_SOLO_SETUP_SEND_ORDER:
            is_solo_entry = seq_ref >= protocol.DEFAULT_INIT_SEQ + 19
            if is_solo_entry != solo_entries:
                continue
            name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = entries[seq_ref]
            payload = bytes.fromhex(payload_hex)
            seq = self._next_seq()
            duss = protocol.build_duss(sender, receiver, attr, cmdset, cmdid, payload, seq)
            if kind == "control":
                with self._lock:
                    packet = self.envelope.wrap_control(duss)
                self._send_packet(packet)
                time.sleep(1.0 / self.control_hz)
            else:
                with self._lock:
                    packet = self.envelope.wrap_direct(duss, bytes.fromhex(reference_prefix)[18:20])
                self._send_packet(packet)
                time.sleep(0.006)

    def _send_connect_setup(self) -> None:
        self._send_setup_entries(solo_entries=False)

    def enter_solo(self) -> None:
        if self._solo:
            return
        self.reset_control_state()
        self._send_setup_entries(solo_entries=True)
        self._send_solo_entry_effect()
        self.reset_control_state()
        self._solo = True
        self._next_mode_keepalive = 0.0

    def _send_solo_entry_effect(self) -> None:
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
            if kind == "control":
                self.send_control_payload(NEUTRAL_PAYLOAD)
                time.sleep(1.0 / self.control_hz)
                continue
            assert command is not None
            sender, receiver, attr, cmdset, cmdid, payload_hex = command
            self.send_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex))
            time.sleep(0.01)

    def exit_solo(self) -> None:
        if not self._solo:
            return
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
            if kind == "control":
                self.send_control_payload(NEUTRAL_PAYLOAD)
                time.sleep(1.0 / self.control_hz)
                continue
            assert command is not None
            sender, receiver, attr, cmdset, cmdid, payload_hex = command
            self.send_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex))
            time.sleep(0.01)
        self.reset_control_state()
        self._solo = False
        self._next_mode_keepalive = 0.0

    def fire(self) -> None:
        self.queue_control_sequence((LED_GUN_TRIGGER_NEUTRAL_PAYLOAD,) * 6)

    def fire_led_gun(self) -> None:
        self.queue_control_sequence((LED_GUN_TRIGGER_NEUTRAL_PAYLOAD,) * 6)

    def fire_physical_gun(self) -> None:
        sender, receiver, attr, cmdset, cmdid, payload_hex = DUSS_ACTIONS["physical_fire_once"]
        self.send_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex))

    def _send_control_frame(self) -> None:
        with self._lock:
            if self._control_sequence:
                payload = self._control_sequence.popleft()
                control_name = ""
                sequence_payload = True
            elif self._control_deadline is not None and time.monotonic() >= self._control_deadline:
                self._control_name = "stop"
                self._control_payload = NEUTRAL_PAYLOAD
                self._control_deadline = None
                payload = NEUTRAL_PAYLOAD
                control_name = "stop"
                sequence_payload = False
            else:
                payload = self._control_payload
                control_name = self._control_name
                pitch_sensitivity = self.gimbal_pitch_sensitivity
                yaw_sensitivity = self.gimbal_yaw_sensitivity
                sequence_payload = False

        if sequence_payload or not control_name:
            self.send_control_payload(payload)
            return

        if control_name in {"forward", "back", "left", "right"}:
            self.send_control_payload(CONTROL_PAYLOADS[control_name])
            return

        if control_name in {"gimbal_left", "gimbal_right", "gimbal_up", "gimbal_down", "gimbal_stop"}:
            pitch_gain = max(0.0, pitch_sensitivity / 50.0)
            yaw_gain = max(0.0, yaw_sensitivity / 50.0)
            vectors = {
                "gimbal_left": (0.0, 0.6 * yaw_gain),
                "gimbal_right": (0.0, -0.6 * yaw_gain),
                "gimbal_up": (0.6 * pitch_gain, 0.0),
                "gimbal_down": (-0.6 * pitch_gain, 0.0),
                "gimbal_stop": (0.0, 0.0),
            }
            pitch, yaw = vectors[control_name]
            self.send_duss(0x02, 0x04, 0x00, 0x04, 0x69, protocol.build_gimbal_velocity_payload(pitch, yaw))
            return

        if control_name == "stop":
            self.send_control_payload(NEUTRAL_PAYLOAD)
            self.send_duss(0x02, 0x04, 0x00, 0x04, 0x69, protocol.build_gimbal_velocity_payload(0.0, 0.0))
            return

        self.send_control_payload(NEUTRAL_PAYLOAD)

    def send_audio_block(self, audio: bytes, block_index: int) -> int:
        payload = (
            (block_index & 0xFFFFFFFF).to_bytes(4, "little")
            + b"\x00"
            + len(audio).to_bytes(2, "little")
            + audio
        )
        return self.send_duss(0x02, 0x09, 0x00, 0x00, 0x09, payload)

    def _loop(self) -> None:
        interval = 1.0 / self.control_hz
        next_control = time.monotonic()
        while not self._stop.is_set():
            if self.sock is not None:
                readable, _, _ = select.select([self.sock], [], [], 0.001)
                for ready in readable:
                    data, _addr = ready.recvfrom(65535)
                    self._handle_rx(data)
            now = time.monotonic()
            if self._connected and now >= next_control:
                if self._solo:
                    self._send_control_frame()
                else:
                    self.send_control_payload(NEUTRAL_PAYLOAD)
                next_control += interval
                if next_control < now - interval:
                    next_control = now + interval
            if self._connected and now >= self._next_mode_keepalive:
                self._send_mode_keepalive()
                self._next_mode_keepalive = now + 1.0
            time.sleep(0.001)

    def _send_mode_keepalive(self) -> None:
        if self.sock is None:
            return
        if self._solo:
            self.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, bytes.fromhex("0b0300"))
        else:
            self.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, bytes.fromhex("000300"))
            self.send_duss(0x02, 0x07, 0x40, 0x07, 0x17, b"")

    def _handle_rx(self, data: bytes) -> None:
        if protocol.looks_like_video_fragment(data):
            self._emit("video", data[20:])
            return
        with self._lock:
            self.envelope.observe_inbound(data)
        frames = protocol.parse_duss_frames(data)
        if len(data) >= 36:
            inner_len = int.from_bytes(data[32:34], "little")
            if inner_len and len(data) >= 34 + inner_len:
                frames.extend(protocol.parse_duss_frames(data[34 : 34 + inner_len]))
        for frame in frames:
            if not frame.get("body_crc_ok"):
                continue
            self._emit("duss", frame)
            payload = frame["payload"]
            if not isinstance(payload, bytes):
                continue
            cmdset = int(frame["cmdset"])
            cmdid = int(frame["cmdid"])
            armor_damage = protocol.decode_armor_damage(
                int(frame["sender"]),
                int(frame["receiver"]),
                int(frame["seq"]),
                int(frame["attr"]),
                cmdset,
                cmdid,
                payload,
            )
            if armor_damage is not None and self._should_emit_armor_damage(armor_damage):
                self._emit("armor_damage", armor_damage)
            if cmdset == 0x48 and cmdid == 0x08:
                decoded = protocol.decode_4808(payload)
                if isinstance(decoded, protocol.GimbalTelemetry):
                    self._last_gimbal = decoded
                    self._emit("gimbal", decoded)
                elif isinstance(decoded, protocol.OdometryTelemetry):
                    self._last_odometry = decoded
                    self._emit("odometry", decoded)
                    if decoded.battery_percent is not None:
                        stats = protocol.RobotStats(battery_percent=decoded.battery_percent)
                        self._last_stats = stats
                        self._emit("stats", stats)
            elif cmdset == 0x3F and cmdid == 0x03:
                stats = protocol.decode_3f03(payload)
                if stats is not None:
                    self._last_stats = stats
                    self._emit("stats", stats)
            elif cmdset == 0x3F and cmdid == 0x1D:
                self._emit("audio_rx", payload)

    def _should_emit_armor_damage(self, event: protocol.ArmorDamageEvent) -> bool:
        if event.source != "armor_impact":
            return True
        now = time.monotonic()
        key = (event.source, event.sender, event.payload_hex)
        if self._last_armor_damage_key == key and now - self._last_armor_damage_time < 0.30:
            self._last_armor_damage_time = now
            return False
        self._last_armor_damage_key = key
        self._last_armor_damage_time = now
        return True
