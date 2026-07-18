from __future__ import annotations


class Battery:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def get_battery(self) -> int | None:
        return self._robot.base.get_battery()

    def sub_battery_info(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False

        def _call(value):  # noqa: ANN001
            battery = None
            if hasattr(value, "battery_percent"):
                battery = value.battery_percent
            elif isinstance(value, dict):
                battery = value.get("battery_percent") or value.get("battery")
            if battery is None:
                battery = self.get_battery()
            if battery is not None:
                callback(battery, *args, **kwargs)

        self._robot.on("stats", _call)
        self._robot.on("telemetry", _call)
        return True

    def unsub_battery_info(self) -> bool:
        return True
