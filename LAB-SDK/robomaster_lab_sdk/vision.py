from __future__ import annotations


class Vision:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def sub_detect_info(self, name: str = "marker", callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_detect_info(self, name: str = "marker") -> bool:
        return True

    def enable_detection(self, name: str = "marker") -> bool:
        self._robot.bridge.call("vision", "enable_detection", name=name)
        return True

    def disable_detection(self, name: str = "marker") -> bool:
        self._robot.bridge.call("vision", "disable_detection", name=name)
        return True

    def set_color(self, name: str = "line", color: str = "blue") -> bool:
        method = "marker_detection_color_set" if name == "marker" else "line_follow_color_set"
        self._robot.bridge.call("vision", method, color=color)
        return True

    def set_marker_detection_distance(self, distance: float = 1.0) -> bool:
        self._robot.bridge.call("vision", "set_marker_detection_distance", distance=float(distance))
        return True

    def detect_marker_and_aim(self, color: str = "blue") -> bool:
        self._robot.bridge.call("vision", "detect_marker_and_aim", color=color)
        return True
