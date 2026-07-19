from __future__ import annotations

from .subscription import rate_limited_callback


class Battery:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._callback = None

    def get_battery(self) -> int | None:
        return self._robot.base.get_battery()

    def sub_battery_info(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
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
                # The official callback is (adc_mV, temperature_dC,
                # current_mA, percent).  Stock S1 Lab exposes percent only.
                callback((0, 0, 0, int(battery)), *args, **kw)

        self.unsub_battery_info()
        self._callback = rate_limited_callback(freq, _call)
        self._robot.on("stats", self._callback)
        self._robot.on("telemetry", self._callback)
        return True

    def unsub_battery_info(self) -> bool:
        if self._callback is None:
            return False
        callback = self._callback
        self._callback = None
        removed_stats = self._robot.off("stats", callback)
        removed_telemetry = self._robot.off("telemetry", callback)
        return removed_stats or removed_telemetry
