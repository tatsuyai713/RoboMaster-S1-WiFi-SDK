from __future__ import annotations

from robomaster_lab_sdk.gimbal import Gimbal, GimbalMoveAction, GimbalRecenterAction

COORDINATE_NED = 0
COORDINATE_CUR = 1
COORDINATE_CAR = 2
COORDINATE_PNED = 3
COORDINATE_YCPN = 4
COORDINATE_YCPO = 5

__all__ = ["Gimbal", "GimbalMoveAction"]
