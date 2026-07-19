from __future__ import annotations

import queue


class Camera:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._frames: queue.Queue[bytes] = queue.Queue(maxsize=120)
        self._robot.on("video", self._on_video)

    def _on_video(self, payload: bytes) -> None:
        try:
            self._frames.put_nowait(payload)
        except queue.Full:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self._frames.put_nowait(payload)
            except queue.Full:
                pass

    def start_video_stream(self, display: bool = True, resolution: str = "720p") -> bool:
        return self._robot.base.camera.start_video_stream(display=display, resolution=resolution)

    def stop_video_stream(self) -> bool:
        return self._robot.base.camera.stop_video_stream()

    def read_cv2_image(self, timeout: float = 3.0, strategy: str = "pipeline"):
        return self._robot.base.camera.read_cv2_image(timeout=timeout, strategy=strategy)

    def start_audio_stream(self) -> bool:
        return self._robot.base.camera.start_audio_stream()

    def stop_audio_stream(self) -> bool:
        return self._robot.base.camera.stop_audio_stream()

    def read_audio_frame(self, timeout: float = 1.0) -> bytes | None:
        return self._robot.base.camera.read_audio_frame(timeout=timeout)

    def read_audio_opus(self, timeout: float = 1.0) -> bytes | None:
        return self._robot.base.camera.read_audio_opus(timeout=timeout)

    def decode_audio_opus(self, packet: bytes) -> bytes | None:
        return self._robot.base.camera.decode_audio_opus(packet)

    def record_audio(self, save_file: str = "output.wav", seconds: int = 5, sample_rate: int = 48000) -> bool:
        return self._robot.base.camera.record_audio(save_file=save_file, seconds=seconds, sample_rate=sample_rate)

    def take_photo(self) -> bool:
        return self._robot.base.camera.take_photo()

    def read_video_frame(self, timeout: float = 3.0, strategy: str = "pipeline") -> bytes | None:
        return self._robot.base.camera.read_video_frame(timeout=timeout, strategy=strategy)
