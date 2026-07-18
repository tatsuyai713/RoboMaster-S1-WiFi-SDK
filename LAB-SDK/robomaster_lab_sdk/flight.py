from __future__ import annotations


class Flight:
    def __init__(self, robot=None) -> None:  # noqa: ANN001
        self._robot = robot

    def __getattr__(self, name: str):  # noqa: ANN001
        def _unsupported(*args, **kwargs):  # noqa: ANN001
            return False

        return _unsupported
