from __future__ import annotations

from .action import ImmediateAction


class RoboticArm:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def reset(self) -> ImmediateAction:
        return ImmediateAction()

    def recenter(self) -> ImmediateAction:
        return ImmediateAction()

    def move(self, x: float = 0.0, y: float = 0.0) -> ImmediateAction:
        return ImmediateAction()

    def moveto(self, x: float = 0.0, y: float = 0.0) -> ImmediateAction:
        return ImmediateAction()

    def sub_position(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_position(self) -> bool:
        return True
