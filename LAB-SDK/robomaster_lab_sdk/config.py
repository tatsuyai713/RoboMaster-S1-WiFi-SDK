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
    connect_settle_sec: float = 0.5
    lab_mode_settle_sec: float = 1.0
    upload_settle_sec: float = 0.5
    program_start_settle_sec: float = 1.0
    upload_retry_timeout_sec: float = 5.0
    bridge_ready_timeout_sec: float = 5.0
    bridge_probe_interval_sec: float = 0.1

    def __post_init__(self) -> None:
        for name in ("control_port", "telemetry_port"):
            value = int(getattr(self, name))
            if not 1 <= value <= 65535:
                raise ValueError(f"{name} must be in 1..65535")
        for name in ("control_period_sec", "telemetry_period_sec"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be greater than zero")
        if float(self.command_timeout_sec) < 0.0:
            raise ValueError("command_timeout_sec must not be negative")
        if not 0.0 <= float(self.command_decay_per_tick) <= 1.0:
            raise ValueError("command_decay_per_tick must be in 0..1")
        for name in ("command_zero_epsilon", "command_angular_zero_epsilon"):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must not be negative")
        for name in ("max_chassis_speed", "max_chassis_yaw_speed", "max_gimbal_speed"):
            if float(getattr(self, name)) <= 0.0:
                raise ValueError(f"{name} must be greater than zero")
        for name in (
            "connect_settle_sec",
            "lab_mode_settle_sec",
            "upload_settle_sec",
            "program_start_settle_sec",
            "upload_retry_timeout_sec",
            "bridge_ready_timeout_sec",
            "bridge_probe_interval_sec",
        ):
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must not be negative")


DEFAULT_CONFIG = LabSdkConfig()
DEFAULT_CONTROL_PORT = DEFAULT_CONFIG.control_port
DEFAULT_TELEMETRY_PORT = DEFAULT_CONFIG.telemetry_port
