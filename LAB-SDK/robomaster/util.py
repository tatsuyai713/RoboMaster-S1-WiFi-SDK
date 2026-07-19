"""Value conversion helpers compatible with :mod:`robomaster.util`."""

UNIT_METRIC = "Unit Metric"
UNIT_INCH = "Unit Inch"


class UnitChecker:
    def __init__(
        self,
        name,
        default=0,
        start=0,
        end=0,
        step=1,
        decimal=2,
        scale=1,
        unit=UNIT_METRIC,
    ):
        self._name = name
        self._default = default
        self._start = start
        self._end = end
        self._step = step
        self._decimal = None if decimal == 0 else decimal
        self._scale = scale
        self._unit = unit

    name = property(lambda self: self._name)
    default = property(lambda self: self._default)
    start = property(lambda self: self._start)
    end = property(lambda self: self._end)
    step = property(lambda self: self._step)
    decimal = property(lambda self: self._decimal)
    scale = property(lambda self: self._scale)
    unit = property(lambda self: self._unit)

    def check(self, value):
        if self._start is not None and self._end is not None:
            value = min(max(value, self._start), self._end)
        return value

    def proto2val(self, val):
        return round(val / self._scale, self._decimal)

    def val2proto(self, val):
        return int(round(self.check(val) * self._scale))


GIMBAL_PITCH_TARGET_CHECKER = UnitChecker("gimbal pitch target", 0, -20, 35, decimal=0)
GIMBAL_YAW_TARGET_CHECKER = UnitChecker("gimbal yaw target", 0, -250, 250, decimal=0)
GIMBAL_PITCH_MOVE_CHECKER = UnitChecker("gimbal pitch move", 0, -55, 55, decimal=0)
GIMBAL_YAW_MOVE_CHECKER = UnitChecker("gimbal yaw move", 0, -500, 500, decimal=0, scale=10)
GIMBAL_PITCH_MOVE_SPEED_SET_CHECKER = UnitChecker("gimbal pitch move speed", 30, 0, 540, decimal=0)
GIMBAL_YAW_MOVE_SPEED_SET_CHECKER = UnitChecker("gimbal yaw move speed", 30, 0, 540, decimal=0)
GIMBAL_PITCH_SPEED_SET_CHECKER = UnitChecker("gimbal pitch speed", 30, -540, 540, decimal=0, scale=10)
GIMBAL_YAW_SPEED_SET_CHECKER = UnitChecker("gimbal yaw speed", 30, -540, 540, decimal=0, scale=10)
GIMBAL_ATTI_PITCH_CHECKER = UnitChecker("gimbal pitch attitude", scale=10)
GIMBAL_ATTI_YAW_CHECKER = UnitChecker("gimbal yaw attitude", scale=10)
CHASSIS_POS_X_SET_CHECKER = UnitChecker("chassis x", 0, -5, 5, 0.01, 0, 100)
CHASSIS_POS_Y_SET_CHECKER = UnitChecker("chassis y", 0, -5, 5, 0.01, 0, 100)
CHASSIS_POS_Z_SET_CHECKER = UnitChecker("chassis z", 0, -1800, 1800, 0.1, 0, 10)
CHASSIS_POS_X_SUB_CHECKER = UnitChecker("chassis x sub", decimal=5)
CHASSIS_POS_Y_SUB_CHECKER = UnitChecker("chassis y sub", decimal=5)
CHASSIS_POS_Z_SUB_CHECKER = UnitChecker("chassis z sub", decimal=2)
CHASSIS_PITCH_CHECKER = UnitChecker("chassis pitch", 0, -180, 180)
CHASSIS_YAW_CHECKER = UnitChecker("chassis yaw", 0, -180, 180)
CHASSIS_ROLL_CHECKER = UnitChecker("chassis roll", 0, -180, 180)
CHASSIS_ACC_CHECKER = UnitChecker("chassis acceleration", start=None, end=None, decimal=5)
CHASSIS_GYRO_CHECKER = UnitChecker("chassis gyro", start=None, end=None, decimal=5)
CHASSIS_SPD_X_CHECKER = UnitChecker("chassis speed x", 0, -3.5, 3.5)
CHASSIS_SPD_Y_CHECKER = UnitChecker("chassis speed y", 0, -3.5, 3.5)
CHASSIS_SPD_Z_CHECKER = UnitChecker("chassis speed z", 0, -600, 600, decimal=0)
WHEEL_SPD_CHECKER = UnitChecker("wheel speed", 0, -1000, 1000, decimal=0)
PWM_VALUE_CHECKER = UnitChecker("pwm value", 0, 0, 50000, decimal=0)
PWM_FREQ_CHECKER = UnitChecker("pwm frequency", 1000, 0, 100, decimal=0, scale=10)
ROBOTIC_ARM_POS_CHECK = UnitChecker("robotic arm position", start=None, end=None, decimal=0)
GRIPPER_POWER_CHECK = UnitChecker("gripper power", 50, 1, 100, decimal=0, scale=6.6)
COLOR_VALUE_CHECKER = UnitChecker("color", 0, 0, 255, decimal=0)
FIRE_TIMES_CHECKER = UnitChecker("fire times", 1, 1, 5, decimal=0)
