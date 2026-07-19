from __future__ import annotations

import unittest

import robomaster_s1_unified_app as unified
from robomaster_s1_sdk import protocol
from robomaster_s1_sdk.robot import Robot


class UnifiedPathParityTests(unittest.TestCase):
    def test_transport_constants_match_working_unified_path(self) -> None:
        self.assertEqual(protocol.APP_PORT, unified.APP_PORT)
        self.assertEqual(protocol.ROBOT_APP_PORT, unified.ROBOT_APP_PORT)
        self.assertEqual(protocol.ROBOT_CONTROL_PORT, unified.ROBOT_CONTROL_PORT)
        self.assertEqual(protocol.DEFAULT_LOCAL_CONTROL_PORT, unified.DEFAULT_LOCAL_CONTROL_PORT)
        self.assertEqual(protocol.DEFAULT_INIT_SEQ, unified.DEFAULT_INIT_SEQ)
        self.assertEqual(protocol.DEFAULT_CONTROL_HZ, unified.DEFAULT_CONTROL_HZ)
        self.assertEqual(protocol.CONTROL_AFTER_APPID_DELAY, unified.CONTROL_AFTER_APPID_DELAY)

    def test_motion_payload_builders_match_working_unified_path(self) -> None:
        for x, y, z in (
            (0.0, 0.0, 0.0),
            (0.3, -0.2, 0.5),
            (-1.0, 1.0, -1.0),
            (10.0, -10.0, 10.0),
        ):
            self.assertEqual(
                protocol.build_chassis_velocity_payload(x, y, z),
                unified.build_chassis_velocity_payload(x, y, z),
            )
            self.assertEqual(
                protocol.build_gimbal_velocity_payload(x, y),
                unified.build_gimbal_velocity_payload(x, y),
            )

    def test_telemetry_decoders_match_working_unified_path(self) -> None:
        payloads = (
            bytes.fromhex("000a010002000300040005"),
            bytes(range(62)),
            b"\x00" * 12,
            b"\x01\x02\x03",
        )
        for payload in payloads:
            sdk_4808 = protocol.decode_4808(payload)
            app_4808 = unified.decode_4808(payload)
            self.assertEqual(
                None if sdk_4808 is None else sdk_4808.__dict__,
                None if app_4808 is None else app_4808.__dict__,
            )
            sdk_3f03 = protocol.decode_3f03(payload)
            app_3f03 = unified.decode_3f03(payload)
            self.assertEqual(
                None if sdk_3f03 is None else sdk_3f03.__dict__,
                None if app_3f03 is None else app_3f03.__dict__,
            )

    def test_setup_entries_match_captured_unified_sequence(self) -> None:
        sdk_entries = Robot()._setup_entries()
        unified_entries = {
            unified.DEFAULT_INIT_SEQ + index: entry
            for index, entry in enumerate(
                unified.iter_solo_setup(
                    unified.DEFAULT_PAIR_HASH1,
                    unified.DEFAULT_PAIR_HASH2,
                )
            )
        }
        self.assertEqual(sdk_entries, unified_entries)

    def test_official_gimbal_speed_is_scaled_before_raw_encoding(self) -> None:
        robot = Robot()
        robot.set_gimbal_velocity(30, -60)
        self.assertEqual(robot._control_name, "gimbal_velocity")
        self.assertEqual(
            robot._control_payload,
            unified.build_gimbal_velocity_payload(0.25, -0.5),
        )

    def test_transient_control_sequence_is_bounded(self) -> None:
        robot = Robot()
        robot.queue_control_sequence(
            [bytes([index & 0xFF]) for index in range(512)]
        )
        self.assertEqual(len(robot._control_sequence), 128)


if __name__ == "__main__":
    unittest.main()
