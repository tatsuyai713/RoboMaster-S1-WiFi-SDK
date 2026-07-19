from __future__ import annotations

from .unsupported import unsupported


class AiModule:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def init_ai_module(self) -> bool:
        return unsupported("AI module")

    def sub_ai_event(self, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return unsupported("AI module")

    def unsub_ai_event(self) -> bool:
        return unsupported("AI module")
