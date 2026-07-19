from __future__ import annotations

from .unsupported import unsupported


class SensorAdaptor:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def get_adc(self, id: int = 1, port: int = 1) -> int | None:
        return unsupported("sensor adaptor")

    def get_io(self, id: int = 1, port: int = 1) -> int | None:
        return unsupported("sensor adaptor")

    def get_pulse_period(self, id: int = 1, port: int = 1) -> int | None:
        return unsupported("sensor adaptor")

    def sub_adapter(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return unsupported("sensor adaptor")

    def unsub_adapter(self) -> bool:
        return unsupported("sensor adaptor")
