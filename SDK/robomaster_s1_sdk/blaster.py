from __future__ import annotations

import time

from .transport import GEL_GUN_CONFIG, IR_GUN_CONFIG


class Blaster:
    LED = "led"
    PHYSICAL = "physical"

    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot
        self.gun_type = self.LED

    def set_type(self, gun_type: str) -> None:
        gun_type = gun_type.lower()
        if gun_type not in {self.LED, self.PHYSICAL}:
            raise ValueError("gun_type must be 'led' or 'physical'")
        self.gun_type = gun_type
        if gun_type == self.PHYSICAL:
            sequence = (
                (0x02, 0x09, 0x40, 0x3F, 0x5B, b"\x01"),
                (0x02, 0x09, 0x40, 0x3F, 0x09, bytes.fromhex(GEL_GUN_CONFIG)),
                (0x02, 0x09, 0x40, 0x3F, 0x59, b"\x02"),
                (0x02, 0x09, 0x40, 0x3F, 0x09, bytes.fromhex(GEL_GUN_CONFIG)),
                (0x02, 0x09, 0x40, 0x3F, 0x59, b"\x02"),
            )
        else:
            sequence = (
                (0x02, 0x09, 0x40, 0x3F, 0x09, bytes.fromhex(IR_GUN_CONFIG)),
                (0x02, 0x09, 0x40, 0x3F, 0x59, b"\x02"),
            )
        for sender, receiver, attr, cmdset, cmdid, payload in sequence:
            self._robot.send_duss(sender, receiver, attr, cmdset, cmdid, payload)
            time.sleep(0.006)

    def fire(self, fire_type: str | None = None, times: int = 1) -> bool:
        if fire_type is not None:
            key = fire_type.lower()
            if key in {"ir", "infrared", "led"}:
                self.set_type(self.LED)
            elif key in {"water", "physical", "gel"}:
                self.set_type(self.PHYSICAL)
            else:
                raise ValueError("fire_type must be 'water' or 'ir'")
        for _ in range(max(1, int(times))):
            self._robot.fire()
        return True

    def set_led(self, brightness: int = 255, effect: str = "on") -> bool:
        value = 0 if effect.lower() == "off" else max(0, min(255, int(brightness)))
        self._robot.led.set_color(value, value, value)
        return True
