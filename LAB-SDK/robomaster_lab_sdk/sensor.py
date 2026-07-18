from __future__ import annotations


class DistanceSensor:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def sub_distance(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def enable_measure(self) -> bool:
        self._robot.bridge.call("sensor", "enable_measure")
        return True

    def disable_measure(self) -> bool:
        self._robot.bridge.call("sensor", "disable_measure")
        return True

    def unsub_distance(self) -> bool:
        self.disable_measure()
        return True


class Sensor(DistanceSensor):
    pass
