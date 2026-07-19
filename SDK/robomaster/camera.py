from __future__ import annotations

from robomaster_s1_sdk.camera import Camera

STREAM_720P = "720p"
STREAM_1080P = "1080p"
STREAM_360P = "360p"
STREAM_540P = "540p"

EPCamera = Camera

__all__ = [
    "Camera",
    "EPCamera",
    "STREAM_360P",
    "STREAM_540P",
    "STREAM_720P",
    "STREAM_1080P",
]
