from __future__ import annotations


class Media:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def play_sound(self, sound_id=0) -> bool:  # noqa: ANN001
        self._robot.bridge.call("media", "play_sound", sound_id=sound_id)
        return True

    def capture(self) -> bool:
        self._robot.bridge.call("media", "capture")
        return True

    def zoom_value_update(self, value: float = 1.0) -> bool:
        self._robot.bridge.call("media", "zoom_value_update", value=float(value))
        return True

    def exposure_value_update(self, value: float = 0.0) -> bool:
        self._robot.bridge.call("media", "exposure_value_update", value=float(value))
        return True

    def record(self, enable: bool = True) -> bool:
        self._robot.bridge.call("media", "record", enable=bool(enable))
        return True

    def enable_sound_recognition(self) -> bool:
        self._robot.bridge.call("media", "enable_sound_recognition")
        return True

    def disable_sound_recognition(self) -> bool:
        self._robot.bridge.call("media", "disable_sound_recognition")
        return True
