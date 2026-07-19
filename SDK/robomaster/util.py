from __future__ import annotations


class UnitChecker:
    def __init__(self, start=None, end=None, scale=1):
        self.start = start
        self.end = end
        self.scale = scale

    def check(self, value):
        if self.start is not None:
            value = max(value, self.start)
        if self.end is not None:
            value = min(value, self.end)
        return value

    def val2proto(self, value):
        return int(round(self.check(value) * self.scale))

    def proto2val(self, value):
        return value / self.scale


COLOR_VALUE_CHECKER = UnitChecker(0, 255)
GIMBAL_PITCH_TARGET_CHECKER = UnitChecker(-20, 35)
GIMBAL_YAW_TARGET_CHECKER = UnitChecker(-250, 250)
GIMBAL_PITCH_MOVE_CHECKER = UnitChecker(-55, 55)
GIMBAL_YAW_MOVE_CHECKER = UnitChecker(-500, 500, 10)
