from __future__ import annotations

from robomaster_s1_sdk.gimbal import Gimbal
from robomaster_s1_sdk.action import ImmediateAction

COORDINATE_NED = 0
COORDINATE_CUR = 1
COORDINATE_CAR = 2
COORDINATE_PNED = 3
COORDINATE_YCPN = 4
COORDINATE_YCPO = 5


class GimbalMoveAction(ImmediateAction):
    pass


class GimbalRecenterAction(ImmediateAction):
    pass

__all__ = ["Gimbal", "GimbalMoveAction", "GimbalRecenterAction"]
