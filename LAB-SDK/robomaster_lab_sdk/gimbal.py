from __future__ import annotations

from .action import ImmediateAction
from .subscription import rate_limited_callback


class GimbalMoveAction(ImmediateAction):
    def __init__(
        self,
        pitch=0,
        yaw=0,
        pitch_speed=30,
        yaw_speed=30,
        coord=4,
        **kw,
    ) -> None:  # noqa: ANN003
        super().__init__(**kw)
        self.pitch = pitch
        self.yaw = yaw
        self.pitch_speed = pitch_speed
        self.yaw_speed = yaw_speed
        self.coord = coord


class GimbalRecenterAction(ImmediateAction):
    def __init__(self, pitch_speed=100, yaw_speed=100, **kw) -> None:  # noqa: ANN003
        super().__init__(**kw)
        self.pitch_speed = pitch_speed
        self.yaw_speed = yaw_speed


class Gimbal:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self._angle_callback = None

    def drive_speed(self, pitch_speed: float = 30.0, yaw_speed: float = 30.0) -> bool:
        return self._robot.update_command(
            gimbal_pitch=float(pitch_speed) / self._robot.config.max_gimbal_speed,
            gimbal_yaw=float(yaw_speed) / self._robot.config.max_gimbal_speed,
        )

    def rotate_with_speed(self, yaw_speed: float = 0.0, pitch_speed: float = 0.0) -> bool:
        return self.drive_speed(pitch_speed=pitch_speed, yaw_speed=yaw_speed)

    def stop(self) -> None:
        self._robot.update_command(gimbal_pitch=0.0, gimbal_yaw=0.0)
        self._robot.bridge.stop_gimbal()

    def recenter(self, pitch_speed: float = 60, yaw_speed: float = 60) -> ImmediateAction:
        self.stop()
        return GimbalRecenterAction(
            pitch_speed=pitch_speed,
            yaw_speed=yaw_speed,
            accepted=self._robot.bridge.call("gimbal", "recenter"),
        )

    def move(self, pitch: float = 0, yaw: float = 0, pitch_speed: float = 30, yaw_speed: float = 30) -> ImmediateAction:
        self.stop()
        accepted = self.set_rotate_speed(max(abs(float(pitch_speed)), abs(float(yaw_speed))))
        if yaw:
            accepted = self._robot.bridge.call("gimbal", "rotate_with_degree", direction="yaw_right" if yaw > 0 else "yaw_left", degree=abs(float(yaw))) and accepted
        if pitch:
            accepted = self._robot.bridge.call("gimbal", "rotate_with_degree", direction="pitch_up" if pitch > 0 else "pitch_down", degree=abs(float(pitch))) and accepted
        return GimbalMoveAction(
            pitch=pitch,
            yaw=yaw,
            pitch_speed=pitch_speed,
            yaw_speed=yaw_speed,
            accepted=accepted,
        )

    def moveto(self, pitch: float = 0, yaw: float = 0, pitch_speed: float = 30, yaw_speed: float = 30) -> ImmediateAction:
        self.stop()
        accepted = self.set_rotate_speed(max(abs(float(pitch_speed)), abs(float(yaw_speed))))
        accepted = self._robot.bridge.call("gimbal", "angle_ctrl", yaw=float(yaw), pitch=float(pitch)) and accepted
        return GimbalMoveAction(
            pitch=pitch,
            yaw=yaw,
            pitch_speed=pitch_speed,
            yaw_speed=yaw_speed,
            accepted=accepted,
        )

    def set_rotate_speed(self, speed: float = 30) -> bool:
        return self._robot.bridge.call("gimbal", "set_rotate_speed", speed=float(speed))

    def set_follow_chassis_offset(self, offset: float = 0.0) -> bool:
        return self._robot.bridge.call("gimbal", "set_follow_chassis_offset", offset=float(offset))

    def suspend(self) -> bool:
        return self._robot.bridge.call("gimbal", "suspend")

    def resume(self) -> bool:
        return self._robot.bridge.call("gimbal", "resume")

    def yaw_ctrl(self, yaw: float = 0.0) -> bool:
        return self._robot.bridge.call("gimbal", "yaw_ctrl", yaw=float(yaw))

    def pitch_ctrl(self, pitch: float = 0.0) -> bool:
        return self._robot.bridge.call("gimbal", "pitch_ctrl", pitch=float(pitch))

    def angle_ctrl(self, yaw: float = 0.0, pitch: float = 0.0) -> bool:
        return self._robot.bridge.call("gimbal", "angle_ctrl", yaw=float(yaw), pitch=float(pitch))

    def sub_angle(self, freq: int = 5, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        if self._angle_callback is not None:
            self._robot.off("gimbal_angle", self._angle_callback)
        self._angle_callback = rate_limited_callback(
            freq,
            lambda value: callback(
                (value[0], value[1], None, None), *args, **kw
            )
        )
        self._robot.on("gimbal_angle", self._angle_callback)
        self._robot._set_telemetry_request(
            "gimbal:angle",
            {"gimbal_pitch", "gimbal_yaw"},
            int(freq),
        )
        return True

    def unsub_angle(self) -> bool:
        if self._angle_callback is None:
            return False
        callback = self._angle_callback
        self._angle_callback = None
        removed = self._robot.off("gimbal_angle", callback)
        self._robot._clear_telemetry_request("gimbal:angle")
        return removed
