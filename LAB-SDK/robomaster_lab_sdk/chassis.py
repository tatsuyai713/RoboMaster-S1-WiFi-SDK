from __future__ import annotations

from .action import ImmediateAction


class Chassis:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def drive_speed(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, timeout: float | None = None) -> bool:
        self._robot.update_command(
            x=float(x) / self._robot.config.max_chassis_speed,
            y=float(y) / self._robot.config.max_chassis_speed,
            z=float(z) / self._robot.config.max_chassis_yaw_speed,
        )
        return True

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, xy_speed: float = 0.5, z_speed: float = 30) -> ImmediateAction:
        if x:
            self._robot.bridge.call("chassis", "move_with_distance", direction="forward" if x > 0 else "backward", distance=abs(float(x)))
        if y:
            self._robot.bridge.call("chassis", "move_with_distance", direction="right" if y > 0 else "left", distance=abs(float(y)))
        if z:
            self._robot.bridge.call("chassis", "rotate_with_degree", direction="clockwise" if z > 0 else "anticlockwise", degree=abs(float(z)))
        return ImmediateAction()

    def stop(self) -> None:
        self._robot.update_command(x=0.0, y=0.0, z=0.0)
        self._robot.send_once(x=0.0, y=0.0, z=0.0)

    def drive_wheels(self, w1: int = 0, w2: int = 0, w3: int = 0, w4: int = 0, timeout: float | None = None) -> bool:
        self._robot.bridge.call("chassis", "set_wheel_speed", w1=int(w1), w2=int(w2), w3=int(w3), w4=int(w4))
        return True

    def set_trans_speed(self, speed: float = 0.5) -> bool:
        self._robot.bridge.call("chassis", "set_trans_speed", speed=float(speed))
        return True

    def set_rotate_speed(self, speed: float = 30) -> bool:
        self._robot.bridge.call("chassis", "set_rotate_speed", speed=float(speed))
        return True

    def set_follow_gimbal_offset(self, offset: float = 0.0) -> bool:
        self._robot.bridge.call("chassis", "set_follow_gimbal_offset", offset=float(offset))
        return True

    def move_with_time(self, direction: str = "forward", time: float = 1.0) -> ImmediateAction:
        self._robot.bridge.call("chassis", "move_with_time", direction=direction, time=float(time))
        return ImmediateAction()

    def move_with_distance(self, direction: str = "forward", distance: float = 1.0) -> ImmediateAction:
        self._robot.bridge.call("chassis", "move_with_distance", direction=direction, distance=float(distance))
        return ImmediateAction()

    def rotate_with_degree(self, direction: str = "clockwise", degree: float = 90.0) -> ImmediateAction:
        self._robot.bridge.call("chassis", "rotate_with_degree", direction=direction, degree=float(degree))
        return ImmediateAction()

    def rotate_with_speed(self, direction: str = "clockwise", speed: float = 30.0) -> bool:
        self._robot.bridge.call("chassis", "rotate_with_speed", direction=direction, speed=float(speed))
        return True

    def forward(self) -> None:
        self.drive_speed(x=self._robot.config.max_chassis_speed)

    def backward(self) -> None:
        self.drive_speed(x=-self._robot.config.max_chassis_speed)

    def left(self) -> None:
        self.drive_speed(y=-self._robot.config.max_chassis_speed)

    def right(self) -> None:
        self.drive_speed(y=self._robot.config.max_chassis_speed)

    def sub_position(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("position", lambda value: callback(value, *args, **kwargs))
        return True

    def sub_velocity(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("velocity", lambda value: callback(value, *args, **kwargs))
        return True

    def sub_attitude(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("attitude", lambda value: callback(value, *args, **kwargs))
        return True

    def sub_status(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("telemetry", lambda value: callback(value, *args, **kwargs))
        return True

    def unsub_position(self) -> bool:
        return True

    def unsub_velocity(self) -> bool:
        return True

    def unsub_attitude(self) -> bool:
        return True

    def unsub_status(self) -> bool:
        return True
