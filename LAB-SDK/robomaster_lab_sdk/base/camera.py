from __future__ import annotations

import queue
import time
import wave

from .audio import (
    MIC_CHANNELS,
    MIC_SAMPLE_RATE,
    MIC_SAMPLE_WIDTH_BYTES,
    OpusDecoder,
)


class Camera:
    RESOLUTION_720P = "720p"
    RESOLUTION_1080P = "1080p"

    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._liveview = None
        self._video_frames: queue.Queue[bytes] = queue.Queue(maxsize=120)
        self._audio_frames: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self._audio_decoder = OpusDecoder()
        self._audio_streaming = False
        self._robot.on("video", self._push_video)
        self._robot.on("audio_rx", self._push_audio)

    @property
    def video_stream_addr(self) -> tuple[str, int]:
        return (self._robot.robot_ip, 40921)

    @property
    def audio_stream_addr(self) -> tuple[str, int]:
        return (self._robot.robot_ip, 40922)

    def _push_video(self, frame: bytes) -> None:
        self._put_newest(self._video_frames, frame)

    def _push_audio(self, frame: bytes) -> None:
        self._put_newest(self._audio_frames, frame)

    @staticmethod
    def _put_newest(q: queue.Queue[bytes], item: bytes) -> None:
        try:
            q.put_nowait(item)
        except queue.Full:
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            q.put_nowait(item)

    def set_resolution(self, resolution: str) -> None:
        resolution = resolution.lower()
        if resolution in {"720", "720p", "720p/30fps"}:
            self._robot.settings.send_named_action("video_resolution_0403")
        elif resolution in {"1080", "1080p", "1080p/30fps"}:
            self._robot.settings.send_named_action("video_resolution_0a03")
        else:
            raise ValueError("resolution must be 720p or 1080p")

    def start_video_stream(self, display: bool = True, resolution: str = "720p") -> bool:
        self.set_resolution(resolution)
        if self._liveview is not None:
            return self._liveview.start_video_stream(display=display)
        return True

    def stop_video_stream(self) -> bool:
        if self._liveview is not None:
            return self._liveview.stop_video_stream()
        return True

    def read_video_frame(self, timeout: float = 3, strategy: str = "pipeline") -> bytes | None:
        return self._read_queue(self._video_frames, timeout, strategy)

    def read_cv2_image(self, timeout: float = 3, strategy: str = "pipeline"):
        raise NotImplementedError("Decoded cv2 image output is app-side; use read_video_frame() for H.264 bytes")

    def start_audio_stream(self) -> bool:
        while True:
            try:
                self._audio_frames.get_nowait()
            except queue.Empty:
                break
        if not self._robot.audio.request_rx():
            return False
        self._audio_streaming = True
        if self._liveview is not None:
            return self._liveview.start_audio_stream()
        return True

    def stop_audio_stream(self) -> bool:
        self._audio_streaming = False
        if self._liveview is not None:
            return self._liveview.stop_audio_stream()
        return True

    def read_audio_opus(self, timeout: float = 1) -> bytes | None:
        """Return one compressed Opus packet from the S1 microphone."""
        return self._read_queue(self._audio_frames, timeout, "pipeline")

    def decode_audio_opus(self, packet: bytes) -> bytes | None:
        return self._audio_decoder.decode(packet)

    def read_audio_frame(self, timeout: float = 1) -> bytes | None:
        """Return decoded 48 kHz mono signed-16 PCM."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            remaining = deadline - time.monotonic()
            packet = self.read_audio_opus(timeout=max(0.0, remaining))
            if packet is None:
                return None
            pcm = self.decode_audio_opus(packet)
            if pcm:
                return pcm
            if remaining <= 0.0:
                return None

    def record_audio(self, save_file: str = "output.wav", seconds: int = 5, sample_rate: int = 48000) -> bool:
        if int(sample_rate) != MIC_SAMPLE_RATE:
            raise ValueError(
                f"sample_rate must be {MIC_SAMPLE_RATE} for S1 audio"
            )
        duration = max(0.0, float(seconds))
        was_streaming = self._audio_streaming
        if not was_streaming and not self.start_audio_stream():
            return False
        wrote_audio = False
        deadline = time.monotonic() + duration
        try:
            with wave.open(str(save_file), "wb") as output:
                output.setnchannels(MIC_CHANNELS)
                output.setsampwidth(MIC_SAMPLE_WIDTH_BYTES)
                output.setframerate(MIC_SAMPLE_RATE)
                while time.monotonic() < deadline:
                    pcm = self.read_audio_frame(
                        timeout=min(0.2, deadline - time.monotonic())
                    )
                    if pcm:
                        output.writeframesraw(pcm)
                        wrote_audio = True
        finally:
            if not was_streaming:
                self.stop_audio_stream()
        return wrote_audio

    def take_photo(self) -> bool:
        raise NotImplementedError("take_photo is not mapped for the S1 Wi-Fi protocol yet")

    def format_sd_card(self) -> bool:
        self._robot.send_duss(0x02, 0x01, 0x40, 0x02, 0x72, b"\x00")
        return True

    @staticmethod
    def _read_queue(q: queue.Queue[bytes], timeout: float, strategy: str) -> bytes | None:
        if strategy == "newest":
            newest = None
            end = max(0.0, timeout)
            try:
                newest = q.get(timeout=end)
            except queue.Empty:
                return None
            while True:
                try:
                    newest = q.get_nowait()
                except queue.Empty:
                    return newest
        try:
            return q.get(timeout=max(0.0, timeout))
        except queue.Empty:
            return None

    def set_antiflicker(self, hz: int) -> None:
        if int(hz) == 50:
            self._robot.settings.send_named_action("video_antiflicker_50")
        elif int(hz) == 60:
            self._robot.settings.send_named_action("video_antiflicker_60")
        else:
            raise ValueError("antiflicker must be 50 or 60")

    def set_3d_quality(self, quality: str) -> None:
        values = {
            "low": "video_3d_low",
            "medium": "video_3d_medium",
            "high": "video_3d_high",
        }
        key = quality.lower()
        if key not in values:
            raise ValueError("quality must be low, medium, or high")
        self._robot.settings.send_named_action(values[key])

    def _set_zoom(self, value: float) -> bool:
        # Keep the official private hook import-compatible for robomaster_ros.
        # No captured S1 zoom command is available, so do not claim success.
        return False
