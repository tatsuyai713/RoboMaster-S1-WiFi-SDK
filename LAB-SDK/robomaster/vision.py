from __future__ import annotations

from robomaster_lab_sdk.vision import Vision

PERSON = "person"
GESTURE = "gesture"
LINE = "line"
MARKER = "marker"
ROBOT = "robot"


class VisionPushEvent:
    def __init__(self):
        self._type = 0
        self._status = 0
        self._rect_info = []


__all__ = [
    "Vision",
    "VisionPushEvent",
    "PERSON",
    "GESTURE",
    "LINE",
    "MARKER",
    "ROBOT",
]
