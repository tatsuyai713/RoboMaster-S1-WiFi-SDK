from __future__ import annotations


class Media:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def play_sound(self, sound_id=0) -> bool:  # noqa: ANN001
        return self._robot.bridge.call("media", "play_sound", sound_id=sound_id)

    def capture(self) -> bool:
        return self._robot.bridge.call("media", "capture")

    def zoom_value_update(self, value: float = 1.0) -> bool:
        return self._robot.bridge.call("media", "zoom_value_update", value=float(value))

    def exposure_value_update(self, value: str = "medium") -> bool:
        return self._robot.bridge.call("media", "exposure_value_update", value=str(value))

    def record(self, enable: bool = True) -> bool:
        return self._robot.bridge.call("media", "record", enable=bool(enable))

    def enable_sound_recognition(self, name: str = "applause") -> bool:
        return self._robot.bridge.call("media", "enable_sound_recognition", name=name)

    def disable_sound_recognition(self, name: str = "applause") -> bool:
        return self._robot.bridge.call("media", "disable_sound_recognition", name=name)
