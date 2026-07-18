from __future__ import annotations


class Battery:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def get_battery(self) -> int | None:
        stats = getattr(self._robot, "_last_stats", None)
        return None if stats is None else stats.battery_percent

    def sub_battery_info(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False

        def _call(stats):
            if stats.battery_percent is not None:
                callback(stats.battery_percent, *args, **kw)

        self._robot.on("stats", _call)
        return True

    def unsub_battery_info(self) -> bool:
        return True
