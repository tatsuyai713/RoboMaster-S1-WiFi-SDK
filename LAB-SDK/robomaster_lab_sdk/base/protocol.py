from __future__ import annotations

from dataclasses import dataclass
import socket
import struct

from .transport import (
    Dc68Envelope,
    build_control,
    build_duss,
    crc8,
    crc16,
    increment_session,
    make_session,
    make_tick_seed,
    parse_duss_frames,
    parse_robot_broadcast,
)


ROBOT_APP_PORT = 56789
APP_PORT = 45678
ROBOT_CONTROL_PORT = 10607
DEFAULT_LOCAL_CONTROL_PORT = 10609
DEFAULT_INIT_SEQ = 10072
DEFAULT_CONTROL_HZ = 50.0
CONTROL_AFTER_APPID_DELAY = 0.20
GIMBAL_SPEED_SCALE = 120.0


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def open_udp(bind_ip: str, port: int, broadcast: bool = False) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((bind_ip, port))
    sock.setblocking(False)
    return sock


def normalize_appid(value: str) -> str:
    appid = value.strip().lower()
    if len(appid) != 8 or any(ch not in "0123456789abcdef" for ch in appid):
        raise ValueError("AppID must be exactly 8 hex characters, for example b6359877")
    return appid


def build_chassis_velocity_payload(linear_x: float, linear_y: float, angular_z: float = 0.0) -> bytes:
    lx = clamp_int(round(1024 + 256 * linear_x), 0, 2047)
    ly = clamp_int(round(1024 + 256 * linear_y), 0, 2047)
    yaw = clamp_int(round(256 * angular_z), -1024, 1023) & 0x0FFF
    data = bytearray(bytes.fromhex("0004200001084000000000000000"))
    data[0] = ly & 0xFF
    data[1] = ((lx << 3) & 0xF8) | ((ly >> 8) & 0x07)
    data[2] = (data[2] & 0xC0) | ((lx >> 5) & 0x3F)
    data[5] = ((yaw << 4) & 0xF0) | 0x08
    data[6] = (yaw >> 4) & 0xFF
    data[8] = 0x02 | ((yaw << 2) & 0xFF)
    data[9] = (yaw >> 6) & 0xFF
    data[10] = 0x04
    data[11] = 0x0C
    data[12] = 0x00
    data[13] = 0x04
    return bytes(data)


def build_gimbal_velocity_payload(pitch: float, yaw: float) -> bytes:
    pitch_raw = clamp_int(round(-1024 * pitch), -1024, 1023)
    yaw_raw = clamp_int(round(-1024 * yaw), -1024, 1023)
    return bytes.fromhex("0805") + struct.pack("<hh", pitch_raw, yaw_raw)


def looks_like_video_fragment(payload: bytes) -> bool:
    if len(payload) < 28:
        return False
    if payload[0] & 0x80 == 0:
        return False
    return payload[2:4] != b"\x00\x00" and payload[20:24] != b"\x55\x00\x00\x00"


@dataclass(frozen=True)
class GimbalTelemetry:
    raw0: int
    raw1: int
    raw2: int
    raw3: int
    flag: int
    payload_hex: str


@dataclass(frozen=True)
class OdometryTelemetry:
    i0: int
    i1: int
    i2: int
    battery_percent: int | None
    heading_like: float | None
    floats: tuple[float, ...]
    payload_hex: str


@dataclass(frozen=True)
class RobotStats:
    driving_distance_m: int | None = None
    driving_time_sec: int | None = None
    battery_percent: int | None = None
    payload_hex: str = ""


@dataclass(frozen=True)
class ArmorDamageEvent:
    source: str
    sender: int
    receiver: int
    seq: int
    attr: int
    armor: str | None
    impact_id: int | None
    payload_hex: str


ARMOR_SENDER_DIRECTIONS = {
    0x38: "back",
    0x58: "front",
    0x78: "left",
    0x98: "right",
}


def int16_le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<h", data, offset)[0]


def float32_le(data: bytes, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def decode_4808(payload: bytes) -> GimbalTelemetry | OdometryTelemetry | None:
    if len(payload) == 11 and payload[:2] == b"\x00\x0a":
        return GimbalTelemetry(
            raw0=int16_le(payload, 2),
            raw1=int16_le(payload, 4),
            raw2=int16_le(payload, 6),
            raw3=int16_le(payload, 8),
            flag=payload[10],
            payload_hex=payload.hex(),
        )
    if len(payload) == 62:
        floats = tuple(float32_le(payload, offset) for offset in range(26, 62, 4))
        return OdometryTelemetry(
            i0=int16_le(payload, 2),
            i1=int16_le(payload, 4),
            i2=int16_le(payload, 6),
            battery_percent=payload[10],
            heading_like=float32_le(payload, 12),
            floats=floats,
            payload_hex=payload.hex(),
        )
    return None


def decode_3f03(payload: bytes) -> RobotStats | None:
    if len(payload) < 12:
        return None
    return RobotStats(
        driving_distance_m=int.from_bytes(payload[4:8], "little", signed=False),
        driving_time_sec=int.from_bytes(payload[8:12], "little", signed=False),
        payload_hex=payload.hex(),
    )


def decode_armor_damage(
    sender: int,
    receiver: int,
    seq: int,
    attr: int,
    cmdset: int,
    cmdid: int,
    payload: bytes,
) -> ArmorDamageEvent | None:
    if cmdset == 0x3F and cmdid == 0x02:
        return ArmorDamageEvent(
            source="led_gun",
            sender=sender,
            receiver=receiver,
            seq=seq,
            attr=attr,
            armor=ARMOR_SENDER_DIRECTIONS.get(sender),
            impact_id=None,
            payload_hex=payload.hex(),
        )
    if cmdset == 0x3F and cmdid == 0x63 and len(payload) == 1:
        return ArmorDamageEvent(
            source="armor_impact",
            sender=sender,
            receiver=receiver,
            seq=seq,
            attr=attr,
            armor=ARMOR_SENDER_DIRECTIONS.get(sender),
            impact_id=payload[0],
            payload_hex=payload.hex(),
        )
    return None
