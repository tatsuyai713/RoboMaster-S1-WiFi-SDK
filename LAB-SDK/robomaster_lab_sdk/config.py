from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabSdkConfig:
    control_port: int = 40923
    telemetry_port: int = 40924
    control_period_sec: float = 0.02
    telemetry_period_sec: float = 0.02
    command_timeout_sec: float = 0.3
    command_decay_per_tick: float = 0.92
    command_zero_epsilon: float = 0.02
    command_angular_zero_epsilon: float = 0.08
    max_chassis_speed: float = 1.0
    max_chassis_yaw_speed: float = 120.0
    max_gimbal_speed: float = 120.0


DEFAULT_CONFIG = LabSdkConfig()
DEFAULT_CONTROL_PORT = DEFAULT_CONFIG.control_port
DEFAULT_TELEMETRY_PORT = DEFAULT_CONFIG.telemetry_port
