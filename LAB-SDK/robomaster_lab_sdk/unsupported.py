from __future__ import annotations

from .exceptions import UnsupportedError


def unsupported(feature: str):
    raise UnsupportedError(f"{feature} is not available on a stock RoboMaster S1")
