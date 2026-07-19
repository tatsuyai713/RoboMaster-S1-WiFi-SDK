from __future__ import annotations

import ftplib

from robomaster_s1_sdk import discover_robots
from robomaster_s1_sdk.qr import build_wifi_qr_data

from . import config

CONNECTION_USB_RNDIS = "rndis"
CONNECTION_WIFI_AP = "ap"
CONNECTION_WIFI_STA = "sta"
CONNECTION_PROTO_TCP = "tcp"
CONNECTION_PROTO_UDP = "udp"


def get_local_ip():
    return config.LOCAL_IP_STR


def scan_robot_ip(user_sn=None, timeout=3.0):  # noqa: ANN001
    robots = discover_robots(timeout=timeout)
    return robots[0].ip if robots else None


def scan_robot_ip_list(timeout=3.0):
    return [item.ip for item in discover_robots(timeout=timeout)]


class ConnectionHelper:
    """Official-SDK-shaped QR/discovery helper used by robomaster_ros tools."""

    def __init__(self):
        self._appid = "b6359877"

    def build_qrcode_string(self, ssid, password):  # noqa: ANN001
        return build_wifi_qr_data(
            ssid=str(ssid),
            password=str(password),
            appid=str(self._appid),
        ).qr_text

    def wait_for_connection(self, timeout=30.0):
        return bool(scan_robot_ip(timeout=float(timeout)))


class FtpConnection:
    """Small compatibility wrapper; robomaster_ros may replace this class."""

    def __init__(self, ip, timeout=3.0):  # noqa: ANN001
        self._ftp = ftplib.FTP()
        self._ftp.connect(str(ip), 21, timeout=float(timeout))
        self._ftp.login("anonymous", "")

    def upload(self, src, target):  # noqa: ANN001
        with open(src, "rb") as stream:
            self._ftp.storbinary(f"STOR {target}", stream)
        return True

    def close(self):
        try:
            self._ftp.quit()
        except Exception:
            self._ftp.close()


class Connection:
    def __init__(self, host_addr, target_addr, proto="v1", protocol=CONNECTION_PROTO_UDP):
        self._host_addr = host_addr
        self._target_addr = target_addr
        self._proto = proto
        self._protocol = protocol

    @property
    def target_addr(self):
        return self._target_addr

    @property
    def protocol(self):
        return self._protocol


__all__ = [
    "Connection",
    "ConnectionHelper",
    "FtpConnection",
    "get_local_ip",
    "scan_robot_ip",
    "scan_robot_ip_list",
]
