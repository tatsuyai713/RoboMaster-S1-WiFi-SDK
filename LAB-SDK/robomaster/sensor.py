from __future__ import annotations

from robomaster_lab_sdk.sensor import DistanceSensor, Sensor
from robomaster_lab_sdk.sensor_adaptor import SensorAdaptor
from robomaster_lab_sdk.unsupported import unsupported


class TelloDistanceSensor:
    def __init__(self, robot) -> None:  # noqa: ANN001
        unsupported("Tello distance sensor")


class TofSubject:
    def __init__(self):
        self._cmd_id = [0, 0, 0, 0]
        self._direct = [0, 0, 0, 0]
        self._flag = [0, 0, 0, 0]
        self._distance = [0, 0, 0, 0]


__all__ = ["DistanceSensor", "SensorAdaptor", "TofSubject"]
