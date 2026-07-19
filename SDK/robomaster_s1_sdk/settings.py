from __future__ import annotations

import struct
import time

from .transport import DUSS_ACTIONS


VOICE_LANGUAGE_IDS = {
    "english": 0x00,
    "en": 0x00,
    "japanese": 0x02,
    "日本語": 0x02,
    "ja": 0x02,
    "deutsch": 0x04,
    "german": 0x04,
    "español": 0x05,
    "spanish": 0x05,
    "한국어": 0x06,
    "korean": 0x06,
    "français": 0x07,
    "french": 0x07,
    "русский": 0x08,
    "russian": 0x08,
}

SPEED_PRESET_PAYLOADS = {
    "slow": "03",
    "medium": "02",
    "fast": "01",
    "custom": "04",
}

CUSTOM_SPEED_PARAMS = (
    ("forward_speed", "810636fe", 1.50),
    ("backward_speed", "d9980ced", 1.50),
    ("starting_accel", "1b175310", 50.0),
    ("braking_accel", "e96d5133", 50.0),
    ("lateral_speed", "6fe6a05e", 1.50),
    ("lateral_starting_accel", "0e1a53a0", 50.0),
    ("lateral_braking_accel", "dc7051c3", 50.0),
)

POWEROFF_PAYLOAD = bytes.fromhex("0002000000000000000000000000")
POWEROFF_KEEP_MODE_PAYLOAD = bytes.fromhex("000300")


class Settings:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def set_voice_language(self, language: str) -> None:
        key = language.strip().lower()
        if key not in VOICE_LANGUAGE_IDS:
            raise ValueError(f"unknown language: {language}")
        self.set_voice_language_id(VOICE_LANGUAGE_IDS[key])

    def set_voice_language_id(self, language_id: int) -> None:
        language_id = max(0, min(255, int(language_id)))
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x16, bytes((language_id,)))

    def set_volume(self, volume: int) -> None:
        volume = max(0, min(80, int(volume)))
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x1B, bytes((volume,)))

    def set_speed_preset(self, preset: str) -> None:
        key = preset.strip().lower()
        if key not in SPEED_PRESET_PAYLOADS:
            raise ValueError("preset must be slow, medium, fast, or custom")
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x3F, bytes.fromhex(SPEED_PRESET_PAYLOADS[key]))

    def set_custom_speed(self, **values: float) -> None:
        self.set_speed_preset("custom")
        for key, param_id, default in CUSTOM_SPEED_PARAMS:
            value = float(values.get(key, default))
            payload = bytes.fromhex(param_id) + struct.pack("<f", value)
            self._robot.send_duss(0x02, 0x09, 0x40, 0x03, 0xF9, payload)
            time.sleep(0.006)

    def send_named_action(self, action: str) -> None:
        """Send a Windows-App-captured DUSS action by name.

        Names are the same keys used by the working Unified app, for example
        video_resolution_0403, video_antiflicker_60, and video_3d_low.
        """
        if action not in DUSS_ACTIONS:
            raise ValueError(f"unknown DUSS action: {action}")
        sender, receiver, attr, cmdset, cmdid, payload_hex = DUSS_ACTIONS[action]
        self._robot.send_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex))

    def set_max_speed(
        self,
        forward: float = 1.50,
        backward: float = 1.50,
        lateral: float = 1.50,
        **extra_values: float,
    ) -> None:
        values = {
            "forward_speed": forward,
            "backward_speed": backward,
            "lateral_speed": lateral,
            **extra_values,
        }
        self.set_custom_speed(**values)

    def set_acceleration(
        self,
        starting: float = 50.0,
        braking: float = 50.0,
        lateral_starting: float = 50.0,
        lateral_braking: float = 50.0,
        **extra_values: float,
    ) -> None:
        values = {
            "starting_accel": starting,
            "braking_accel": braking,
            "lateral_starting_accel": lateral_starting,
            "lateral_braking_accel": lateral_braking,
            **extra_values,
        }
        self.set_custom_speed(**values)

    def set_auto_sleep(self, enabled: bool = True, seconds: int = 60) -> None:
        seconds = max(0, min(0xFFFF, int(seconds)))
        payload = bytes((0x01 if enabled else 0x00,)) + seconds.to_bytes(2, "little")
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x4A, payload)

    def query_auto_sleep(self) -> None:
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x4B, b"")

    def poweroff(self) -> None:
        """Power off the robot using the Windows App-compatible DUSS sequence."""
        self._robot.send_duss(0x02, 0x09, 0x00, 0x3F, 0x04, POWEROFF_KEEP_MODE_PAYLOAD)
        self._robot.send_duss(0x02, 0x0B, 0x40, 0x00, 0x0B, POWEROFF_PAYLOAD)
