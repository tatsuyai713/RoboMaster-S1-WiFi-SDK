from __future__ import annotations

from .action import ImmediateAction
from .unsupported import unsupported


class Servo:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def moveto(self, index: int = 0, angle: float = 0) -> ImmediateAction:
        return unsupported("servo")

    def drive_speed(self, index: int = 0, speed: float = 0) -> bool:
        return unsupported("servo")

    def pause(self, index: int = 0) -> bool:
        return unsupported("servo")

    def get_angle(self, index: int = 1) -> float | None:
        return unsupported("servo")

    def sub_servo_info(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return unsupported("servo")

    def unsub_servo_info(self) -> bool:
        return unsupported("servo")
