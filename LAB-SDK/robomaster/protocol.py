from __future__ import annotations

from robomaster_lab_sdk.unsupported import unsupported

RM_SDK_FIRST_SEQ_ID = 10000
RM_SDK_LAST_SEQ_ID = 20000
DUSS_MB_ACK_NO = 0
DUSS_MB_ACK_NOW = 1
DUSS_MB_ACK_FINISH = 2
DUSS_MB_ENC_NO = 0
DUSS_MB_ENC_AES128 = 1
DUSS_MB_ENC_CUSTOM = 2
DUSS_MB_TYPE_REQ = 0
DUSS_MB_TYPE_PUSH = 1


class ProtoData:
    _cmdset = None
    _cmdid = None

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    @property
    def cmdset(self):
        return self._cmdset

    @property
    def cmdid(self):
        return self._cmdid

    @property
    def cmdkey(self):
        if self._cmdset is None or self._cmdid is None:
            return None
        return int(self._cmdset) * 256 + int(self._cmdid)


class ProtoSdkHeartBeat(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xD5


class ProtoSetSystemLed(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0x33


class ProtoChassisSetWorkMode(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0x19


class ProtoGripperCtrl(ProtoData):
    _cmdset = 0x33
    _cmdid = 0x11


class ProtoPlaySound(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xB3


class ProtoSoundPush(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xB4


def host2byte(host, index):
    return (int(host) << 5) | int(index)


def byte2host(value):
    return int(value) >> 5, int(value) & 0x1F


class Msg:
    def __init__(self, sender=0, receiver=0, proto=None):
        self._sender = sender
        self._receiver = receiver
        self._proto = proto

    @property
    def cmdset(self):
        return getattr(self._proto, "_cmdset", None)

    @property
    def cmdid(self):
        return getattr(self._proto, "_cmdid", None)

    @property
    def is_ack(self):
        return False

    @property
    def receiver(self):
        return self._receiver

    @property
    def sender(self):
        return self._sender

    def pack(self, is_ack=False):
        unsupported("official EP protocol.Msg packing")

    def unpack_protocol(self):
        unsupported("official EP protocol.Msg decoding")

    def get_proto(self):
        return self._proto


class TextMsg:
    def __init__(self, proto=None):
        self._proto = proto

    def pack(self):
        unsupported("Tello TextMsg packing")

    def unpack_protocol(self):
        unsupported("Tello TextMsg decoding")

    def get_proto(self):
        return self._proto

    def get_buf(self):
        unsupported("Tello TextMsg buffer")


__all__ = ["Msg", "TextMsg"]
