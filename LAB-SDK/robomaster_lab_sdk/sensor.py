from __future__ import annotations

from .unsupported import unsupported


class DistanceSensor:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def sub_distance(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("sensor.sub_distance result forwarding")

    def enable_measure(self, sensor_id: int = 1) -> bool:
        return self._robot.bridge.call("sensor", "enable_measure", sensor_id=int(sensor_id))

    def disable_measure(self, sensor_id: int = 1) -> bool:
        return self._robot.bridge.call("sensor", "disable_measure", sensor_id=int(sensor_id))

    def unsub_distance(self) -> bool:
        unsupported("sensor.unsub_distance result forwarding")


class Sensor(DistanceSensor):
    pass
