from __future__ import annotations


class ProtoData:
    _cmdset = None
    _cmdid = None

    def __init__(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)


class ProtoSdkHeartBeat(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xD5


class ProtoSetSystemLed(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0x33


class ProtoChassisSetWorkMode(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0x19


class ProtoPlaySound(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xB3


class ProtoSoundPush(ProtoData):
    _cmdset = 0x3F
    _cmdid = 0xB4


def host2byte(host, index):
    return (int(host) << 5) | int(index)
