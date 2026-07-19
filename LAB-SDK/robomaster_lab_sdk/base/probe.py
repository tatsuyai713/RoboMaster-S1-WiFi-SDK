#!/usr/bin/env python3
"""
Minimal RoboMaster S1 UDP probe for Windows-App-style traffic.

This script is intentionally conservative:
- listens for the S1 discovery broadcast on UDP/40927
- opens a local UDP socket for the App control path
- sends a captured App keepalive/probe packet
- sends one small DUSS command wrapped in the App UDP envelope
- prints received packets and any DUSS frames it can decode

Reference used for DUSS CRC and command templates:
https://github.com/RoboMasterS1Challenge/robostacks1
"""

from __future__ import annotations

import argparse
import select
import socket
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable


CRC8_INIT = 119
CRC16_INIT = 13970

CRC8_TABLE = [
    0x00, 0x5e, 0xbc, 0xe2, 0x61, 0x3f, 0xdd, 0x83, 0xc2, 0x9c, 0x7e, 0x20,
    0xa3, 0xfd, 0x1f, 0x41, 0x9d, 0xc3, 0x21, 0x7f, 0xfc, 0xa2, 0x40, 0x1e,
    0x5f, 0x01, 0xe3, 0xbd, 0x3e, 0x60, 0x82, 0xdc, 0x23, 0x7d, 0x9f, 0xc1,
    0x42, 0x1c, 0xfe, 0xa0, 0xe1, 0xbf, 0x5d, 0x03, 0x80, 0xde, 0x3c, 0x62,
    0xbe, 0xe0, 0x02, 0x5c, 0xdf, 0x81, 0x63, 0x3d, 0x7c, 0x22, 0xc0, 0x9e,
    0x1d, 0x43, 0xa1, 0xff, 0x46, 0x18, 0xfa, 0xa4, 0x27, 0x79, 0x9b, 0xc5,
    0x84, 0xda, 0x38, 0x66, 0xe5, 0xbb, 0x59, 0x07, 0xdb, 0x85, 0x67, 0x39,
    0xba, 0xe4, 0x06, 0x58, 0x19, 0x47, 0xa5, 0xfb, 0x78, 0x26, 0xc4, 0x9a,
    0x65, 0x3b, 0xd9, 0x87, 0x04, 0x5a, 0xb8, 0xe6, 0xa7, 0xf9, 0x1b, 0x45,
    0xc6, 0x98, 0x7a, 0x24, 0xf8, 0xa6, 0x44, 0x1a, 0x99, 0xc7, 0x25, 0x7b,
    0x3a, 0x64, 0x86, 0xd8, 0x5b, 0x05, 0xe7, 0xb9, 0x8c, 0xd2, 0x30, 0x6e,
    0xed, 0xb3, 0x51, 0x0f, 0x4e, 0x10, 0xf2, 0xac, 0x2f, 0x71, 0x93, 0xcd,
    0x11, 0x4f, 0xad, 0xf3, 0x70, 0x2e, 0xcc, 0x92, 0xd3, 0x8d, 0x6f, 0x31,
    0xb2, 0xec, 0x0e, 0x50, 0xaf, 0xf1, 0x13, 0x4d, 0xce, 0x90, 0x72, 0x2c,
    0x6d, 0x33, 0xd1, 0x8f, 0x0c, 0x52, 0xb0, 0xee, 0x32, 0x6c, 0x8e, 0xd0,
    0x53, 0x0d, 0xef, 0xb1, 0xf0, 0xae, 0x4c, 0x12, 0x91, 0xcf, 0x2d, 0x73,
    0xca, 0x94, 0x76, 0x28, 0xab, 0xf5, 0x17, 0x49, 0x08, 0x56, 0xb4, 0xea,
    0x69, 0x37, 0xd5, 0x8b, 0x57, 0x09, 0xeb, 0xb5, 0x36, 0x68, 0x8a, 0xd4,
    0x95, 0xcb, 0x29, 0x77, 0xf4, 0xaa, 0x48, 0x16, 0xe9, 0xb7, 0x55, 0x0b,
    0x88, 0xd6, 0x34, 0x6a, 0x2b, 0x75, 0x97, 0xc9, 0x4a, 0x14, 0xf6, 0xa8,
    0x74, 0x2a, 0xc8, 0x96, 0x15, 0x4b, 0xa9, 0xf7, 0xb6, 0xe8, 0x0a, 0x54,
    0xd7, 0x89, 0x6b, 0x35,
]

CRC16_TABLE = [
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf, 0x8c48,
    0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7, 0x1081, 0x0108,
    0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e, 0x9cc9, 0x8d40, 0xbfdb,
    0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876, 0x2102, 0x308b, 0x0210, 0x1399,
    0x6726, 0x76af, 0x4434, 0x55bd, 0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e,
    0xfae7, 0xc87c, 0xd9f5, 0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e,
    0x54b5, 0x453c, 0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd,
    0xc974, 0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3, 0x5285,
    0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a, 0xdecd, 0xcf44,
    0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72, 0x6306, 0x728f, 0x4014,
    0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9, 0xef4e, 0xfec7, 0xcc5c, 0xddd5,
    0xa96a, 0xb8e3, 0x8a78, 0x9bf1, 0x7387, 0x620e, 0x5095, 0x411c, 0x35a3,
    0x242a, 0x16b1, 0x0738, 0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862,
    0x9af9, 0x8b70, 0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e,
    0xf0b7, 0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036, 0x18c1,
    0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e, 0xa50a, 0xb483,
    0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5, 0x2942, 0x38cb, 0x0a50,
    0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd, 0xb58b, 0xa402, 0x9699, 0x8710,
    0xf3af, 0xe226, 0xd0bd, 0xc134, 0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7,
    0x6e6e, 0x5cf5, 0x4d7c, 0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1,
    0xa33a, 0xb2b3, 0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72,
    0x3efb, 0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a, 0xe70e,
    0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1, 0x6b46, 0x7acf,
    0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9, 0xf78f, 0xe606, 0xd49d,
    0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330, 0x7bc7, 0x6a4e, 0x58d5, 0x495c,
    0x3de3, 0x2c6a, 0x1ef1, 0x0f78,
]


# Observed PC -> S1 packets. Solo used db68; Labo used dc68.
APP_PROFILES = {
    "solo": {
        "keepalive": bytes.fromhex(
            "2280db6800000415d846d84600000000"
            "d846d84600000000e846e846000000000000"
        ),
        "preconnect": bytes.fromhex(
            "3080db6800000003d84664006400c005140000640064006400c005140000"
            "640014006400c00514000064000101040102"
        ),
        "duss_outer_prefix": bytes.fromhex(
            "0080db680000040d9048904800000000"
            "30473047000000003047304700000000"
        ),
        "direct_outer_prefix": bytes.fromhex(
            "0080db683847056f304738470000000000010000"
        ),
    },
    "labo": {
        "keepalive": bytes.fromhex(
            "2280dc6800000412886c886c00000000"
            "6048604800000000c84ac84a000000000000"
        ),
        "preconnect": bytes.fromhex(
            "30800267000000d5103864006400c005140000640064006400c005140000"
            "640014006400c00514000064000101040102"
        ),
        "duss_outer_prefix": bytes.fromhex(
            "0080dc680000040ac86dc86d00000000"
            "6048604800000000c84ac84a00000000"
        ),
        "direct_outer_prefix": bytes.fromhex(
            "0080dc68d04a058fc84ad04a0000000000012000"
        ),
    },
}


@dataclass(frozen=True)
class DussCommand:
    name: str
    template: bytes
    description: str


DUSS_COMMANDS = {
    # From robostacks1 command_list.h row 0. This is the safest default:
    # it is a small command-set 0x00 / command-id 0x01 query-like packet.
    "query": DussCommand(
        "query",
        bytes.fromhex("550d04000aff00004000010000"),
        "small cmdset=0x00 cmdid=0x01 query",
    ),
    # Mode packets from robostacks1 command_list.h rows 23-25.
    "normal_mode": DussCommand(
        "normal_mode",
        bytes.fromhex("550e040009c30000403f3f020000"),
        "cmdset=0x3f cmdid=0x3f payload=0x02",
    ),
    "slow_mode": DussCommand(
        "slow_mode",
        bytes.fromhex("550e040009c30000403f3f030000"),
        "cmdset=0x3f cmdid=0x3f payload=0x03",
    ),
    "manual_mode": DussCommand(
        "manual_mode",
        bytes.fromhex("550e040009c30000403f3f040000"),
        "cmdset=0x3f cmdid=0x3f payload=0x04",
    ),
    "wheel_forward_pulse": DussCommand(
        "wheel_forward_pulse",
        bytes.fromhex("551b040009c30000003f6000042000010840000210040300040000"),
        "robostacks1 Move Command template, short wheel pulse",
    ),
    "wheel_stop": DussCommand(
        "wheel_stop",
        bytes.fromhex("551b040009c30000003f6000042000010040000210000300000000"),
        "robostacks1 zero-speed Move Command template",
    ),
    "gimbal_probe": DussCommand(
        "gimbal_probe",
        bytes.fromhex("55140400090400000004690805000000006d0000"),
        "experimental cmdset=0x04 cmdid=0x69 gimbal-side pulse candidate",
    ),
    "gimbal_stop": DussCommand(
        "gimbal_stop",
        bytes.fromhex("5514040009040000000469080500000000010000"),
        "experimental cmdset=0x04 cmdid=0x69 neutral candidate",
    ),
    "solo_neutral": DussCommand(
        "solo_neutral",
        bytes.fromhex("551804000209000000010400000420000108400002100000"),
        "Windows App Solo neutral control cmdset=0x01 cmdid=0x04",
    ),
    "solo_axis_high": DussCommand(
        "solo_axis_high",
        bytes.fromhex("551804000209000000010402000420000108400042100000"),
        "Windows App Solo control payload observed repeatedly near 136s",
    ),
    "solo_axis_low": DussCommand(
        "solo_axis_low",
        bytes.fromhex("5518040002090000000104020004200001084000be0f0000"),
        "Windows App Solo control payload observed repeatedly near 106s",
    ),
}


SOLO_INIT_SEQUENCE = [
    ("version_query", 0x02, 0x28, 0x40, 0x00, 0x01, ""),
    ("mode_fe", 0x02, 0x28, 0x40, 0x3F, 0xFE, "00"),
    ("param_0000", 0x02, 0x28, 0x40, 0x00, 0x4F, "0100000000ffffffff"),
    ("param_03d4", 0x02, 0x28, 0x40, 0x00, 0x4F, "01d4030000ffffffff"),
    ("param_07a8", 0x02, 0x28, 0x40, 0x00, 0x4F, "01a8070000ffffffff"),
    ("sdk_like_0730", 0x02, 0x07, 0x40, 0x07, 0x30, "4a5000004a5000000100"),
    ("param_0b7c", 0x02, 0x28, 0x40, 0x00, 0x4F, "017c0b0000ffffffff"),
    ("app_4801", 0x02, 0x09, 0x40, 0x48, 0x01, "0200000003"),
    ("app_4803_a", 0x02, 0x09, 0x40, 0x48, 0x03, "02010000059f22626809000200c49ac5c409000200fd7b4c7809000200ceceb7ee090002009c00a449090002000100"),
    ("app_4803_b", 0x02, 0x09, 0x40, 0x48, 0x03, "02010000059f22626809000200c49ac5c409000200fd7b4c7809000200ceceb7ee090002009c00a449090002000100"),
    ("param_0f50", 0x02, 0x28, 0x40, 0x00, 0x4F, "01500f0000ffffffff"),
    ("param_1324", 0x02, 0x28, 0x40, 0x00, 0x4F, "0124130000ffffffff"),
    ("param_16f8", 0x02, 0x28, 0x40, 0x00, 0x4F, "01f8160000ffffffff"),
    ("param_1acc", 0x02, 0x28, 0x40, 0x00, 0x4F, "01cc1a0000ffffffff"),
    ("solo_mode_3f04", 0x02, 0x09, 0x00, 0x3F, 0x04, "010301"),
    ("solo_3f77_bulk", 0x02, 0x09, 0x40, 0x3F, 0x77, "040501030004000200"),
    ("solo_3f19", 0x02, 0x03, 0x40, 0x3F, 0x19, "00"),
    ("solo_0032", 0x02, 0x28, 0x40, 0x00, 0x32, "1100"),
    ("solo_3f77_0400", 0x02, 0x09, 0x40, 0x3F, 0x77, "010400"),
    ("solo_3f77_0200", 0x02, 0x09, 0x40, 0x3F, 0x77, "010200"),
    ("version_query_2", 0x02, 0x28, 0x40, 0x00, 0x01, ""),
    ("solo_3f66_c3", 0x02, 0xC3, 0x40, 0x3F, 0x66, "0200"),
    ("solo_3f66_09", 0x02, 0x09, 0x40, 0x3F, 0x66, "0200"),
    ("solo_3fb3", 0x02, 0x09, 0x40, 0x3F, 0xB3, "010438aa4f6a00000000"),
    ("solo_3f59", 0x02, 0x09, 0x40, 0x3F, 0x59, "02"),
    ("solo_3f09_config", 0x02, 0x09, 0x40, 0x3F, 0x09, "0d000000e903000000000000ea03000001000000eb03000020bf0200ec030000b0040000ed03000064000000ef0300000a000000f003000000000000f1030000b80b0000f2030000dc050000060400000100000007040000000000000804000001000000090400000100000005000000dd050000dc050000de050000c4090000df050000b80b0000e0050000b80b00004006000000879303050000004d0400003075000001000000de0500004e0400001027000001000000dd0500004f0400003075000001000000df050000500400001027000001000000e0050000b0040000000000000100000040060000"),
    ("solo_mode_3f04_repeat", 0x02, 0x09, 0x00, 0x3F, 0x04, "010301"),
    ("solo_3f0a", 0x02, 0x09, 0x40, 0x3F, 0x0A, "0100"),
    ("solo_3fa3_a9", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "a9000000000000000000000000000000000000000000000000000000000000000000"),
    ("solo_3fa3_09", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "09000000000000000000000000000000000000000000000000000000000000000000"),
    ("solo_3fa3_hash1", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "01626137646331356139366338346634303865343336633762636137313661653637623231383866363831303062323137"),
    ("solo_3fa3_hash2", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "01636130316464306134343966346338663834343030386363396161393134306535366234376530393337326265356232"),
    ("solo_4804", 0x02, 0x09, 0x40, 0x48, 0x04, "00020a"),
    ("solo_4803_short", 0x02, 0x09, 0x40, 0x48, 0x03, "020a000001973c9bf7090002000a00"),
    ("solo_3fa3_hash1b", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "08626137646331356139366338346634303865343336633762636137313661653637623231383866363831303062323137"),
    ("solo_3fa3_hash2b", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "a8636130316464306134343966346338663834343030386363396161393134306535366234376530393337326265356232"),
]


def crc8(data: bytes, seed: int = CRC8_INIT) -> int:
    value = seed
    for byte in data:
        value = CRC8_TABLE[value ^ byte]
    return value


def crc16(data: bytes, seed: int = CRC16_INIT) -> int:
    value = seed
    for byte in data:
        value = ((value >> 8) ^ CRC16_TABLE[(value ^ byte) & 0xFF]) & 0xFFFF
    return value


def build_duss(command: DussCommand, seq: int) -> bytes:
    frame = bytearray(command.template)
    if len(frame) < 13 or frame[0] != 0x55 or frame[2] != 0x04:
        raise ValueError(f"bad DUSS template for {command.name}")
    frame[3] = crc8(bytes(frame[:3]))
    frame[6] = seq & 0xFF
    frame[7] = (seq >> 8) & 0xFF
    crc = crc16(bytes(frame[:-2]))
    frame[-2] = crc & 0xFF
    frame[-1] = (crc >> 8) & 0xFF
    return bytes(frame)


def wrap_app_duss(duss: bytes, outer_prefix: bytes) -> bytes:
    outer = bytearray(outer_prefix)
    total_len = len(outer) + 2 + len(duss)
    if total_len > 0x7F:
        raise ValueError("wrapped command is larger than expected one-byte length")
    outer[0] = total_len
    return bytes(outer) + struct.pack("<H", len(duss)) + duss


def wrap_app_duss_direct(duss: bytes, outer_prefix: bytes) -> bytes:
    outer = bytearray(outer_prefix)
    total_len = len(outer) + len(duss)
    outer[0] = total_len & 0xFF
    outer[1] = 0x81 if total_len > 0xFF else 0x80
    return bytes(outer) + duss


def make_duss_template(
    sender: int,
    receiver: int,
    attr: int,
    cmdset: int,
    cmdid: int,
    payload_hex: str = "",
) -> bytes:
    payload = bytes.fromhex(payload_hex)
    length = 13 + len(payload)
    return bytes([0x55, length, 0x04, 0x00, sender, receiver, 0x00, 0x00, attr, cmdset, cmdid]) + payload + b"\x00\x00"


def hex_preview(data: bytes, limit: int = 96) -> str:
    text = data[:limit].hex()
    return text + ("..." if len(data) > limit else "")


def parse_duss_frames(data: bytes) -> list[dict[str, object]]:
    frames: list[dict[str, object]] = []
    i = 0
    while i <= len(data) - 13:
        if data[i] != 0x55 or (data[i + 2] & 0xFC) != 0x04:
            i += 1
            continue
        length = data[i + 1] | ((data[i + 2] & 0x03) << 8)
        if length < 13 or i + length > len(data):
            i += 1
            continue
        frame = data[i : i + length]
        header_ok = crc8(frame[:3]) == frame[3]
        body_ok = crc16(frame[:-2]) == int.from_bytes(frame[-2:], "little")
        frames.append(
            {
                "offset": i,
                "length": length,
                "header_crc_ok": header_ok,
                "body_crc_ok": body_ok,
                "sender": frame[4],
                "receiver": frame[5],
                "seq": frame[6] | (frame[7] << 8),
                "attr": frame[8],
                "cmdset": frame[9],
                "cmdid": frame[10],
                "payload": frame[11:-2],
            }
        )
        i += length
    return frames
