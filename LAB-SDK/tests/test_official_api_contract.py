from __future__ import annotations

import inspect
import unittest

from robomaster import chassis, gimbal, led, robot, vision


class OfficialApiContractTests(unittest.TestCase):
    def test_robot_initialize_signature(self) -> None:
        self.assertEqual(
            str(inspect.signature(robot.Robot.initialize)),
            "(self, conn_type='ap', proto_type='udp', sn=None)",
        )

    def test_component_parameter_names_and_defaults(self) -> None:
        signatures = {
            chassis.Chassis.drive_speed: ("x", "y", "z", "timeout"),
            chassis.Chassis.drive_wheels: ("w1", "w2", "w3", "w4", "timeout"),
            chassis.Chassis.move: ("x", "y", "z", "xy_speed", "z_speed"),
            chassis.Chassis.sub_position: ("cs", "freq", "callback", "args", "kw"),
            gimbal.Gimbal.drive_speed: ("pitch_speed", "yaw_speed"),
            led.Led.set_gimbal_led: ("comp", "r", "g", "b", "led_list", "effect"),
            vision.Vision.sub_detect_info: ("name", "color", "callback", "args", "kw"),
        }
        for method, expected in signatures.items():
            actual = tuple(inspect.signature(method).parameters)[1:]
            self.assertEqual(actual, expected, method.__qualname__)

        self.assertEqual(
            inspect.signature(gimbal.Gimbal.drive_speed).parameters["pitch_speed"].default,
            30.0,
        )
        self.assertEqual(
            inspect.signature(led.Led.set_led).parameters["r"].default,
            0,
        )

    def test_official_modules_are_importable(self) -> None:
        from robomaster import (  # noqa: F401
            action,
            ai_module,
            algo,
            armor,
            battery,
            blaster,
            camera,
            chassis,
            client,
            config,
            conn,
            dds,
            event,
            exceptions,
            flight,
            gimbal,
            gripper,
            led,
            media,
            module,
            protocol,
            robot,
            robotic_arm,
            sensor,
            servo,
            uart,
            util,
            version,
            vision,
        )


if __name__ == "__main__":
    unittest.main()
