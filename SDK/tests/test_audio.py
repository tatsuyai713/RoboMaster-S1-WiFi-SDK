from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import wave

from robomaster_s1_sdk.audio import (
    MIC_SAMPLE_RATE,
    MIC_START_PAYLOAD,
    MIC_STOP_PAYLOAD,
    Audio,
    OpusDecoder,
)
from robomaster_s1_sdk.camera import Camera


class _Robot:
    def __init__(self) -> None:
        self.calls = []
        self.callbacks = {}
        self.audio = Audio(self)
        self.robot_ip = "192.0.2.1"

    def on(self, event, callback):  # noqa: ANN001
        self.callbacks.setdefault(event, []).append(callback)
        return callback

    def send_duss(
        self,
        sender,
        receiver,
        attr,
        cmdset,
        cmdid,
        payload=b"",
    ):  # noqa: ANN001
        self.calls.append(
            ("duss", sender, receiver, attr, cmdset, cmdid, payload)
        )
        return len(self.calls)

    def send_audio_block(self, pcm, index):  # noqa: ANN001
        self.calls.append(("pcm", index, bytes(pcm)))
        return len(self.calls)


class _Plane:
    def __bytes__(self) -> bytes:
        return b"\x01\x00\x02\x00padding"


class _Frame:
    samples = 2
    planes = [_Plane()]


class _Codec:
    @staticmethod
    def decode(packet):  # noqa: ANN001
        return [_Frame()]


class _Resampler:
    @staticmethod
    def resample(frame):  # noqa: ANN001
        return [frame]


class _Av:
    @staticmethod
    def Packet(payload):  # noqa: N802, ANN001
        return payload


class _Decoder:
    @staticmethod
    def decode(payload):  # noqa: ANN001
        return b"\x01\x00" if payload == b"opus" else None


class AudioTests(unittest.TestCase):
    def test_unified_rx_and_tx_commands_are_preserved(self) -> None:
        robot = _Robot()
        self.assertTrue(robot.audio.request_rx())
        self.assertEqual(robot.calls[-1][4:7], (0x3F, 0x1E, b"\x01"))

        self.assertTrue(robot.audio.start_tx())
        self.assertEqual(robot.calls[-1][4:7], (0x3F, 0x5F, MIC_START_PAYLOAD))
        self.assertTrue(robot.audio.send_pcm_block(b"\x01\x02"))
        self.assertEqual(robot.calls[-1], ("pcm", 0, b"\x01\x02"))
        self.assertTrue(robot.audio.stop_tx())
        self.assertEqual(robot.calls[-1][4:7], (0x3F, 0x5F, MIC_STOP_PAYLOAD))

    def test_opus_decoder_returns_48khz_mono_s16_bytes(self) -> None:
        decoder = object.__new__(OpusDecoder)
        decoder._av = _Av()
        decoder._codec = _Codec()
        decoder._resampler = _Resampler()
        self.assertEqual(decoder.decode(b"opus"), b"\x01\x00\x02\x00")

    def test_camera_exposes_opus_and_decoded_pcm(self) -> None:
        robot = _Robot()
        camera = Camera(robot)
        camera._audio_decoder = _Decoder()
        camera._push_audio(b"opus")
        self.assertEqual(camera.read_audio_frame(timeout=0), b"\x01\x00")
        camera._push_audio(b"opus")
        self.assertEqual(camera.read_audio_opus(timeout=0), b"opus")

    def test_record_audio_writes_a_valid_48khz_mono_wave(self) -> None:
        robot = _Robot()
        camera = Camera(robot)
        camera._audio_streaming = True
        frames = iter((b"\x01\x00" * 480, None))
        camera.read_audio_frame = lambda timeout=1: next(frames, None)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audio.wav"
            self.assertTrue(camera.record_audio(str(output), seconds=0.001))
            with wave.open(str(output), "rb") as recording:
                self.assertEqual(recording.getframerate(), MIC_SAMPLE_RATE)
                self.assertEqual(recording.getnchannels(), 1)
                self.assertEqual(recording.getsampwidth(), 2)

    def test_audio_file_returns_a_real_host_tracked_action(self) -> None:
        robot = _Robot()
        robot.audio._pcm_from_audio_file = lambda filename: iter(
            (b"\x00" * 960,)
        )
        action = robot.audio.play_file_action("sound.wav")
        self.assertTrue(action.wait_for_completed(timeout=1.0))
        self.assertTrue(action.has_succeeded)
        self.assertEqual(
            [call[0] for call in robot.calls],
            ["duss", "pcm", "duss"],
        )


if __name__ == "__main__":
    unittest.main()
