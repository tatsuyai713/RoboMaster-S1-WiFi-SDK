from __future__ import annotations

from robomaster_lab_sdk.camera import Camera as _LabCamera
from robomaster_lab_sdk.unsupported import unsupported

STREAM_360P = "360p"
STREAM_540P = "540p"
STREAM_720P = "720p"


class Camera(_LabCamera):
    def start_video_stream(self, display=True):
        return super().start_video_stream(display=display)


class EPCamera(_LabCamera):
    def __init__(self, robot) -> None:  # noqa: ANN001
        super().__init__(robot)
        self._liveview = None

    def start_video_stream(self, display=True, resolution="720p"):
        accepted = super().start_video_stream(
            display=display, resolution=resolution
        )
        if accepted and self._liveview is not None:
            return self._liveview.start_video_stream(display=display)
        return accepted

    def stop_video_stream(self):
        liveview_result = True
        if self._liveview is not None:
            liveview_result = self._liveview.stop_video_stream()
        return super().stop_video_stream() and liveview_result

    def start_audio_stream(self):
        accepted = super().start_audio_stream()
        if accepted and self._liveview is not None:
            return self._liveview.start_audio_stream()
        return accepted

    def stop_audio_stream(self):
        liveview_result = True
        if self._liveview is not None:
            liveview_result = self._liveview.stop_audio_stream()
        return super().stop_audio_stream() and liveview_result

    def _set_zoom(self, value):
        return self._robot.media.zoom_value_update(float(value))


class TelloCamera(Camera):
    def __init__(self, robot) -> None:  # noqa: ANN001
        unsupported("Tello camera")


__all__ = ["Camera", "EPCamera", "TelloCamera", "STREAM_360P", "STREAM_540P", "STREAM_720P"]
