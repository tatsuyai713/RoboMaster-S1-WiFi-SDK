from __future__ import annotations

from types import SimpleNamespace
import inspect
import unittest

import robomaster
from robomaster import media
from robomaster_s1_sdk.armor import Armor
from robomaster_s1_sdk.battery import Battery
from robomaster_s1_sdk.chassis import Chassis


class _Robot:
    def __init__(self) -> None:
        self.callbacks = {}

    def on(self, event, callback):
        self.callbacks.setdefault(event, []).append(callback)
        return callback

    def off(self, event, callback):
        values = self.callbacks.get(event, [])
        if callback not in values:
            return False
        values.remove(callback)
        return True


class RosCompatibilityTests(unittest.TestCase):
    def test_backend_marker_and_private_import_shims_exist(self) -> None:
        self.assertTrue(robomaster.IS_S1_WIFI_SDK)
        self.assertFalse(robomaster.IS_LAB_SDK)
        for name in ("client", "config", "conn", "media", "protocol", "util"):
            __import__("robomaster." + name)

    def test_chassis_position_accepts_official_cs_parameter(self) -> None:
        parameters = inspect.signature(Chassis.sub_position).parameters
        self.assertIn("cs", parameters)

    def test_battery_callback_keeps_official_four_value_shape(self) -> None:
        robot = _Robot()
        values = []
        self.assertTrue(Battery(robot).sub_battery_info(callback=values.append))
        robot.callbacks["stats"][0](SimpleNamespace(battery_percent=73))
        self.assertEqual(values, [(0, 0, 0, 73)])

    def test_armor_callback_keeps_official_three_value_shape(self) -> None:
        robot = _Robot()
        values = []
        self.assertTrue(Armor(robot).sub_hit_event(callback=values.append))
        robot.callbacks["armor_damage"][0](
            SimpleNamespace(armor="front", impact_id=2, source="ir_hit")
        )
        self.assertEqual(values, [(2, 1, 0)])

    def test_immediate_action_exposes_ros_state_fields(self) -> None:
        action = robomaster.action.ImmediateAction()
        self.assertEqual(action._percent, 100)
        self.assertTrue(action.has_succeeded)
        self.assertTrue(action.wait_for_completed(timeout=0))

    def test_liveview_has_bounded_decoded_audio_path(self) -> None:
        liveview = media.LiveView(_Robot())
        self.assertEqual(liveview._audio_stream_conn._sock_queue.maxsize, 32)
        self.assertEqual(liveview._audio_frame_queue.maxsize, 32)
        self.assertTrue(hasattr(liveview, "_audio_decoder"))


if __name__ == "__main__":
    unittest.main()
