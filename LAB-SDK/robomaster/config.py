from __future__ import annotations

DEFAULT_CONN_TYPE = "ap"
DEFAULT_PROTO_TYPE = "udp"
LOCAL_IP_STR = None
ROBOT_IP_STR = None

ROBOT_SDK_PORT_MIN = 10100
ROBOT_SDK_PORT_MAX = 10500
ROBOT_DEVICE_PORT = 20020
ROBOT_PROXY_PORT = 30030
ROBOT_BROADCAST_PORT = 40927
ROBOT_SN_LEN = 14

ROBOT_DEFAULT_RNDIS_ADDR = ("192.168.42.2", ROBOT_DEVICE_PORT)
ROBOT_DEFAULT_WIFI_ADDR = ("192.168.2.1", ROBOT_DEVICE_PORT)
ROBOT_DEFAULT_LOCAL_RNDIS_ADDR = ("192.168.42.3", ROBOT_SDK_PORT_MIN)
ROBOT_DEFAULT_LOCAL_WIFI_ADDR = ("192.168.2.23", ROBOT_SDK_PORT_MIN)


class Config:
    def __init__(self, name):
        self._name = name
        self._product = "Unknown"
        self._cmd_addr = None
        self._cmd_proto = "v1"
        self._sdk_addr = None
        self._video_stream_addr = None
        self._video_stream_port = None
        self._video_stream_proto = "tcp"
        self._audio_stream_addr = None
        self._audio_stream_port = None
        self._audio_stream_proto = "tcp"

    @property
    def default_cmd_addr_port(self):
        return self.default_cmd_addr[1]

    product = property(lambda self: self._product, lambda self, value: setattr(self, "_product", value))
    default_robot_addr = property(lambda self: self._cmd_addr, lambda self, value: setattr(self, "_cmd_addr", value))
    cmd_proto = property(lambda self: self._cmd_proto, lambda self, value: setattr(self, "_cmd_proto", value))
    default_cmd_addr = property(lambda self: self._cmd_addr, lambda self, value: setattr(self, "_cmd_addr", value))
    default_sdk_addr = property(lambda self: self._sdk_addr, lambda self, value: setattr(self, "_sdk_addr", value))
    video_stream_addr = property(lambda self: self._video_stream_addr, lambda self, value: setattr(self, "_video_stream_addr", value))
    video_stream_port = property(lambda self: self._video_stream_port, lambda self, value: setattr(self, "_video_stream_port", value))
    video_stream_proto = property(lambda self: self._video_stream_proto, lambda self, value: setattr(self, "_video_stream_proto", value))
    audio_stream_addr = property(lambda self: self._audio_stream_addr, lambda self, value: setattr(self, "_audio_stream_addr", value))
    audio_stream_port = property(lambda self: self._audio_stream_port, lambda self, value: setattr(self, "_audio_stream_port", value))
    audio_stream_proto = property(lambda self: self._audio_stream_proto, lambda self, value: setattr(self, "_audio_stream_proto", value))


te_conf = Config("TelloEduConfig")
te_conf.product = "TelloEdu"
te_conf.default_cmd_addr = ("192.168.10.1", 8889)
te_conf.cmd_proto = "text"
te_conf.default_sdk_addr = ("0.0.0.0", 8890)
te_conf.video_stream_addr = ("0.0.0.0", 11111)
te_conf.video_stream_proto = "udp"

ep_conf = Config("RoboMasterEPConfig")
ep_conf.product = "RoboMasterEP"
ep_conf.video_stream_port = 40921
ep_conf.audio_stream_port = 40922

__all__ = ["LOCAL_IP_STR", "ROBOT_IP_STR", "DEFAULT_PROTO_TYPE"]
