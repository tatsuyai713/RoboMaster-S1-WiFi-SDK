from __future__ import annotations

import logging
import time

from . import (
    action,
    ai_module,
    algo,
    armor,
    battery,
    blaster,
    camera,
    chassis,
    client,
    config,
    conn,
    dds,
    exceptions,
    event,
    flight,
    gimbal,
    gripper,
    led,
    media,
    module,
    protocol,
    robot,
    robotic_arm,
    sensor,
    sensor_adaptor,
    servo,
    uart,
    util,
    version,
    vision,
)

logger = logging.getLogger("sdk")
IS_LAB_SDK = True


def enable_logging_to_file() -> None:
    logger.setLevel(logging.INFO)
    filename = "RoboMasterSDK_{0}_log.txt".format(time.strftime("%Y%m%d%H%M%S", time.localtime()))
    handler = logging.FileHandler(filename)
    logger.addHandler(handler)


__all__ = [
    "ai_module",
    "algo",
    "action",
    "armor",
    "battery",
    "blaster",
    "camera",
    "chassis",
    "client",
    "config",
    "conn",
    "dds",
    "exceptions",
    "event",
    "flight",
    "gimbal",
    "gripper",
    "led",
    "media",
    "module",
    "protocol",
    "robot",
    "robotic_arm",
    "sensor",
    "sensor_adaptor",
    "servo",
    "uart",
    "util",
    "version",
    "vision",
    "logger",
    "IS_LAB_SDK",
]
