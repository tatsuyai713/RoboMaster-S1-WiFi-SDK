from __future__ import annotations

import queue
import unittest

import robomaster_s1_sdk_app
import robomaster_s1_unified_app


class _Status:
    def set(self, _value):
        return None


def make_app(app_class):
    app = object.__new__(app_class)
    app.worker = object()
    app.last_sent_action = ""
    app.current_action_group = None
    app.commands = queue.Queue(maxsize=64)
    app.motion_commands = queue.Queue(maxsize=1)
    app.stop_commands = queue.Queue(maxsize=1)
    app.status_var = _Status()
    return app


class GuiMotionTests(unittest.TestCase):
    def test_release_immediately_stops_the_same_component(self) -> None:
        for app_class in (
            robomaster_s1_unified_app.UnifiedApp,
            robomaster_s1_sdk_app.UnifiedApp,
        ):
            with self.subTest(app=app_class.__module__):
                app = make_app(app_class)
                app.press_action("gimbal_left")
                self.assertEqual(app.motion_commands.get_nowait(), "gimbal_left")
                app.release_action("gimbal_left")
                self.assertEqual(app.motion_commands.get_nowait(), "gimbal_stop")

    def test_switch_queues_old_component_stop_before_new_state(self) -> None:
        for app_class in (
            robomaster_s1_unified_app.UnifiedApp,
            robomaster_s1_sdk_app.UnifiedApp,
        ):
            with self.subTest(app=app_class.__module__):
                app = make_app(app_class)
                app.press_action("gimbal_left")
                app.motion_commands.get_nowait()
                app.press_action("forward")
                self.assertEqual(app.stop_commands.get_nowait(), "gimbal_stop")
                self.assertEqual(app.motion_commands.get_nowait(), "forward")


if __name__ == "__main__":
    unittest.main()
