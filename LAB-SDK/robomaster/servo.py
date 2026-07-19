from __future__ import annotations

from robomaster_lab_sdk.servo import Servo
from robomaster_lab_sdk.action import ImmediateAction


class ServoSetAngleAction(ImmediateAction):
    def __init__(self, index=0, angle=0, **kw) -> None:  # noqa: ANN003
        super().__init__(**kw)
        self.index = index
        self.angle = angle


__all__ = ["Servo"]
