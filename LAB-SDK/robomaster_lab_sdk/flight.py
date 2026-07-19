from __future__ import annotations

from .unsupported import unsupported


class Flight:
    """DJI Tello/Drone API placeholder.

    The class and official method signatures are present for import
    compatibility. RoboMaster S1 is a ground robot, so every operation raises
    an explicit unsupported error.
    """

    def __init__(self, robot=None) -> None:  # noqa: ANN001
        self._robot = robot

    def _unsupported(self):
        return unsupported("Tello flight")

    def takeoff(self, retry: bool = True):
        return self._unsupported()

    def land(self, retry: bool = True):
        return self._unsupported()

    def up(self, distance=0, retry: bool = True):
        return self._unsupported()

    def down(self, distance=0, retry: bool = True):
        return self._unsupported()

    def forward(self, distance=0, retry: bool = True):
        return self._unsupported()

    def backward(self, distance=0, retry: bool = True):
        return self._unsupported()

    def left(self, distance=0, retry: bool = True):
        return self._unsupported()

    def right(self, distance=0, retry: bool = True):
        return self._unsupported()

    def fly(self, direction="forward", distance=0, retry: bool = True):
        return self._unsupported()

    def rotate(self, angle=0, retry: bool = True):
        return self._unsupported()

    def flip_forward(self, retry: bool = True):
        return self._unsupported()

    def flip_backward(self, retry: bool = True):
        return self._unsupported()

    def flip_left(self, retry: bool = True):
        return self._unsupported()

    def flip_right(self, retry: bool = True):
        return self._unsupported()

    def flip(self, direction="f", retry: bool = True):
        return self._unsupported()

    def throw_fly(self):
        return self._unsupported()

    def go(self, x, y, z, speed=10, mid=None, retry: bool = True):
        return self._unsupported()

    def move(self, x=0, y=0, z=0, speed=10, mid=None, retry: bool = True):
        return self._unsupported()

    def moveto(self, yaw=0, retry: bool = True):
        return self._unsupported()

    def rc(self, a=0, b=0, c=0, d=0):
        return self._unsupported()

    def curve(self, x1=0, y1=0, z1=0, x2=0, y2=0, z2=0, speed=20, mid=None, retry: bool = True):
        return self._unsupported()

    def stop(self, retry: bool = True):
        return self._unsupported()

    def jump(self, x=0, y=0, z=0, speed=20, yaw=0, mid1="m-1", mid2="m-1", retry: bool = True):
        return self._unsupported()

    def set_speed(self, speed=0):
        return self._unsupported()

    def mission_pad_on(self):
        return self._unsupported()

    def mission_pad_off(self):
        return self._unsupported()

    def motor_on(self):
        return self._unsupported()

    def motor_off(self):
        return self._unsupported()

    def get_speed(self):
        return self._unsupported()

    def sub_attitude(self, freq=5, callback=None, *args, **kw):
        return self._unsupported()

    def unsub_attitude(self):
        return self._unsupported()

    def sub_imu(self, freq=5, callback=None, *args, **kw):
        return self._unsupported()

    def unsub_imu(self):
        return self._unsupported()
