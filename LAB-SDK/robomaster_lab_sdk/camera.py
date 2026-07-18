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
        return True

    def stop_video_stream(self) -> bool:
        return True

    def read_video_frame(self, timeout: float = 3.0) -> bytes | None:
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty:
            return None
