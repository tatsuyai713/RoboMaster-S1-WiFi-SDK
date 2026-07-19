from __future__ import annotations

from robomaster_lab_sdk.action import ImmediateAction
from robomaster_lab_sdk.action import ActionDispatcher
from robomaster_lab_sdk.robot import Robot as _LabRobot
from robomaster_lab_sdk.unsupported import unsupported
from . import config as sdk_config
from .camera import EPCamera
from .dds import Subscriber

FREE = "free"
GIMBAL_LEAD = "gimbal_lead"
CHASSIS_LEAD = "chassis_lead"

SOUND_ID_ATTACK = 0x101
SOUND_ID_SHOOT = 0x102
SOUND_ID_SCANNING = 0x103
SOUND_ID_RECOGNIZED = 0x104
SOUND_ID_GIMBAL_MOVE = 0x105
SOUND_ID_COUNT_DOWN = 0x106
SOUND_ID_1C = 0x107
SOUND_ID_1C_SHARP = 0x108
SOUND_ID_1D = 0x109
SOUND_ID_1D_SHARP = 0x10A
SOUND_ID_1E = 0x10B
SOUND_ID_1F = 0x10C
SOUND_ID_1F_SHARP = 0x10D
SOUND_ID_1G = 0x10E
SOUND_ID_1A = 0x110
SOUND_ID_1A_SHARP = 0x111
SOUND_ID_1B = 0x112
SOUND_ID_2C = 0x113
SOUND_ID_2C_SHARP = 0x114
SOUND_ID_2D = 0x115
SOUND_ID_2D_SHARP = 0x116
SOUND_ID_2E = 0x117
SOUND_ID_2F = 0x118
SOUND_ID_2F_SHARP = 0x119
SOUND_ID_2G = 0x11A
SOUND_ID_2G_SHARP = 0x11B
SOUND_ID_2A = 0x11C
SOUND_ID_2A_SHARP = 0x11D
SOUND_ID_2B = 0x11E
SOUND_ID_3C = 0x11F
SOUND_ID_3C_SHARP = 0x120
SOUND_ID_3D = 0x121
SOUND_ID_3D_SHARP = 0x122
SOUND_ID_3E = 0x123
SOUND_ID_3F = 0x124
SOUND_ID_3F_SHARP = 0x125
SOUND_ID_3G = 0x126
SOUND_ID_3G_SHARP = 0x127
SOUND_ID_3A = 0x128
SOUND_ID_3A_SHARP = 0x129
SOUND_ID_3B = 0x12A


class RobotPlaySoundAction(ImmediateAction):
    def __init__(self, sound_id, times, **kw) -> None:  # noqa: ANN001, ANN003
        super().__init__(**kw)
        self.sound_id = sound_id
        self.times = times


class Robot(_LabRobot):
    def __init__(self, cli=None, **kwargs) -> None:  # noqa: ANN001, ANN003
        super().__init__(**kwargs)
        self.client = cli
        self.action_dispatcher = ActionDispatcher(cli)
        self.dds = Subscriber(self)
        self.conf = sdk_config.ep_conf
        previous_camera = self.camera
        self.off("video", previous_camera._on_video)
        self.camera = EPCamera(self)

    def initialize(self, conn_type="ap", proto_type="udp", sn=None):
        return super().initialize(conn_type=conn_type, proto_type=proto_type, sn=sn)

    def play_sound(self, sound_id, times=1):
        accepted = True
        for _ in range(max(1, int(times))):
            accepted = self.media.play_sound(sound_id) and accepted
        return RobotPlaySoundAction(
            sound_id=sound_id,
            times=times,
            accepted=accepted,
        )


class Drone:
    def __init__(self, cli=None) -> None:  # noqa: ANN001
        unsupported("Tello Drone")


__all__ = [
    "Robot",
    "RobotPlaySoundAction",
    "Drone",
    "FREE",
    "GIMBAL_LEAD",
    "CHASSIS_LEAD",
    "SOUND_ID_ATTACK",
    "SOUND_ID_SHOOT",
    "SOUND_ID_SCANNING",
    "SOUND_ID_RECOGNIZED",
    "SOUND_ID_GIMBAL_MOVE",
    "SOUND_ID_COUNT_DOWN",
]
