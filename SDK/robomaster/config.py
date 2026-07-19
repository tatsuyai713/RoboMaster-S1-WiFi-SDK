from __future__ import annotations

DEFAULT_CONN_TYPE = "sta"
DEFAULT_PROTO_TYPE = "udp"
LOCAL_IP_STR = None
ROBOT_IP_STR = None
ROBOT_BROADCAST_PORT = 40927


class Config:
    def __init__(self, name: str):
        self.name = name
        self.video_stream_proto = "udp"
        self.audio_stream_proto = "udp"


ep_conf = Config("RoboMasterS1WiFiConfig")
