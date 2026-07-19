from __future__ import annotations

from robomaster_lab_sdk.armor import Armor

HIT_TYPE_WATER_ATTACK = 0
HIT_TYPE_IR_ATTACK = 1
COMP_TOP_LEFT = "top_left"
COMP_TOP_RIGHT = "top_right"
COMP_BOTTOM_LEFT = "bottom_left"
COMP_BOTTOM_RIGHT = "bottom_right"
COMP_BOTTOM_FRONT = "bottom_front"
COMP_BOTTOM_BACK = "bottom_back"
COMP_BOTTOM_ALL = "bottom_all"
COMP_TOP_ALL = "top_all"
COMP_ALL = "all"


class ArmorHitEvent:
    def __init__(self):
        self._armor_id = 0
        self._type = HIT_TYPE_WATER_ATTACK
        self._mic_value = 0


__all__ = ["Armor", "ArmorHitEvent"]
