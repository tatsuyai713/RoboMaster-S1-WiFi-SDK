from __future__ import annotations

import ftplib

from robomaster_s1_sdk import discover_robots
from robomaster_s1_sdk.qr import build_wifi_qr_data

CONNECTION_USB_RNDIS = "rndis"
CONNECTION_WIFI_AP = "ap"
CONNECTION_WIFI_STA = "sta"
CONNECTION_PROTO_TCP = "tcp"
CONNECTION_PROTO_UDP = "udp"


def scan_robot_ip(user_sn=None, timeout=3.0):  # noqa: ANN001
    robots = discover_robots(timeout=float(timeout))
    return robots[0].ip if robots else None


def scan_robot_ip_list(timeout=3.0):
    return [item.ip for item in discover_robots(timeout=float(timeout))]


class ConnectionHelper:
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
    def __init__(self, ip, timeout=3.0):  # noqa: ANN001
        self._ftp = ftplib.FTP()
        self._ftp.connect(str(ip), 21, timeout=float(timeout))
        self._ftp.login("anonymous", "")

    def upload(self, src, target):  # noqa: ANN001
        with open(src, "rb") as stream:
            self._ftp.storbinary("STOR {0}".format(target), stream)
        return True

    def close(self):
        try:
            self._ftp.quit()
        except Exception:
            self._ftp.close()
