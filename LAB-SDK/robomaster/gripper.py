from __future__ import annotations

from robomaster_lab_sdk.gripper import Gripper


class GripperSubject:
    def __init__(self):
        self._status = 0


__all__ = ["Gripper", "GripperSubject"]
