from __future__ import annotations

from robomaster_lab_sdk.led import LED as Led

LED = Led

COMP_TOP_LEFT = "top_left"
COMP_TOP_RIGHT = "top_right"
COMP_BOTTOM_LEFT = "bottom_left"
COMP_BOTTOM_RIGHT = "bottom_right"
COMP_BOTTOM_FRONT = "bottom_front"
COMP_BOTTOM_BACK = "bottom_back"
COMP_BOTTOM_ALL = "bottom_all"
COMP_TOP_ALL = "top_all"
COMP_ALL = "all"

EFFECT_ON = "on"
EFFECT_OFF = "off"
EFFECT_PULSE = "pulse"
EFFECT_FLASH = "flash"
EFFECT_BREATH = "breath"
EFFECT_SCROLLING = "scrolling"

__all__ = [
    "Led",
    "COMP_TOP_LEFT",
    "COMP_TOP_RIGHT",
    "COMP_BOTTOM_LEFT",
    "COMP_BOTTOM_RIGHT",
    "COMP_BOTTOM_FRONT",
    "COMP_BOTTOM_BACK",
    "COMP_BOTTOM_ALL",
    "COMP_TOP_ALL",
    "COMP_ALL",
    "EFFECT_ON",
    "EFFECT_OFF",
    "EFFECT_PULSE",
    "EFFECT_FLASH",
    "EFFECT_BREATH",
    "EFFECT_SCROLLING",
]
