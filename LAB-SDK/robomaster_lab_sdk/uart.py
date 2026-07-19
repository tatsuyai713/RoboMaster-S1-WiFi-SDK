from __future__ import annotations

from .unsupported import unsupported


class Uart:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def start(self) -> bool:
        return unsupported("UART")

    def stop(self) -> bool:
        return unsupported("UART")

    def serial_read_data(self, msg_len: int):
        return unsupported("UART")

    def serial_param_set(
        self,
        baud_rate: int = 0,
        data_bit: int = 1,
        odd_even: int = 0,
        stop_bit: int = 0,
        rx_en: int = 1,
        tx_en: int = 1,
        rx_size: int = 50,
        tx_size: int = 50,
    ) -> bool:
        return unsupported("UART")

    def serial_send_msg(self, msg_buf) -> bool:  # noqa: ANN001
        return unsupported("UART")

    def serial_process_decode(self, msg):  # noqa: ANN001
        return unsupported("UART")

    def serial_process_exec(self):
        return unsupported("UART")

    def sub_serial_msg(self, callback=None, *args) -> bool:  # noqa: ANN001
        return unsupported("UART")

    def unsub_serial_msg(self) -> bool:
        return unsupported("UART")
