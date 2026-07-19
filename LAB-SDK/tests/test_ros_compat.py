from __future__ import annotations

import unittest

import robomaster
from robomaster import action, battery, client, conn, media, protocol
from robomaster_lab_sdk.battery import Battery


class _EventRobot:
    def __init__(self) -> None:
        self.callbacks = {}

    def on(self, event, callback):
        self.callbacks.setdefault(event, []).append(callback)
        return callback

    def off(self, event, callback):
        callbacks = self.callbacks.get(event, [])
        if callback not in callbacks:
            return False
        callbacks.remove(callback)
        return True


class _BatteryRobot(_EventRobot):
    class _Base:
        @staticmethod
        def get_battery():
            return 73

    base = _Base()


class RosCompatibilityTests(unittest.TestCase):
    def test_lab_backend_marker_and_private_import_shims_exist(self) -> None:
        self.assertTrue(robomaster.IS_LAB_SDK)
        self.assertIsNotNone(client.MsgHandler(protocol.ProtoSdkHeartBeat()))
        self.assertTrue(issubclass(protocol.ProtoSetSystemLed, protocol.ProtoData))
        self.assertTrue(issubclass(protocol.ProtoPlaySound, protocol.ProtoData))
        self.assertTrue(hasattr(battery, "BatterySubject"))
        self.assertTrue(hasattr(conn, "ConnectionHelper"))
        self.assertTrue(hasattr(conn, "FtpConnection"))

    def test_liveview_uses_bounded_event_queues(self) -> None:
        liveview = media.LiveView(_EventRobot())
        self.assertEqual(liveview._video_frame_queue.maxsize, 64)
        self.assertEqual(liveview._audio_frame_queue.maxsize, 32)
        self.assertEqual(liveview._video_stream_conn._sock_queue.maxsize, 256)

    def test_battery_callback_has_official_four_value_shape(self) -> None:
        robot = _BatteryRobot()
        api = Battery(robot)
        values = []
        self.assertTrue(api.sub_battery_info(freq=1, callback=values.append))
        robot.callbacks["telemetry"][0]({})
        self.assertEqual(values, [(0, 0, 0, 73)])

    def test_immediate_action_has_ros_expected_state_event(self) -> None:
        item = action.ImmediateAction(accepted=True)
        self.assertTrue(item._event.is_set())
        self.assertTrue(item.has_succeeded)
        self.assertEqual(item._percent, 100)


if __name__ == "__main__":
    unittest.main()
