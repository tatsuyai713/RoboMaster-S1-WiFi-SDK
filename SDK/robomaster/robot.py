from __future__ import annotations

from robomaster_s1_sdk.robot import Robot as _S1Robot

FREE = "free"
GIMBAL_LEAD = "gimbal_lead"
CHASSIS_LEAD = "chassis_lead"


class Robot(_S1Robot):
    """Official RoboMaster SDK style Robot facade for RoboMaster S1 Wi-Fi.

    Official examples can use:

        from robomaster import robot
        ep_robot = robot.Robot(appid="b6359877")
        ep_robot.initialize(conn_type="sta")

    The S1-specific QR/AppID pairing options remain available as constructor
    keyword arguments.
    """


class Drone:
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise NotImplementedError("Drone/Tello API is not part of the RoboMaster S1 Wi-Fi SDK")


__all__ = ["Robot", "Drone", "FREE", "GIMBAL_LEAD", "CHASSIS_LEAD"]
