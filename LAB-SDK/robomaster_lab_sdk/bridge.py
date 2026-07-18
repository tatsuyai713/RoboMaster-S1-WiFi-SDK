from __future__ import annotations

from dataclasses import dataclass
import json
import multiprocessing as mp
import queue
import socket
import threading
import time
from typing import Callable

from .config import DEFAULT_CONTROL_PORT, DEFAULT_TELEMETRY_PORT


@dataclass
class LabTelemetry:
    sequence: int
    timestamp_ms: int
    values: dict[str, object]


def _put_latest(q, item) -> None:  # noqa: ANN001
    while True:
        try:
            q.put_nowait(item)
            return
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                return


def _is_event_command(command: dict[str, object]) -> bool:
    event_keys = {"fire", "led", "module", "method", "mode", "stop"}
    return any(bool(command.get(key)) for key in event_keys)


def _tx_process_main(robot_ip: str, control_port: int, event_queue, state_queue, status_queue, stop_event, debug: bool) -> None:  # noqa: ANN001
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
        _put_latest(status_queue, ("tx-start", None))
        while not stop_event.is_set():
            event_payloads = []
            latest_state_payload = None

            while True:
                try:
                    event_payload = event_queue.get_nowait()
                except queue.Empty:
                    break
                if event_payload is None:
                    stop_event.set()
                    break
                event_payloads.append(event_payload)

            while True:
                try:
                    latest_state_payload = state_queue.get_nowait()
                except queue.Empty:
                    break

            payloads_to_send = event_payloads
            if latest_state_payload is not None:
                payloads_to_send.append(latest_state_payload)

            if not payloads_to_send:
                try:
                    event_payload = event_queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                if event_payload is None:
                    break
                payloads_to_send.append(event_payload)

                while True:
                    try:
                        event_payload = event_queue.get_nowait()
                    except queue.Empty:
                        break
                    if event_payload is None:
                        stop_event.set()
                        break
                    payloads_to_send.append(event_payload)

                while True:
                    try:
                        latest_state_payload = state_queue.get_nowait()
                    except queue.Empty:
                        break
                if latest_state_payload is not None:
                    payloads_to_send.append(latest_state_payload)

            if not payloads_to_send:
                continue

            try:
                for payload in payloads_to_send:
                    sock.sendto(payload, (robot_ip, control_port))
                    if debug:
                        print(f"[lab-tx] {payload.decode('utf-8', 'replace')}")
            except OSError as exc:
                _put_latest(status_queue, ("tx-error", str(exc)))
                if debug:
                    print(f"[lab-tx-error] {exc}")
    except Exception as exc:
        _put_latest(status_queue, ("tx-fatal", repr(exc)))
    finally:
        if sock is not None:
            sock.close()


def _rx_process_main(listen_ip: str, telemetry_port: int, rx_queue, status_queue, stop_event, debug: bool) -> None:  # noqa: ANN001
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        sock.bind((listen_ip or "0.0.0.0", telemetry_port))
        sock.settimeout(0.1)
        _put_latest(status_queue, ("rx-start", None))
        while not stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if debug:
                print(f"[lab-rx] {addr[0]}:{addr[1]} {payload[:160]!r}")
            _put_latest(rx_queue, (payload, addr))
    except Exception as exc:
        _put_latest(status_queue, ("rx-fatal", repr(exc)))
    finally:
        if sock is not None:
            sock.close()


class LabBridge:
    def __init__(
        self,
        robot_ip: str,
        control_port: int = DEFAULT_CONTROL_PORT,
        telemetry_port: int = DEFAULT_TELEMETRY_PORT,
        listen_ip: str = "0.0.0.0",
        debug: bool = False,
        require_session_id: bool = False,
    ) -> None:
        self.robot_ip = robot_ip
        self.control_port = int(control_port)
        self.telemetry_port = int(telemetry_port)
        self.listen_ip = listen_ip
        self.debug = debug
        self.require_session_id = require_session_id
        self._mp_context = mp.get_context("spawn")
        self._stop = self._mp_context.Event()
        self._thread: threading.Thread | None = None
        self._tx_lock = threading.RLock()
        self._tx_event_queue = None
        self._tx_state_queue = None
        self._rx_queue = None
        self._status_queue = None
        self._tx_process: mp.Process | None = None
        self._rx_process: mp.Process | None = None
        self._callbacks: list[Callable[[LabTelemetry], None]] = []
        self.last_telemetry: LabTelemetry | None = None
        self._fire_id = 0
        self._command_seq = 0
        self.session_id = int(time.time() * 1000) & 0x7FFFFFFF

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._tx_event_queue = self._mp_context.Queue(maxsize=128)
        self._tx_state_queue = self._mp_context.Queue(maxsize=1)
        self._rx_queue = self._mp_context.Queue(maxsize=64)
        self._status_queue = self._mp_context.Queue(maxsize=16)
        self._tx_process = self._mp_context.Process(
            target=_tx_process_main,
            args=(self.robot_ip, self.control_port, self._tx_event_queue, self._tx_state_queue, self._status_queue, self._stop, self.debug),
        )
        self._rx_process = self._mp_context.Process(
            target=_rx_process_main,
            args=(self.listen_ip or "0.0.0.0", self.telemetry_port, self._rx_queue, self._status_queue, self._stop, self.debug),
        )
        try:
            self._tx_process.start()
            self._rx_process.start()
            self._wait_for_process_start()
            self._thread = threading.Thread(target=self._rx_queue_loop, daemon=True)
            self._thread.start()
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        self._stop.set()
        if self._tx_event_queue is not None:
            try:
                self._tx_event_queue.put_nowait(None)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        for process in (self._tx_process, self._rx_process):
            if process is None:
                continue
            process.join(timeout=1.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
        self._tx_process = None
        self._rx_process = None
        self._tx_event_queue = None
        self._tx_state_queue = None
        self._rx_queue = None
        self._status_queue = None

    def on_telemetry(self, callback: Callable[[LabTelemetry], None]) -> None:
        self._callbacks.append(callback)

    def send(self, **command: object) -> bool:
        command.pop("_drop_if_busy", None)
        force_event = bool(command.pop("_event", False) or command.pop("_single_shot", False))
        with self._tx_lock:
            self._command_seq = (self._command_seq + 1) & 0x7FFFFFFF
            command.setdefault("command_seq", self._command_seq)
            command.setdefault("session_id", self.session_id)
        is_event = force_event or _is_event_command(command)
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        if self._tx_event_queue is None or self._tx_state_queue is None:
            return False
        if self._tx_process is not None and not self._tx_process.is_alive():
            self._drain_status()
            return False
        if is_event:
            try:
                self._tx_event_queue.put(payload, timeout=0.05)
            except queue.Full:
                return False
        else:
            _put_latest(self._tx_state_queue, payload)
        return True

    def prime(self, count: int = 5, interval: float = 0.02) -> None:
        """Send neutral packets so the robot-side bridge learns the host address."""
        neutral = {
            "stop": True,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "gimbal_pitch": 0.0,
            "gimbal_yaw": 0.0,
        }
        for _ in range(max(1, int(count))):
            self.send(**neutral)
            time.sleep(max(0.0, float(interval)))

    def call(self, module: str, method: str, **params: object) -> None:
        self.send(module=module, method=method, params=params)

    def drive_speed(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.send(x=float(x), y=float(y), z=float(z))

    def gimbal_drive_speed(self, pitch_speed: float = 0.0, yaw_speed: float = 0.0) -> None:
        self.send(gimbal_pitch=float(pitch_speed), gimbal_yaw=float(yaw_speed))

    def stop_robot(self) -> None:
        self.send(stop=True)

    def stop_chassis(self) -> None:
        self.send(_event=True, x=0.0, y=0.0, z=0.0)

    def stop_gimbal(self) -> None:
        self.send(_event=True, gimbal_pitch=0.0, gimbal_yaw=0.0)

    def set_robot_mode(self, mode: str = "free") -> None:
        self.send(mode=mode)

    def fire(self, gun_type: str = "physical") -> None:
        with self._tx_lock:
            self._fire_id = (self._fire_id + 1) & 0xFFFF
            fire_id = self._fire_id
        self.send(fire=True, gun_type=gun_type, fire_id=fire_id)

    def set_led(self, comp: str = "all", r: int = 255, g: int = 255, b: int = 255, effect: str = "on", freq: int = 1) -> None:
        self.send(led=True, comp=comp, r=int(r), g=int(g), b=int(b), effect=effect, freq=int(freq))

    def _rx_queue_loop(self) -> None:
        assert self._rx_queue is not None
        while not self._stop.is_set():
            self._drain_status()
            try:
                payload, _addr = self._rx_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                values = json.loads(payload.decode("utf-8"))
            except Exception:
                continue
            packet_session_id = values.get("session_id")
            if self.require_session_id and packet_session_id != self.session_id:
                if self.debug:
                    print(f"[lab-rx-drop] session={packet_session_id!r} expected={self.session_id}")
                continue
            if packet_session_id is not None and packet_session_id != self.session_id:
                if self.debug:
                    print(f"[lab-rx-drop] session={packet_session_id!r} expected={self.session_id}")
                continue
            telemetry = LabTelemetry(
                sequence=int(values.get("sequence", values.get("seq", 0)) or 0),
                timestamp_ms=int(values.get("time_ms", 0) or 0),
                values=values,
            )
            self.last_telemetry = telemetry
            for callback in tuple(self._callbacks):
                try:
                    callback(telemetry)
                except Exception as exc:
                    if self.debug:
                        print(f"[lab-callback] {exc}")

    def _drain_status(self) -> None:
        if self._status_queue is None:
            return
        while True:
            try:
                kind, detail = self._status_queue.get_nowait()
            except queue.Empty:
                return
            if self.debug:
                print(f"[lab-process] {kind} {detail or ''}")

    def _wait_for_process_start(self) -> None:
        if self._status_queue is None:
            raise RuntimeError("LabBridge status queue was not created")
        started: set[str] = set()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and started != {"tx-start", "rx-start"}:
            try:
                kind, detail = self._status_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if kind in {"tx-start", "rx-start"}:
                started.add(kind)
                if self.debug:
                    print(f"[lab-process] {kind}")
                continue
            if kind in {"tx-fatal", "rx-fatal"}:
                raise RuntimeError(f"LabBridge {kind}: {detail}")
            if self.debug:
                print(f"[lab-process] {kind} {detail or ''}")

        missing = {"tx-start", "rx-start"} - started
        if missing:
            details = []
            if self._tx_process is not None and not self._tx_process.is_alive():
                details.append(f"tx exit={self._tx_process.exitcode}")
            if self._rx_process is not None and not self._rx_process.is_alive():
                details.append(f"rx exit={self._rx_process.exitcode}")
            suffix = f" ({', '.join(details)})" if details else ""
            raise RuntimeError(f"LabBridge process start timeout: missing={sorted(missing)}{suffix}")
