from __future__ import annotations


class LED:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def set_led(self, comp: str = "all", r: int = 255, g: int = 255, b: int = 255, effect: str = "on", freq: int = 1) -> bool:
        self._robot.bridge.set_led(comp=comp, r=int(r), g=int(g), b=int(b), effect=effect, freq=int(freq))
        return True

    def set_gimbal_led(self, r: int = 255, g: int = 255, b: int = 255, effect: str = "on", freq: int = 1) -> bool:
        return self.set_led("gimbal", r, g, b, effect, freq)

    def turn_off(self, comp: str = "all") -> bool:
        self._robot.bridge.call("led", "turn_off", comp=comp)
        return True

    def set_flash(self, comp: str = "all", freq: int = 1) -> bool:
        self._robot.bridge.call("led", "set_flash", comp=comp, freq=int(freq))
        return True

    def set_single_led(self, comp: str = "all", led_list=None, effect: str = "on") -> bool:  # noqa: ANN001
        self._robot.bridge.call("led", "set_single_led", comp=comp, led_list=list(led_list or []), effect=effect)
        return True
