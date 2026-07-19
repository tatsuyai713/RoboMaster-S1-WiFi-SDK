from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import call, patch

from robomaster_lab_sdk.config import LabSdkConfig
from robomaster_lab_sdk.robot import Robot


class _Base:
    def __init__(self, calls) -> None:  # noqa: ANN001
        self.calls = calls
        self.robot_ip = "192.0.2.1"
        self.connected = False

    def on(self, event, callback):  # noqa: ANN001
        return callback

    def initialize(self, **kwargs) -> bool:  # noqa: ANN003
        self.calls.append("connect")
        self.connected = True
        return True

    def close(self) -> None:
        self.calls.append("close")
        self.connected = False


class _Bridge:
    def __init__(self, ready: bool = True) -> None:
        self.robot_ip = ""
        self.ready = ready
        self.calls = []

    def prime(self, count=1, interval=0.0) -> None:
        self.calls.append("prime")

    def send(self, **command) -> bool:  # noqa: ANN003
        self.calls.append(("send", command.get("method")))
        return True

    def wait_for_telemetry(self, timeout=None) -> bool:  # noqa: ANN001
        self.calls.append("wait")
        return self.ready

    def close(self) -> None:
        self.calls.append("close")


def zero_delay_config(**values) -> LabSdkConfig:  # noqa: ANN003
    defaults = {
        "connect_settle_sec": 0.0,
        "lab_mode_settle_sec": 0.0,
        "upload_settle_sec": 0.0,
        "program_start_settle_sec": 0.0,
        "upload_retry_timeout_sec": 0.0,
        "bridge_ready_timeout_sec": 0.0,
        "bridge_probe_interval_sec": 0.0,
    }
    defaults.update(values)
    return LabSdkConfig(**defaults)


class LabLifecycleTests(unittest.TestCase):
    def test_robot_requires_matching_session_telemetry(self) -> None:
        robot = Robot(config=zero_delay_config())
        self.assertTrue(robot.bridge.require_session_id)

    def test_initialize_orders_connect_lab_upload_and_start(self) -> None:
        calls = []
        robot = Robot(
            config=zero_delay_config(
                connect_settle_sec=0.11,
                lab_mode_settle_sec=0.22,
                upload_settle_sec=0.33,
            )
        )
        robot.base = _Base(calls)
        robot.bridge = SimpleNamespace(robot_ip="")
        robot.enter_lab = lambda: calls.append("lab")
        robot.upload_lab_bridge = lambda: calls.append("upload")
        robot.start_lab_bridge = lambda: calls.append("start")

        with patch("robomaster_lab_sdk.robot.time.sleep") as sleep:
            self.assertTrue(robot.initialize())
        self.assertEqual(calls, ["connect", "lab", "upload", "start"])
        self.assertEqual(sleep.call_args_list, [call(0.11), call(0.22), call(0.33)])

    def test_bridge_readiness_probe_primes_before_requesting_telemetry(self) -> None:
        robot = object.__new__(Robot)
        robot.config = zero_delay_config(bridge_ready_timeout_sec=0.1)
        robot.bridge = _Bridge(ready=True)

        robot._wait_for_lab_bridge()

        self.assertEqual(
            robot.bridge.calls,
            ["prime", ("send", "set_telemetry"), "wait"],
        )

    def test_bridge_start_timeout_closes_transport(self) -> None:
        robot = object.__new__(Robot)
        robot.config = zero_delay_config()
        robot.bridge = _Bridge(ready=False)

        with self.assertRaises(TimeoutError):
            robot._wait_for_lab_bridge()
        self.assertEqual(robot.bridge.calls[-1], "close")


if __name__ == "__main__":
    unittest.main()
