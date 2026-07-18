from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_selected_package_path = None
for _entry in sys.path:
    candidate = Path(_entry).resolve() / "robomaster"
    if candidate.exists() and candidate != Path(__file__).resolve().parent:
        _selected_package_path = candidate
        break

if _selected_package_path is None:
    _selected_package_path = _ROOT / "SDK" / "robomaster"

if _selected_package_path.exists():
    _selected_sdk_root = _selected_package_path.parent
    if str(_selected_sdk_root) not in sys.path:
        sys.path.insert(0, str(_selected_sdk_root))
    __path__.append(str(_selected_package_path))

from . import battery, blaster, camera, chassis, gimbal, led, robot  # noqa: E402

__all__ = ["battery", "blaster", "camera", "chassis", "gimbal", "led", "robot"]
