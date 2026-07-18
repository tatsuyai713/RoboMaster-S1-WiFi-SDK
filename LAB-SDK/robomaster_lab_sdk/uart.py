from __future__ import annotations


class Uart:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def serial_send_msg(self, msg: bytes | str) -> bool:
        return False

    def sub_serial_msg(self, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        return False

    def unsub_serial_msg(self) -> bool:
        return True
