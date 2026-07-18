from __future__ import annotations

from .action import ImmediateAction


class Gimbal:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def drive_speed(self, pitch_speed: float = 0.0, yaw_speed: float = 0.0, **kwargs) -> bool:
        if "pitch" in kwargs:
            pitch_speed = kwargs["pitch"]
        if "yaw" in kwargs:
            yaw_speed = kwargs["yaw"]
        self._robot.update_command(
            gimbal_pitch=float(pitch_speed) / self._robot.config.max_gimbal_speed,
            gimbal_yaw=float(yaw_speed) / self._robot.config.max_gimbal_speed,
        )
        return True

    def rotate_with_speed(self, yaw_speed: float = 0.0, pitch_speed: float = 0.0) -> bool:
        return self.drive_speed(pitch_speed=pitch_speed, yaw_speed=yaw_speed)

    def stop(self) -> None:
        self._robot.update_command(gimbal_pitch=0.0, gimbal_yaw=0.0)
        self._robot.send_once(gimbal_pitch=0.0, gimbal_yaw=0.0)

    def recenter(self, pitch_speed: float = 60, yaw_speed: float = 60) -> ImmediateAction:
        self._robot.bridge.call("gimbal", "recenter")
        return ImmediateAction()

    def move(self, pitch: float = 0.0, yaw: float = 0.0, pitch_speed: float = 30, yaw_speed: float = 30) -> ImmediateAction:
        if yaw:
            self._robot.bridge.call("gimbal", "rotate_with_degree", direction="yaw_right" if yaw > 0 else "yaw_left", degree=abs(float(yaw)))
        if pitch:
            self._robot.bridge.call("gimbal", "rotate_with_degree", direction="pitch_up" if pitch > 0 else "pitch_down", degree=abs(float(pitch)))
        return ImmediateAction()

    def moveto(self, pitch: float = 0.0, yaw: float = 0.0, pitch_speed: float = 30, yaw_speed: float = 30) -> ImmediateAction:
        self._robot.bridge.call("gimbal", "angle_ctrl", yaw=float(yaw), pitch=float(pitch))
        return ImmediateAction()

    def set_rotate_speed(self, speed: float = 30) -> bool:
        self._robot.bridge.call("gimbal", "set_rotate_speed", speed=float(speed))
        return True

    def set_follow_chassis_offset(self, offset: float = 0.0) -> bool:
        self._robot.bridge.call("gimbal", "set_follow_chassis_offset", offset=float(offset))
        return True

    def suspend(self) -> bool:
        self._robot.bridge.call("gimbal", "suspend")
        return True

    def resume(self) -> bool:
        self._robot.bridge.call("gimbal", "resume")
        return True

    def yaw_ctrl(self, yaw: float = 0.0) -> bool:
        self._robot.bridge.call("gimbal", "yaw_ctrl", yaw=float(yaw))
        return True

    def pitch_ctrl(self, pitch: float = 0.0) -> bool:
        self._robot.bridge.call("gimbal", "pitch_ctrl", pitch=float(pitch))
        return True

    def angle_ctrl(self, yaw: float = 0.0, pitch: float = 0.0) -> bool:
        self._robot.bridge.call("gimbal", "angle_ctrl", yaw=float(yaw), pitch=float(pitch))
        return True

    def sub_angle(self, freq: int = 5, callback=None, *args, **kwargs) -> bool:  # noqa: ANN001
        if callback is None:
            return False
        self._robot.on("gimbal_angle", lambda value: callback(value, *args, **kwargs))
        return True

    def unsub_angle(self) -> bool:
        return True
