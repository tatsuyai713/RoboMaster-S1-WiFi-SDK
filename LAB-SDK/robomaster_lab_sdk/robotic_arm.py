from __future__ import annotations

from .action import ImmediateAction
from .unsupported import unsupported


class RoboticArm:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def reset(self) -> ImmediateAction:
        return unsupported("robotic arm")

    def recenter(self) -> ImmediateAction:
        return unsupported("robotic arm")

    def move(self, x: float = 0.0, y: float = 0.0) -> ImmediateAction:
        return unsupported("robotic arm")

    def moveto(self, x: float = 0.0, y: float = 0.0) -> ImmediateAction:
        return unsupported("robotic arm")

    def sub_position(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return unsupported("robotic arm")

    def unsub_position(self) -> bool:
        return unsupported("robotic arm")
