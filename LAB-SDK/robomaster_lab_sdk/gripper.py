from __future__ import annotations


class Gripper:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def open(self, power: int = 50) -> bool:
        return False

    def close(self, power: int = 50) -> bool:
        return False

    def pause(self) -> bool:
        return False

    def sub_status(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_status(self) -> bool:
        return True
