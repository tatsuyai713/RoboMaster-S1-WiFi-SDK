from __future__ import annotations

from .action import ImmediateAction
class Gimbal:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self.pitch_sensitivity = 40
        self.yaw_sensitivity = 50
        self._angle_callback = None

    def drive_speed(self, pitch_speed: float = 30.0, yaw_speed: float = 30.0) -> bool:
        self._robot.set_gimbal_velocity(pitch_speed, yaw_speed)
        return True

    def move(
        self,
        pitch: float = 0.0,
        yaw: float = 0.0,
        pitch_speed: float = 30,
        yaw_speed: float = 30,
    ) -> ImmediateAction:
        raise NotImplementedError("Gimbal relative angle action is not mapped for the S1 Wi-Fi protocol yet")

    def moveto(
        self,
        pitch: float = 0.0,
        yaw: float = 0.0,
        pitch_speed: float = 30,
        yaw_speed: float = 30,
    ) -> ImmediateAction:
        raise NotImplementedError("Gimbal absolute angle action is not mapped for the S1 Wi-Fi protocol yet")

    def recenter(self, pitch_speed: float = 60, yaw_speed: float = 60) -> ImmediateAction:
        raise NotImplementedError("Gimbal recenter is not mapped for the S1 Wi-Fi protocol")

    def suspend(self) -> bool:
        raise NotImplementedError("Gimbal suspend is not mapped for the S1 Wi-Fi protocol")

    def resume(self) -> bool:
        raise NotImplementedError("Gimbal resume is not mapped for the S1 Wi-Fi protocol")

    def calibrate(self) -> ImmediateAction:
        """Start gimbal auto calibration.

        This maps to the Windows App calibration command observed in the
        chassis/gimbal calibration capture.
        """
        self._robot.send_duss(0x02, 0x04, 0x40, 0x04, 0x08, b"")
        return ImmediateAction()

    def _pitch_speed(self, speed: float) -> float:
        return abs(speed) * self.pitch_sensitivity / 50.0

    def _yaw_speed(self, speed: float) -> float:
        return abs(speed) * self.yaw_sensitivity / 50.0

    def stop(self) -> None:
        self._robot.set_control_action("gimbal_stop", timeout=None)

    def up(self, speed: float = 0.6) -> None:
        self._robot.set_control_action("gimbal_up", timeout=None)

    def down(self, speed: float = 0.6) -> None:
        self._robot.set_control_action("gimbal_down", timeout=None)

    def left(self, speed: float = 0.6) -> None:
        self._robot.set_control_action("gimbal_left", timeout=None)

    def right(self, speed: float = 0.6) -> None:
        self._robot.set_control_action("gimbal_right", timeout=None)

    def set_control_sensitivity(self, pitch: int = 40, yaw: int = 50) -> None:
        self.pitch_sensitivity = max(0, min(100, int(pitch)))
        self.yaw_sensitivity = max(0, min(100, int(yaw)))
        self._robot.gimbal_pitch_sensitivity = self.pitch_sensitivity
        self._robot.gimbal_yaw_sensitivity = self.yaw_sensitivity

    def sub_angle(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False

        def _call(value):
            callback((value.raw0, value.raw1, value.raw2, value.raw3), *args, **kw)

        if self._angle_callback is not None:
            self._robot.off("gimbal", self._angle_callback)
        self._angle_callback = _call
        self._robot.on("gimbal", _call)
        return True

    def unsub_angle(self) -> bool:
        if self._angle_callback is None:
            return False
        callback = self._angle_callback
        self._angle_callback = None
        return self._robot.off("gimbal", callback)
