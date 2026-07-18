from __future__ import annotations

import time

from robomaster import blaster, robot


def main() -> None:
    ep_robot = robot.Robot(appid="b6359877", robot_ip="192.168.23.149")
    ep_robot.initialize(conn_type="sta")
    ep_robot.chassis.drive_speed(x=0.3, y=0, z=0)
    time.sleep(1)
    ep_robot.chassis.stop()
    ep_robot.gimbal.drive_speed(yaw_speed=30, pitch_speed=0)
    time.sleep(1)
    ep_robot.gimbal.stop()
    ep_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE)
    ep_robot.close()


if __name__ == "__main__":
    main()
