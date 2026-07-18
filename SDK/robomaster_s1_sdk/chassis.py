from __future__ import annotations

import struct

from robomaster_s1_designed_motion import CONTROL_PAYLOADS

from .action import ImmediateAction
from .protocol import build_chassis_velocity_payload, clamp_int


class Chassis:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def drive_speed(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, timeout: float | None = None) -> bool:
        """Official-style chassis speed control.

        x is forward/backward m/s, y is lateral m/s, z is yaw speed.
        """
        self._robot.set_control_payload(build_chassis_velocity_payload(x, y, z / 150.0), timeout=timeout)
        return True

    def drive_wheels(self, w1: int = 0, w2: int = 0, w3: int = 0, w4: int = 0, timeout: float | None = None) -> bool:
        values = [clamp_int(int(v), -1000, 1000) for v in (w1, w2, w3, w4)]
        self._robot.send_duss(0x02, 0x03, 0x40, 0x3F, 0x20, struct.pack("<hhhh", *values))
        return True

    def move(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        xy_speed: float = 0.5,
        z_speed: float = 30,
    ) -> ImmediateAction:
        """Official-style relative movement placeholder.

        The official EP SDK uses this name for distance/angle actions. The S1
        Wi-Fi implementation currently has reliable speed control only, so this
        applies a short speed pulse and returns an already-completed action.
        """
        self.drive_speed(x, y, z)
        return ImmediateAction()

    def stop(self) -> None:
        self._robot.set_control_action("stop", timeout=None)

    def forward(self) -> None:
        self._robot.set_control_action("forward", timeout=None)

    def backward(self) -> None:
        self._robot.set_control_action("back", timeout=None)

    def left(self) -> None:
        self._robot.set_control_action("left", timeout=None)

    def right(self) -> None:
        self._robot.set_control_action("right", timeout=None)

    def sub_position(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        return self._subscribe_odometry(
            callback,
            lambda v: (
                v.floats[0] if len(v.floats) > 0 else 0.0,
                v.floats[1] if len(v.floats) > 1 else 0.0,
                v.heading_like if v.heading_like is not None else 0.0,
            ),
            *args,
            **kw,
        )

    def sub_velocity(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        return self._subscribe_odometry(
            callback,
            lambda v: (
                v.floats[2] if len(v.floats) > 2 else 0.0,
                v.floats[3] if len(v.floats) > 3 else 0.0,
                v.floats[4] if len(v.floats) > 4 else 0.0,
            ),
            *args,
            **kw,
        )

    def sub_attitude(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        return self._subscribe_odometry(callback, lambda v: (v.heading_like or 0.0, 0.0, 0.0), *args, **kw)

    def sub_status(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("stats", lambda value: callback(value, *args, **kw))
        return True

    def unsub_position(self) -> bool:
        return True

    def unsub_velocity(self) -> bool:
        return True

    def unsub_attitude(self) -> bool:
        return True

    def unsub_status(self) -> bool:
        return True

    def start_calibration(self) -> bool:
        self._robot.send_duss(0x02, 0x03, 0x40, 0x03, 0xF9, bytes.fromhex("e4a3997d03"))
        return True

    def enter_calibration_measurement(self) -> bool:
        self._robot.send_duss(0x02, 0x03, 0x40, 0x03, 0xF9, bytes.fromhex("e4a3997d01"))
        return True

    def stop_wheels(self) -> bool:
        return self.drive_wheels(0, 0, 0, 0)

    def _subscribe_odometry(self, callback, projector, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("odometry", lambda value: callback(projector(value), *args, **kw))
        return True
