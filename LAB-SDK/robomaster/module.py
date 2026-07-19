from __future__ import annotations

from robomaster_lab_sdk.unsupported import unsupported


class Module:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    @property
    def client(self):
        return getattr(self._robot, "client", None)

    def reset(self):
        unsupported("low-level module.reset")

    def start(self):
        unsupported("low-level module.start")

    def stop(self):
        unsupported("low-level module.stop")

    def get_version(self):
        unsupported("low-level module.get_version")


__all__ = ["Module"]
