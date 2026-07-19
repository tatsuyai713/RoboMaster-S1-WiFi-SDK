from __future__ import annotations

from .unsupported import unsupported


class Gripper:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def reset(self) -> bool:
        return unsupported("gripper")

    def open(self, power: int = 50) -> bool:
        return unsupported("gripper")

    def close(self, power: int = 50) -> bool:
        return unsupported("gripper")

    def pause(self) -> bool:
        return unsupported("gripper")

    def sub_status(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return unsupported("gripper")

    def unsub_status(self) -> bool:
        return unsupported("gripper")
