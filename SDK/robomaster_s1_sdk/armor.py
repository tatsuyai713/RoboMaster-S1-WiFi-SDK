from __future__ import annotations


ARMOR_ID_TO_COMP = {
    1: "bottom_back",
    2: "bottom_front",
    3: "bottom_left",
    4: "bottom_right",
    5: "top_left",
    6: "top_right",
}
ARMOR_COMP_TO_ID = {value: key for key, value in ARMOR_ID_TO_COMP.items()}
ARMOR_NAME_TO_ID = {
    "back": 1,
    "front": 2,
    "left": 3,
    "right": 4,
}


class Armor:
    def __init__(self, robot) -> None:  # noqa: ANN001
        self._robot = robot

    @staticmethod
    def id2comp(armor_id: int) -> str:
        return ARMOR_ID_TO_COMP[int(armor_id)]

    @staticmethod
    def comp2id(comp: str) -> int:
        return ARMOR_COMP_TO_ID[comp]

    def set_hit_sensitivity(self, comp: str = "all", sensitivity: int = 5) -> bool:
        raise NotImplementedError("Armor hit sensitivity is not mapped for the S1 Wi-Fi protocol yet")

    def sub_hit_event(self, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False

        def _call(event):
            armor_id = ARMOR_NAME_TO_ID.get(event.armor or "", event.impact_id or 0)
            hit_type = "ir" if event.source == "ir_hit" else "water"
            callback((armor_id, hit_type), *args, **kw)

        self._robot.on("armor_damage", _call)
        return True

    def sub_ir_event(self, callback=None, *args, **kw) -> bool:  # noqa: ANN001
        if callback is None:
            return False

        def _call(event):
            if event.source == "ir_hit":
                callback(1, *args, **kw)

        self._robot.on("armor_damage", _call)
        return True

    def unsub_hit_event(self) -> bool:
        return True

    def unsub_ir_event(self) -> bool:
        return True
