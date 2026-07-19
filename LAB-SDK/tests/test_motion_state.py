from __future__ import annotations

from types import SimpleNamespace
import json
import queue
import socket
import threading
import time
import unittest

from robomaster_lab_sdk.chassis import Chassis
from robomaster_lab_sdk.bridge import (
    MAX_PRIORITY_COMMANDS,
    LabBridge,
    LabTelemetry,
    _tx_process_main,
)
from robomaster_lab_sdk.gimbal import Gimbal
from robomaster_lab_sdk.robot import Robot


class _Bridge:
    def __init__(self) -> None:
        self.commands = []
        self.stop_after = None
        self.stop_event = None

    def send(self, **command):
        self.commands.append(command)
        if self.stop_after is not None and len(self.commands) >= self.stop_after:
            self.stop_event.set()
        return True

    def call(self, module, method, **params):
        self.commands.append({"module": module, "method": method, "params": params})
        return True

    def stop_chassis(self):
        return self.call("chassis", "stop")

    def stop_gimbal(self):
        return self.call("gimbal", "stop")


class _ComponentRobot:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            max_chassis_speed=1.0,
            max_chassis_yaw_speed=120.0,
            max_gimbal_speed=120.0,
        )
        self.bridge = _Bridge()
        self.command = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "gimbal_pitch": 0.0,
            "gimbal_yaw": 0.0,
        }
        self.telemetry_requests = {}
        self.callbacks = {}

    def update_command(self, **values):
        self.command.update(values)
        return True

    def on(self, event, callback):
        self.callbacks.setdefault(event, []).append(callback)
        return callback

    def off(self, event, callback):
        callbacks = self.callbacks.get(event, [])
        if callback not in callbacks:
            return False
        callbacks.remove(callback)
        return True

    def _set_telemetry_request(self, key, fields, freq):
        self.telemetry_requests[key] = (set(fields), int(freq))

    def _clear_telemetry_request(self, key):
        self.telemetry_requests.pop(key, None)


class MotionStateTests(unittest.TestCase):
    def test_bridge_motion_queue_is_latest_only_and_events_are_bounded(self) -> None:
        bridge = LabBridge("127.0.0.1")
        bridge._tx_priority_queue = queue.Queue(maxsize=MAX_PRIORITY_COMMANDS)
        bridge._tx_event_queue = queue.Queue(maxsize=2)
        bridge._tx_state_queue = queue.Queue(maxsize=1)

        for value in range(100):
            self.assertTrue(bridge.send(x=value))
        self.assertEqual(bridge._tx_state_queue.qsize(), 1)
        _sequence, payload, _generation = bridge._tx_state_queue.get_nowait()
        latest = json.loads(payload)
        self.assertEqual(latest["x"], 99)

        self.assertTrue(bridge.call("led", "set_flash", freq=1))
        self.assertTrue(bridge.call("led", "set_flash", freq=2))
        self.assertFalse(bridge.call("led", "set_flash", freq=3))

        self.assertTrue(bridge.stop_gimbal())
        self.assertEqual(bridge._tx_priority_queue.qsize(), 1)

    def test_independent_stop_commands_are_not_coalesced(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1.0)
        port = receiver.getsockname()[1]
        priority_queue = queue.Queue(maxsize=MAX_PRIORITY_COMMANDS)
        event_queue = queue.Queue()
        state_queue = queue.Queue()
        status_queue = queue.Queue()
        stop_event = threading.Event()

        def payload(sequence, module):
            return json.dumps(
                {
                    "command_seq": sequence,
                    "module": module,
                    "method": "stop",
                }
            ).encode()

        priority_queue.put(payload(1, "chassis"))
        priority_queue.put(payload(2, "gimbal"))
        worker = threading.Thread(
            target=_tx_process_main,
            args=(
                "127.0.0.1",
                port,
                priority_queue,
                event_queue,
                state_queue,
                status_queue,
                stop_event,
                False,
            ),
        )
        worker.start()
        received = [json.loads(receiver.recv(4096)), json.loads(receiver.recv(4096))]
        stop_event.set()
        worker.join(timeout=1.0)
        receiver.close()

        self.assertEqual(
            [(item["command_seq"], item["module"]) for item in received],
            [(1, "chassis"), (2, "gimbal")],
        )

    def test_stop_discards_older_events_but_preserves_newer_order(self) -> None:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1.0)
        port = receiver.getsockname()[1]
        priority_queue = queue.Queue()
        event_queue = queue.Queue()
        state_queue = queue.Queue()
        status_queue = queue.Queue()
        stop_event = threading.Event()

        def payload(sequence, **values):
            return json.dumps({"command_seq": sequence, **values}).encode()

        event_queue.put(payload(1, module="led", method="set_flash"))
        event_queue.put(payload(3, module="chassis", method="set_wheel_speed"))
        priority_queue.put(payload(2, module="gimbal", method="stop"))
        worker = threading.Thread(
            target=_tx_process_main,
            args=(
                "127.0.0.1",
                port,
                priority_queue,
                event_queue,
                state_queue,
                status_queue,
                stop_event,
                False,
            ),
        )
        worker.start()
        received = [json.loads(receiver.recv(4096)), json.loads(receiver.recv(4096))]
        stop_event.set()
        worker.join(timeout=1.0)
        receiver.close()

        self.assertEqual([item["command_seq"] for item in received], [2, 3])

    def test_gimbal_release_then_wheel_command_does_not_restore_gimbal(self) -> None:
        robot = _ComponentRobot()
        gimbal = Gimbal(robot)
        chassis = Chassis(robot)

        gimbal.drive_speed(pitch_speed=0, yaw_speed=60)
        gimbal.stop()
        chassis.drive_wheels(100, 100, 100, 100)

        self.assertEqual(robot.command["gimbal_pitch"], 0.0)
        self.assertEqual(robot.command["gimbal_yaw"], 0.0)
        self.assertIn(
            {"module": "gimbal", "method": "stop", "params": {}},
            robot.bridge.commands,
        )

    def test_command_loop_refreshes_held_state(self) -> None:
        robot = object.__new__(Robot)
        robot.config = SimpleNamespace(control_period_sec=0.001)
        robot._command = {
            "x": 0.4,
            "y": 0.0,
            "z": 0.0,
            "gimbal_pitch": 0.0,
            "gimbal_yaw": 0.0,
        }
        robot._command_lock = threading.RLock()
        robot._command_stop = threading.Event()
        robot._command_wake = threading.Event()
        robot._command_wake.set()
        robot._telemetry_requests = {}
        robot.bridge = _Bridge()
        robot.bridge.stop_after = 5
        robot.bridge.stop_event = robot._command_stop
        robot.debug = False

        robot._command_loop()

        motion_commands = [
            command for command in robot.bridge.commands if "x" in command
        ]
        self.assertGreaterEqual(len(motion_commands), 3)
        self.assertTrue(
            all(command["x"] == 0.4 for command in motion_commands)
        )

    def test_telemetry_getters_follow_official_subscriptions(self) -> None:
        robot = _ComponentRobot()
        chassis = Chassis(robot)
        gimbal = Gimbal(robot)

        self.assertTrue(chassis.sub_velocity(freq=20, callback=lambda _value: None))
        self.assertEqual(
            robot.telemetry_requests["chassis:velocity"],
            ({"vx", "vy"}, 20),
        )
        self.assertTrue(gimbal.sub_angle(freq=50, callback=lambda _value: None))
        self.assertEqual(
            robot.telemetry_requests["gimbal:angle"],
            ({"gimbal_pitch", "gimbal_yaw"}, 50),
        )
        self.assertTrue(chassis.unsub_velocity())
        self.assertNotIn("chassis:velocity", robot.telemetry_requests)

    def test_zero_motion_stream_sleeps_until_woken(self) -> None:
        robot = object.__new__(Robot)
        robot.config = SimpleNamespace(control_period_sec=0.001)
        robot._command = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "gimbal_pitch": 0.0,
            "gimbal_yaw": 0.0,
        }
        robot._command_lock = threading.RLock()
        robot._command_stop = threading.Event()
        robot._command_wake = threading.Event()
        robot._command_wake.set()
        robot._telemetry_requests = {}
        robot.bridge = _Bridge()
        robot.debug = False
        worker = threading.Thread(target=robot._command_loop)
        worker.start()
        time.sleep(0.02)
        motion_commands = [
            command for command in robot.bridge.commands if "x" in command
        ]
        self.assertEqual(len(motion_commands), 1)
        robot._command_stop.set()
        robot._command_wake.set()
        worker.join(timeout=1.0)
        self.assertFalse(worker.is_alive())

    def test_partial_telemetry_packets_keep_complete_callback_values(self) -> None:
        robot = object.__new__(Robot)
        received = []
        robot._callbacks = {"position": [received.append]}
        robot._telemetry_cache = {}
        robot.debug = False

        robot._handle_telemetry(
            LabTelemetry(1, 1, {"x": 1.0, "y": 2.0, "yaw": 3.0})
        )
        robot._handle_telemetry(
            LabTelemetry(2, 2, {"yaw": 4.0})
        )

        self.assertEqual(received, [(1.0, 2.0, 3.0), (1.0, 2.0, 4.0)])


if __name__ == "__main__":
    unittest.main()
