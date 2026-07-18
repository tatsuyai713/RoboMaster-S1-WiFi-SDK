from __future__ import annotations

import queue


class Camera:
    RESOLUTION_720P = "720p"
    RESOLUTION_1080P = "1080p"

    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._video_frames: queue.Queue[bytes] = queue.Queue(maxsize=120)
        self._audio_frames: queue.Queue[bytes] = queue.Queue(maxsize=120)
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
        return True

    def stop_video_stream(self) -> bool:
        return True

    def read_video_frame(self, timeout: float = 3, strategy: str = "pipeline") -> bytes | None:
        return self._read_queue(self._video_frames, timeout, strategy)

    def read_cv2_image(self, timeout: float = 3, strategy: str = "pipeline"):
        raise NotImplementedError("Decoded cv2 image output is app-side; use read_video_frame() for H.264 bytes")

    def start_audio_stream(self) -> bool:
        self._robot.audio.request_rx()
        return True

    def stop_audio_stream(self) -> bool:
        return True

    def read_audio_frame(self, timeout: float = 1) -> bytes | None:
        return self._read_queue(self._audio_frames, timeout, "pipeline")

    def record_audio(self, save_file: str = "output.wav", seconds: int = 5, sample_rate: int = 48000) -> bool:
        raise NotImplementedError("Audio recording helper is not implemented yet")

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
