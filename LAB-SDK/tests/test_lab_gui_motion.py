from __future__ import annotations

import unittest

from robomaster_s1_lab_app import LabApp


class _Component:
    def __init__(self) -> None:
        self.stop_count = 0

    def stop(self) -> None:
        self.stop_count += 1


class _Robot:
    def __init__(self) -> None:
        self.chassis = _Component()
        self.gimbal = _Component()


class LabGuiMotionTests(unittest.TestCase):
    def make_app(self):
        app = object.__new__(LabApp)
        app.robot = _Robot()
        app.bridge = object()
        app.control_job = None
        app.current_action = None
        app.current_action_group = None
        app.log = lambda _message: None
        return app

    def test_press_sets_state_once_and_release_stops_only_that_group(self) -> None:
        app = self.make_app()
        calls = []
        app.begin_command("gimbal", lambda: calls.append("gimbal"))
        self.assertEqual(calls, ["gimbal"])
        self.assertIsNone(app.control_job)

        app._end_current_command()
        self.assertEqual(app.robot.gimbal.stop_count, 1)
        self.assertEqual(app.robot.chassis.stop_count, 0)

    def test_switching_groups_stops_previous_motion(self) -> None:
        app = self.make_app()
        app.begin_command("gimbal", lambda: None)
        app.begin_command("chassis", lambda: None)
        self.assertEqual(app.robot.gimbal.stop_count, 1)
        self.assertEqual(app.robot.chassis.stop_count, 0)


if __name__ == "__main__":
    unittest.main()
