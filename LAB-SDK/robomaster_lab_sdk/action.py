from __future__ import annotations


class ImmediateAction:
    def wait_for_completed(self, timeout: float | None = None) -> bool:
        return True
