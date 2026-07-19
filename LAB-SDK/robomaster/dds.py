from __future__ import annotations

from robomaster_lab_sdk.unsupported import unsupported

DDS_BATTERY = "battery"
DDS_GIMBAL_BASE = "gimbal_base"
DDS_VELOCITY = "velocity"
DDS_ESC = "esc"
DDS_ATTITUDE = "attitude"
DDS_IMU = "imu"
DDS_POSITION = "position"
DDS_SA_STATUS = "sa_status"
DDS_CHASSIS_MODE = "chassis_mode"
DDS_SBUS = "sbus"
DDS_SERVO = "servo"
DDS_ARM = "arm"
DDS_GRIPPER = "gripper"
DDS_GIMBAL_POS = "gimbal_pos"
DDS_STICK = "stick"
DDS_MOVE_MODE = "move_mode"
DDS_TOF = "tof"
DDS_PINBOARD = "pinboard"


class Subject:
    def __init__(self):
        self._callback = None
        self._args = ()
        self._kw = {}

    def set_callback(self, callback, args, kw):
        self._callback = callback
        self._args = args
        self._kw = kw

    def data_info(self):
        unsupported("low-level DDS subject decoding")

    def exec(self):
        if self._callback is not None:
            self._callback(self.data_info(), *self._args, **self._kw)


class Subscriber:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._next_subject_id = 0

    def get_next_subject_id(self):
        self._next_subject_id = (self._next_subject_id + 1) & 0xFF
        return self._next_subject_id

    def start(self):
        return True

    def stop(self):
        return True

    def add_cmd_filter(self, cmd_set, cmd_id):
        unsupported("low-level DDS command filters")

    def del_cmd_filter(self, cmd_set, cmd_id):
        unsupported("low-level DDS command filters")

    def add_subject_event_info(self, subject, callback=None, *args):
        unsupported("low-level DDS event subjects")

    def del_subject_event_info(self, subject):
        unsupported("low-level DDS event subjects")

    def add_subject_info(self, subject, callback=None, *args):
        unsupported("low-level DDS subjects")

    def del_subject_info(self, subject_name):
        unsupported("low-level DDS subjects")
