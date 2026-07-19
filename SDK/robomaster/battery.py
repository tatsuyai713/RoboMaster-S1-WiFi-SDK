from __future__ import annotations

from robomaster_s1_sdk.battery import Battery


class BatterySubject:
    def __init__(self):
        self._adc_value = 0
        self._temperature = 0
        self._current = 0
        self._percent = 0


__all__ = ["Battery", "BatterySubject"]
