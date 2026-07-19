from __future__ import annotations

from robomaster_lab_sdk.robotic_arm import RoboticArm
from robomaster_lab_sdk.action import ImmediateAction


class RoboticArmMoveAction(ImmediateAction):
    def __init__(self, x=0, y=0, z=0, mode=0, **kw) -> None:  # noqa: ANN003
        super().__init__(**kw)
        self.x = x
        self.y = y
        self.z = z
        self.mode = mode


__all__ = ["RoboticArm"]
