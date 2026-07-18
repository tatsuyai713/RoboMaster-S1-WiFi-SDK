from __future__ import annotations

from .action import ImmediateAction


class Servo:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def moveto(self, index: int = 1, angle: float = 0.0) -> ImmediateAction:
        return ImmediateAction()

    def drive_speed(self, index: int = 1, speed: float = 0.0) -> bool:
        return False

    def pause(self, index: int = 1) -> bool:
        return False

    def get_angle(self, index: int = 1) -> float | None:
        return None

    def sub_servo_info(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_servo_info(self) -> bool:
        return True
