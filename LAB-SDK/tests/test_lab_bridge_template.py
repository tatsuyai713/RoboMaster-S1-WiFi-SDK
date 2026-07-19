from __future__ import annotations

import ast
import unittest

from robomaster_lab_sdk.config import LabSdkConfig
from robomaster_lab_sdk.program import render_bridge_python


class LabBridgeTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = render_bridge_python(
            LabSdkConfig(control_period_sec=0.02, telemetry_period_sec=0.04)
        )
        self.tree = ast.parse(self.source)

    def test_rendered_source_compiles_and_has_no_placeholders(self) -> None:
        compile(self.source, "lab_control_bridge.py", "exec")
        ast.parse(self.source, feature_version=(3, 6))
        self.assertNotIn("__COMMAND_PORT__", self.source)
        self.assertNotIn("__TELEMETRY_PERIOD_SEC__", self.source)

    def test_telemetry_uses_real_controller_getters(self) -> None:
        required = (
            "chassis_ctrl.get_position_based_power_on",
            "chassis_ctrl.get_attitude",
            "chassis_ctrl.get_speed",
            "gimbal_ctrl.get_axis_angle",
        )
        for expression in required:
            self.assertIn(expression, self.source)

    def test_telemetry_echoes_the_active_host_session(self) -> None:
        self.assertIn('state["session_id"] = int(number(', self.source)
        self.assertIn('parts.append(\',"session_id":\' + str(session_id))', self.source)

    def test_scheduler_does_not_sleep_one_period_after_work(self) -> None:
        self.assertNotIn("_time.sleep(TELEMETRY_PERIOD_SEC)", self.source)
        self.assertIn("missed_periods", self.source)
        self.assertIn('getattr(_time, "monotonic", _time.time)', self.source)

    def test_io_children_never_reference_lab_controllers(self) -> None:
        child_names = {"RECEIVER_PROCESS_CODE", "SENDER_PROCESS_CODE"}
        child_sources = {}
        for node in self.tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in child_names:
                    child_sources[target.id] = ast.literal_eval(node.value)
        self.assertEqual(set(child_sources), child_names)
        for name, child_source in child_sources.items():
            ast.parse(child_source, feature_version=(3, 6))
            self.assertNotIn("_ctrl", child_source, name)
            self.assertNotIn("rm_define", child_source, name)
            self.assertNotIn("json.loads", child_source, name)
            self.assertNotIn("json.dumps", child_source, name)

    def test_rx_and_tx_are_separate_child_processes(self) -> None:
        self.assertIn("receiver = _subprocess.Popen(", self.source)
        self.assertIn("sender = _subprocess.Popen(", self.source)

    def test_robot_queues_are_bounded_and_child_pipe_is_nonblocking(self) -> None:
        self.assertIn("MAX_PENDING_EVENTS = 32", self.source)
        self.assertIn("MAX_PRIORITY_EVENTS = 8", self.source)
        self.assertIn("fcntl.F_SETFL", self.source)
        self.assertIn('len(state["receiver_buffer"]) > 65536', self.source)
        self.assertIn("del output[:written]", self.source)


if __name__ == "__main__":
    unittest.main()
