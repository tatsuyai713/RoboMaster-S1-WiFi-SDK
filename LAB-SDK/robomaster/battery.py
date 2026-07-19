from __future__ import annotations

from robomaster_lab_sdk.battery import Battery
from robomaster_lab_sdk.unsupported import unsupported


class BatterySubject:
    """Compatibility container used by robomaster_ros monkey patches."""

    def __init__(self):
        self._adc_value = 0
        self._temperature = 0
        self._current = 0
        self._percent = 0


class TelloBattery:
    def __init__(self, robot) -> None:  # noqa: ANN001
        unsupported("Tello battery")


__all__ = ["Battery", "BatterySubject", "TelloBattery"]
