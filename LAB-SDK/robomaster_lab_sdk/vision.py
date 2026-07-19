from __future__ import annotations

from .unsupported import unsupported


class Vision:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def reset(self) -> None:
        return None

    def sub_detect_info(self, name, color=None, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        unsupported("vision.sub_detect_info result forwarding")

    def unsub_detect_info(self, name) -> bool:
        return self.disable_detection(name)

    def enable_detection(self, name: str = "marker") -> bool:
        return self._robot.bridge.call("vision", "enable_detection", name=name)

    def disable_detection(self, name: str = "marker") -> bool:
        return self._robot.bridge.call("vision", "disable_detection", name=name)

    def set_color(self, name: str = "line", color: str = "blue") -> bool:
        method = "marker_detection_color_set" if name == "marker" else "line_follow_color_set"
        return self._robot.bridge.call("vision", method, color=color)

    def set_marker_detection_distance(self, distance: float = 1.0) -> bool:
        return self._robot.bridge.call("vision", "set_marker_detection_distance", distance=float(distance))

    def detect_marker_and_aim(self, marker: str = "target") -> bool:
        return self._robot.bridge.call("vision", "detect_marker_and_aim", marker=marker)
