from __future__ import annotations

import logging
import time

from . import (
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
IS_S1_WIFI_SDK = True
IS_LAB_SDK = False


def enable_logging_to_file() -> None:
    logger.setLevel(logging.INFO)
    filename = "RoboMasterSDK_{0}_log.txt".format(
        time.strftime("%Y%m%d%H%M%S", time.localtime())
    )
    logger.addHandler(logging.FileHandler(filename))


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
    "IS_S1_WIFI_SDK",
    "IS_LAB_SDK",
]
