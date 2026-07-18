from __future__ import annotations

import time

from robomaster_s1_sdk import Robot


def main() -> None:
    robot = Robot(appid="b6359877", robot_ip="192.168.23.149", debug=True)
    robot.on("gimbal", lambda value: print("gimbal", value))
    robot.on("odometry", lambda value: print("odometry", value))

    robot.initialize()
    robot.enter_solo()

    robot.led.set_color(0, 80, 255)
    robot.settings.set_speed_preset("medium")

    robot.chassis.forward()
    time.sleep(1.0)
    robot.chassis.stop()

    robot.gimbal.left()
    time.sleep(0.5)
    robot.gimbal.stop()

    robot.blaster.fire()
    time.sleep(0.5)

    robot.exit_solo()
    robot.close()


if __name__ == "__main__":
    main()
