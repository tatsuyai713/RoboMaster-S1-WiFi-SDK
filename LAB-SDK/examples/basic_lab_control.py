from __future__ import annotations

import time

from robomaster import blaster, robot


def main() -> None:
    s1_robot = robot.Robot(appid="b6359877", robot_ip="192.168.23.149")
    s1_robot.initialize(conn_type="sta")
    s1_robot.chassis.drive_speed(x=0.3, y=0, z=0)
    time.sleep(1)
    s1_robot.chassis.stop()
    s1_robot.gimbal.drive_speed(yaw_speed=30, pitch_speed=0)
    time.sleep(1)
    s1_robot.gimbal.stop()
    s1_robot.blaster.fire(fire_type=blaster.INFRARED_FIRE)
    s1_robot.close()


if __name__ == "__main__":
    main()
