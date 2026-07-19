from __future__ import annotations

import struct
import threading

from .action import ImmediateAction
from .protocol import build_chassis_velocity_payload, clamp_int


class Chassis:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._subscriptions = {}
        self._wheel_timer: threading.Timer | None = None

    def drive_speed(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, timeout: float | None = None) -> bool:
        """Official-style chassis speed control.

        x is forward/backward m/s, y is lateral m/s, z is yaw speed.
        """
        self._robot.set_control_payload(build_chassis_velocity_payload(x, y, z / 150.0), timeout=timeout)
        return True

    def drive_wheels(self, w1: int = 0, w2: int = 0, w3: int = 0, w4: int = 0, timeout: float | None = None) -> bool:
        values = [clamp_int(int(v), -1000, 1000) for v in (w1, w2, w3, w4)]
        self._robot.send_duss(0x02, 0x03, 0x40, 0x3F, 0x20, struct.pack("<hhhh", *values))
        if self._wheel_timer is not None:
            self._wheel_timer.cancel()
            self._wheel_timer = None
        if timeout is not None:
            self._wheel_timer = threading.Timer(
                max(0.0, float(timeout)),
                self.stop_wheels,
            )
            self._wheel_timer.daemon = True
            self._wheel_timer.start()
        return True

    def move(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        xy_speed: float = 0.5,
        z_speed: float = 30,
    ) -> ImmediateAction:
        raise NotImplementedError(
            "Chassis distance/angle action is not mapped for the direct S1 Wi-Fi protocol"
        )

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

    def sub_position(self, cs: int = 0, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if int(cs) not in (0, 1):
            raise ValueError("cs must be 0 or 1")
        return self._subscribe_odometry(
            "position",
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
            "velocity",
            callback,
            lambda v: (
                v.floats[2] if len(v.floats) > 2 else 0.0,
                v.floats[3] if len(v.floats) > 3 else 0.0,
                v.floats[4] if len(v.floats) > 4 else 0.0,
                v.floats[2] if len(v.floats) > 2 else 0.0,
                v.floats[3] if len(v.floats) > 3 else 0.0,
                v.floats[4] if len(v.floats) > 4 else 0.0,
            ),
            *args,
            **kw,
        )

    def sub_attitude(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        return self._subscribe_odometry(
            "attitude",
            callback,
            lambda v: (v.heading_like or 0.0, 0.0, 0.0),
            *args,
            **kw,
        )

    def sub_status(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._replace_subscription(
            "status",
            "stats",
            lambda value: callback(value, *args, **kw),
        )
        return True

    def unsub_position(self) -> bool:
        return self._remove_subscription("position")

    def unsub_velocity(self) -> bool:
        return self._remove_subscription("velocity")

    def unsub_attitude(self) -> bool:
        return self._remove_subscription("attitude")

    def unsub_status(self) -> bool:
        return self._remove_subscription("status")

    def start_calibration(self) -> bool:
        self._robot.send_duss(0x02, 0x03, 0x40, 0x03, 0xF9, bytes.fromhex("e4a3997d03"))
        return True

    def enter_calibration_measurement(self) -> bool:
        self._robot.send_duss(0x02, 0x03, 0x40, 0x03, 0xF9, bytes.fromhex("e4a3997d01"))
        return True

    def stop_wheels(self) -> bool:
        return self.drive_wheels(0, 0, 0, 0)

    def _subscribe_odometry(self, name, callback, projector, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._replace_subscription(
            name,
            "odometry",
            lambda value: callback(projector(value), *args, **kw),
        )
        return True

    def _replace_subscription(self, name: str, event: str, callback) -> None:  # noqa: ANN001
        self._remove_subscription(name)
        self._subscriptions[name] = (event, callback)
        self._robot.on(event, callback)

    def _remove_subscription(self, name: str) -> bool:
        item = self._subscriptions.pop(name, None)
        if item is None:
            return False
        event, callback = item
        return self._robot.off(event, callback)
