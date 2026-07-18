from __future__ import annotations


MIC_START_PAYLOAD = bytes.fromhex("00000001000500d2110000000000000000")
MIC_STOP_PAYLOAD = bytes.fromhex("0200000000000000000000000000000000")


class Audio:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._block_index = 0

    def request_rx(self) -> None:
        """Ask the robot to start sending microphone/audio frames."""
        self._robot.send_duss(0x02, 0x01, 0x40, 0x3F, 0x1E, b"\x01")

    def start_tx(self) -> None:
        """Start PC-to-robot audio session. Raw audio block helper is intentionally not high-level yet."""
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x5F, MIC_START_PAYLOAD)

    def stop_tx(self) -> None:
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x5F, MIC_STOP_PAYLOAD)

    def send_pcm_block(self, pcm: bytes) -> None:
        if not pcm:
            return
        self._robot.send_audio_block(pcm, self._block_index)
        self._block_index = (self._block_index + 1) & 0xFFFFFFFF
