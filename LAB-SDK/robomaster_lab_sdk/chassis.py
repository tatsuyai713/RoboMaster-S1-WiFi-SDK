from __future__ import annotations

import threading

from .action import ImmediateAction
from .subscription import rate_limited_callback
from .unsupported import unsupported


class ChassisMoveAction(ImmediateAction):
    def __init__(self, x=0, y=0, z=0, spd_xy=0, spd_z=0, **kw) -> None:  # noqa: ANN003
        super().__init__(**kw)
        self.x = x
        self.y = y
        self.z = z
        self.spd_xy = spd_xy
        self.spd_z = spd_z


class Chassis:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._speed_timer: threading.Timer | None = None
        self._wheel_timer: threading.Timer | None = None
        self._subscription_callbacks = {}

    @staticmethod
    def _cancel_timer(timer: threading.Timer | None) -> None:
        if timer is not None:
            timer.cancel()

    def _arm_speed_timeout(self, timeout: float | None) -> None:
        self._cancel_timer(self._speed_timer)
        self._speed_timer = None
        if timeout is not None:
            self._speed_timer = threading.Timer(max(0.0, float(timeout)), self.stop)
            self._speed_timer.daemon = True
            self._speed_timer.start()

    def _arm_wheel_timeout(self, timeout: float | None) -> None:
        self._cancel_timer(self._wheel_timer)
        self._wheel_timer = None
        if timeout is not None:
            self._wheel_timer = threading.Timer(
                max(0.0, float(timeout)),
                lambda: self._robot.bridge.call(
                    "chassis", "set_wheel_speed", w1=0, w2=0, w3=0, w4=0
                ),
            )
            self._wheel_timer.daemon = True
            self._wheel_timer.start()

    def drive_speed(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, timeout: float | None = None) -> bool:
        accepted = self._robot.update_command(
            x=float(x) / self._robot.config.max_chassis_speed,
            y=float(y) / self._robot.config.max_chassis_speed,
            z=float(z) / self._robot.config.max_chassis_yaw_speed,
        )
        if accepted:
            self._arm_speed_timeout(timeout)
        return accepted

    def move(self, x: float = 0, y: float = 0, z: float = 0, xy_speed: float = 0.5, z_speed: float = 30) -> ImmediateAction:
        self._robot.update_command(x=0.0, y=0.0, z=0.0)
        self._robot.bridge.stop_chassis()
        accepted = self.set_trans_speed(xy_speed)
        accepted = self.set_rotate_speed(z_speed) and accepted
        if x:
            accepted = self._robot.bridge.call("chassis", "move_with_distance", direction="forward" if x > 0 else "backward", distance=abs(float(x))) and accepted
        if y:
            accepted = self._robot.bridge.call("chassis", "move_with_distance", direction="right" if y > 0 else "left", distance=abs(float(y))) and accepted
        if z:
            accepted = self._robot.bridge.call("chassis", "rotate_with_degree", direction="clockwise" if z > 0 else "anticlockwise", degree=abs(float(z))) and accepted
        return ChassisMoveAction(
            x=x,
            y=y,
            z=z,
            spd_xy=xy_speed,
            spd_z=z_speed,
            accepted=accepted,
        )

    def stop(self) -> None:
        self._cancel_timer(self._speed_timer)
        self._speed_timer = None
        self._robot.update_command(x=0.0, y=0.0, z=0.0)
        self._robot.bridge.stop_chassis()

    def drive_wheels(self, w1: int = 0, w2: int = 0, w3: int = 0, w4: int = 0, timeout: float | None = None) -> bool:
        self._robot.update_command(x=0.0, y=0.0, z=0.0)
        self._robot.bridge.stop_chassis()
        accepted = self._robot.bridge.call(
            "chassis", "set_wheel_speed", w1=int(w1), w2=int(w2), w3=int(w3), w4=int(w4)
        )
        if accepted:
            self._arm_wheel_timeout(timeout)
        return accepted

    def stick_overlay(self, fusion_mode: int = 0) -> bool:
        mode = int(fusion_mode)
        if mode not in (0, 1, 2):
            raise ValueError("fusion_mode must be 0, 1, or 2")
        return self._robot.bridge.call(
            "chassis",
            "disable_stick_overlay" if mode == 0 else "enable_stick_overlay",
            fusion_mode=mode,
        )

    def set_pwm_value(
        self,
        pwm1=None,
        pwm2=None,
        pwm3=None,
        pwm4=None,
        pwm5=None,
        pwm6=None,
    ) -> bool:
        accepted = True
        for index, value in enumerate((pwm1, pwm2, pwm3, pwm4, pwm5, pwm6), 1):
            if value is not None:
                accepted = self._robot.bridge.call(
                    "chassis", "set_pwm_value", pwm=index, value=float(value)
                ) and accepted
        return accepted

    def set_pwm_freq(
        self,
        pwm1=None,
        pwm2=None,
        pwm3=None,
        pwm4=None,
        pwm5=None,
        pwm6=None,
    ) -> bool:
        unsupported("chassis.set_pwm_freq")

    def set_trans_speed(self, speed: float = 0.5) -> bool:
        return self._robot.bridge.call("chassis", "set_trans_speed", speed=float(speed))

    def set_rotate_speed(self, speed: float = 30) -> bool:
        return self._robot.bridge.call("chassis", "set_rotate_speed", speed=float(speed))

    def set_follow_gimbal_offset(self, offset: float = 0.0) -> bool:
        return self._robot.bridge.call("chassis", "set_follow_gimbal_offset", offset=float(offset))

    def move_with_time(self, direction: str = "forward", time: float = 1.0) -> ImmediateAction:
        self.stop()
        return ImmediateAction(accepted=self._robot.bridge.call("chassis", "move_with_time", direction=direction, time=float(time)))

    def move_with_distance(self, direction: str = "forward", distance: float = 1.0) -> ImmediateAction:
        self.stop()
        return ImmediateAction(accepted=self._robot.bridge.call("chassis", "move_with_distance", direction=direction, distance=float(distance)))

    def rotate_with_degree(self, direction: str = "clockwise", degree: float = 90.0) -> ImmediateAction:
        self.stop()
        return ImmediateAction(accepted=self._robot.bridge.call("chassis", "rotate_with_degree", direction=direction, degree=float(degree)))

    def rotate_with_speed(self, direction: str = "clockwise", speed: float = 30.0) -> bool:
        return self._robot.bridge.call("chassis", "rotate_with_speed", direction=direction, speed=float(speed))

    def forward(self) -> None:
        self.drive_speed(x=self._robot.config.max_chassis_speed)

    def backward(self) -> None:
        self.drive_speed(x=-self._robot.config.max_chassis_speed)

    def left(self) -> None:
        self.drive_speed(y=-self._robot.config.max_chassis_speed)

    def right(self) -> None:
        self.drive_speed(y=self._robot.config.max_chassis_speed)

    def sub_position(self, cs: int = 0, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        if int(cs) not in (0, 1):
            raise ValueError("cs must be 0 or 1")
        origin = [None, None, None]

        def forward(value):  # noqa: ANN001
            output = list(value)
            if int(cs) == 0:
                for index, item in enumerate(output):
                    if item is not None and origin[index] is None:
                        origin[index] = item
                    if item is not None and origin[index] is not None:
                        output[index] = item - origin[index]
            callback(tuple(output), *args, **kw)

        self._replace_subscription(
            "position",
            rate_limited_callback(freq, forward),
            {"x", "y", "yaw"},
            freq,
        )
        return True

    def sub_velocity(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._replace_subscription(
            "velocity",
            rate_limited_callback(
                freq, lambda value: callback(value, *args, **kw)
            ),
            {"vx", "vy"},
            freq,
        )
        return True

    def sub_attitude(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._replace_subscription(
            "attitude",
            rate_limited_callback(
                freq, lambda value: callback(value, *args, **kw)
            ),
            {"yaw"},
            freq,
        )
        return True

    def sub_status(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("chassis.sub_status")

    def _replace_subscription(
        self,
        event: str,
        callback,
        fields: set[str],
        freq: int,
    ) -> None:  # noqa: ANN001
        previous = self._subscription_callbacks.get(event)
        if previous is not None:
            self._robot.off(event, previous)
        self._subscription_callbacks[event] = callback
        self._robot.on(event, callback)
        self._robot._set_telemetry_request(
            f"chassis:{event}",
            fields,
            int(freq),
        )

    def _remove_subscription(self, event: str) -> bool:
        callback = self._subscription_callbacks.pop(event, None)
        if callback is None:
            return False
        removed = self._robot.off(event, callback)
        self._robot._clear_telemetry_request(f"chassis:{event}")
        return removed

    def unsub_position(self) -> bool:
        return self._remove_subscription("position")

    def unsub_velocity(self) -> bool:
        return self._remove_subscription("velocity")

    def unsub_attitude(self) -> bool:
        return self._remove_subscription("attitude")

    def unsub_status(self) -> bool:
        unsupported("chassis.unsub_status")

    def sub_imu(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("chassis.sub_imu")

    def unsub_imu(self) -> bool:
        unsupported("chassis.unsub_imu")

    def sub_mode(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("chassis.sub_mode")

    def unsub_mode(self) -> bool:
        unsupported("chassis.unsub_mode")

    def sub_esc(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("chassis.sub_esc")

    def unsub_esc(self) -> bool:
        unsupported("chassis.unsub_esc")
