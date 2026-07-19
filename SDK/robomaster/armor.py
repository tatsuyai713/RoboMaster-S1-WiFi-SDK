from __future__ import annotations

from robomaster_s1_sdk.armor import Armor

HIT_TYPE_WATER_ATTACK = 0
HIT_TYPE_IR_ATTACK = 1


class ArmorHitEvent:
    def __init__(self):
        self._armor_id = 0
        self._type = HIT_TYPE_WATER_ATTACK
        self._mic_value = 0


__all__ = ["Armor", "ArmorHitEvent"]
