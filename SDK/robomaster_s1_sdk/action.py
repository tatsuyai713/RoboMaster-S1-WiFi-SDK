from __future__ import annotations

import time


class Action:
    """Small official-SDK-style action object.

    The stock EP SDK returns action objects for task-style movement. Most S1
    Wi-Fi commands here are immediate, so the action is completed when created.
    """

    def __init__(self, completed: bool = True) -> None:
        self._completed = completed

    def wait_for_completed(self, timeout: float | None = None) -> bool:
        if self._completed:
            return True
        if timeout:
            time.sleep(max(0.0, timeout))
        return self._completed


class ImmediateAction(Action):
    def __init__(self) -> None:
        super().__init__(completed=True)


class TextAction(ImmediateAction):
    pass
