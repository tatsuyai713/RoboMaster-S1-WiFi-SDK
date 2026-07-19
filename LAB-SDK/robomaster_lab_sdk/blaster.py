from __future__ import annotations


INFRARED_FIRE = "ir"
WATER_FIRE = "water"


class Blaster:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def fire(self, fire_type: str = WATER_FIRE, times: int = 1) -> bool:
        gun_type = "led" if str(fire_type).lower() in {"ir", "infrared", "led"} else "physical"
        accepted = True
        for _ in range(max(1, int(times))):
            accepted = self._robot.send_fire(gun_type) and accepted
        return accepted

    def set_led(self, brightness: int = 255, effect: str = "on") -> bool:
        return self._robot.bridge.call(
            "blaster",
            "set_led",
            brightness=int(brightness),
            effect=effect,
        )
