from __future__ import annotations


class AiModule:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def sub_ai_event(self, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_ai_event(self) -> bool:
        return True
