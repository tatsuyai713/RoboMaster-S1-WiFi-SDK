from __future__ import annotations

from robomaster_lab_sdk.ai_module import AiModule
from robomaster_lab_sdk.unsupported import unsupported


class TelloAI:
    def __init__(self, robot) -> None:  # noqa: ANN001
        unsupported("Tello AI")


__all__ = ["AiModule", "TelloAI"]
