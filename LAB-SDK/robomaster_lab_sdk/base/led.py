from __future__ import annotations


class LED:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    def set_color(self, r: int, g: int, b: int) -> None:
        payload = bytes((
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))),
            0x00,
        ))
        self._robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x34, payload)

    def set_led(
        self,
        comp: str = "all",
        r: int = 255,
        g: int = 255,
        b: int = 255,
        effect: str = "on",
        freq: int = 1,
    ) -> bool:
        if effect.lower() == "off":
            self.set_color(0, 0, 0)
        else:
            self.set_color(r, g, b)
        return True

    def set_gimbal_led(self, r: int = 255, g: int = 255, b: int = 255, effect: str = "on", freq: int = 1) -> bool:
        return self.set_led("gimbal", r, g, b, effect, freq)
