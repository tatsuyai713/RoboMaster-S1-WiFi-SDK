from __future__ import annotations

from pathlib import Path
import logging
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

from . import (  # noqa: E402
    action,
    armor,
    battery,
    blaster,
    camera,
    chassis,
    client,
    config,
    conn,
    gimbal,
    led,
    media,
    protocol,
    robot,
    util,
)

logger = logging.getLogger("sdk")
_selected_root_name = _selected_package_path.parent.name
IS_LAB_SDK = _selected_root_name == "LAB-SDK"
IS_S1_WIFI_SDK = _selected_root_name == "SDK"

__all__ = [
    "action",
    "armor",
    "battery",
    "blaster",
    "camera",
    "chassis",
    "client",
    "config",
    "conn",
    "gimbal",
    "led",
    "media",
    "protocol",
    "robot",
    "util",
    "logger",
    "IS_LAB_SDK",
    "IS_S1_WIFI_SDK",
]
