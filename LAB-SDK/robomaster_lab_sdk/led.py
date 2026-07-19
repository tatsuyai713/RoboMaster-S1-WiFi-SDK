from __future__ import annotations


class LED:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def set_led(self, comp: str = "all", r: int = 0, g: int = 0, b: int = 0, effect: str = "on", freq: int = 1) -> bool:
        target = str(comp).lower()
        if target not in {
            "all",
            "bottom",
            "bottom_all",
            "bottom_left",
            "bottom_right",
            "bottom_front",
            "bottom_back",
            "top",
            "top_all",
            "top_left",
            "top_right",
            "gimbal",
        }:
            raise ValueError("unsupported LED component")
        return self._robot.bridge.set_led(comp=target, r=int(r), g=int(g), b=int(b), effect=effect, freq=int(freq))

    def set_gimbal_led(
        self,
        comp: str = "top_all",
        r: int = 255,
        g: int = 255,
        b: int = 255,
        led_list=[0, 1, 2, 3],
        effect: str = "on",
    ) -> bool:
        accepted = self.set_led(comp, r, g, b, "on")
        return self.set_single_led(comp, led_list, effect) and accepted

    def turn_off(self, comp: str = "all") -> bool:
        return self._robot.bridge.call("led", "turn_off", comp=comp)

    def set_flash(self, comp: str = "all", freq: int = 1) -> bool:
        return self._robot.bridge.call("led", "set_flash", comp=comp, freq=int(freq))

    def set_single_led(self, comp: str = "all", led_list=None, effect: str = "on") -> bool:  # noqa: ANN001
        return self._robot.bridge.call("led", "set_single_led", comp=comp, led_list=list(led_list or []), effect=effect)
