from __future__ import annotations

from dataclasses import dataclass
import select
import time

from . import protocol


@dataclass(frozen=True)
class DiscoveredRobot:
    ip: str
    source: tuple[str, int]
    mac: str
    appid: str
    state: str


def discover_robots(timeout: float = 4.0, bind_ip: str = "0.0.0.0") -> list[DiscoveredRobot]:
    """Listen for RoboMaster S1 pairing/status broadcasts and return discovered robots."""
    sock = protocol.open_udp(bind_ip, protocol.APP_PORT, broadcast=True)
    deadline = time.monotonic() + max(0.1, timeout)
    robots: dict[str, DiscoveredRobot] = {}
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select([sock], [], [], 0.20)
            for ready in readable:
                data, addr = ready.recvfrom(65535)
                broadcast = protocol.parse_robot_broadcast(data)
                if broadcast is None:
                    continue
                ip = broadcast.robot_ip or addr[0]
                robots[ip] = DiscoveredRobot(
                    ip=ip,
                    source=addr,
                    mac=broadcast.robot_mac,
                    appid=broadcast.appid_text,
                    state="pairing" if broadcast.is_pairing else "idle",
                )
        return sorted(robots.values(), key=lambda robot: robot.ip)
    finally:
        sock.close()
