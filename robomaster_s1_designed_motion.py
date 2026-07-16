#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets
import select
import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path

from robomaster_s1_probe import crc8, crc16, parse_duss_frames


DISCOVERY_TOKEN = bytes.fromhex("5de771ca63d8ad6e68a1e94284ddd37ba119b20fc37d9f81")
DEFAULT_PAIR_HASH1 = "ba7dc15a96c84f408e436c7bca716ae67b2188f68100b217"
DEFAULT_PAIR_HASH2 = "ca01dd0a449f4c8f844008cc9aa9140e56b47e09372be5b2"


@dataclass(frozen=True)
class RobotBroadcast:
    raw: bytes
    decrypted: bytes
    is_valid: bool
    is_pairing: bool
    robot_ip: str
    robot_mac: str
    appid_bytes: bytes

    @property
    def appid_text(self) -> str:
        if self.appid_bytes == b"\x00" * 8:
            return "00000000"
        return self.appid_bytes.decode("ascii", errors="replace")


def simple_crypt(data: bytes) -> bytes:
    key = 7
    out = bytearray()
    for byte in data:
        out.append(byte ^ key)
        key = ((key + 7) ^ 178) & 0xFF
    return bytes(out)


def parse_robot_broadcast(data: bytes) -> RobotBroadcast | None:
    if len(data) != 24:
        return None
    decrypted = simple_crypt(data)
    if decrypted[:2] != b"\x5a\x5b":
        return None
    flags = decrypted[2]
    robot_ip = ".".join(str(part) for part in decrypted[6:10])
    mac = ":".join(f"{part:02X}" for part in decrypted[10:16])
    return RobotBroadcast(
        raw=data,
        decrypted=decrypted,
        is_valid=True,
        is_pairing=bool(flags & 0x01),
        robot_ip=robot_ip,
        robot_mac=mac,
        appid_bytes=decrypted[16:24],
    )


def make_appid(value: str) -> bytes:
    appid = value.strip().lower()
    if len(appid) != 8 or any(ch not in "0123456789abcdef" for ch in appid):
        raise SystemExit("--appid must be exactly 8 lowercase/uppercase hex characters")
    return appid.encode("ascii")


def open_udp(bind_ip: str, port: int, broadcast: bool = False) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((bind_ip, port))
    sock.setblocking(False)
    return sock


def send_appid(sock: socket.socket, appid: bytes, robot_ip: str, robot_port: int, reason: str) -> None:
    sock.sendto(appid, (robot_ip, robot_port))
    print(f"[send] AppID {appid.decode('ascii')} -> {robot_ip}:{robot_port} ({reason})")

PRECONNECT_TEMPLATE = bytes.fromhex(
    "3080dc6800000004d84664006400c005140000640064006400c005140000"
    "640014006400c00514000064000101040102"
)
NEUTRAL_PAYLOAD = bytes.fromhex("0000042000010840000210")
GIMBAL_NEUTRAL_PAYLOAD = NEUTRAL_PAYLOAD
LED_GUN_TRIGGER_NEUTRAL_PAYLOAD = bytes.fromhex("0000042000010840000230")

# Windows App Solo control payloads from 66.7720087-67.4328611 s in
# initial-connect-solo-damage1time.pcapng. The robot reported the one-off
# 0x3f/0x02 damage event at 67.1045630 s while this sequence was active.
IR_GUN_CONTROL_SEQUENCE = tuple(
    bytes.fromhex(value)
    for value in (
        "020004200001084000ce11", "020004200001283f001613", "020004200001283f001613",
        "0200042000010840008210", "0200042000010840008210", "020004200001d840000a11",
        "020004200001a841008210", "020004200001d840008210", "0200042000017842008230",
        "020004200001d840004230", "020004200001a841008230", "020004200001d840004230",
        "020004200001d840000230", "020004200001a841004230", "020004200001a841004230",
        "020004200001a841004230", "0000042000010840000230", "020004200001d840000210",
        "020004200001d840000210", "020004200001a841004210", "0200042000017842004210",
        "0000042000010840000210", "020004200001d840000210", "0000042000010840000210",
        "020004200001d840000230", "0000042000010840000230", "0000042000010840000230",
        "0000042000010840000230", "0000042000010840000230", "020004200001d840000230",
        "0000042000010840000230", "0000042000010840000230", "0000042000010840000210",
        "020004200001d840000210", "0000042000010840000210", "020004200001084000be0f",
        "0000042000010840000210", "020004200001084000be2f", "020004200001084000be2f",
        "020004200001084000be2f", "0000042000010840000230", "020004200001d840000230",
        "020004200001d840000230", "0000042000010840000230",
    )
)

# Decoded DUSS commands from the working IR-GUN initialization block. These
# are rebuilt with the active sequence instead of replaying captured packets.
IR_GUN_CONFIG = "0d000000e903000000000000ea03000001000000eb03000020bf0200ec030000b0040000ed03000064000000ef0300000a000000f003000000000000f1030000b80b0000f2030000dc050000060400000100000007040000000000000804000001000000090400000100000005000000dd050000dc050000de050000c4090000df050000b80b0000e0050000b80b00004006000000879303050000004d0400003075000001000000de0500004e0400001027000001000000dd0500004f0400003075000001000000df050000500400001027000001000000e0050000b0040000000000000100000040060000"
GEL_GUN_CONFIG = "0d000000e903000000000000ea03000000000000eb03000020bf0200ec030000b0040000ed03000064000000ef0300000a000000f003000000000000f1030000b80b0000f2030000dc050000060400000100000007040000010000000804000001000000090400000100000005000000dd050000dc050000de050000c4090000df050000b80b0000e0050000b80b00004006000000879303050000004d0400003075000001000000de0500004e0400001027000001000000dd0500004f0400003075000001000000df050000500400001027000001000000e0050000b0040000000000000100000040060000"
IR_GUN_INIT_COMMANDS = (
    (0x02, 0x09, 0x40, 0x3F, 0x77, "010301", "2480945d00ee0586f8ed00ee000000002d010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x77, "010401", "2480945d08ee058ef8ed08ee000000002e010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x77, "010201", "2480945d10ee059608ee10ee000000002f014000"),
    (0x02, 0x09, 0x40, 0x3F, 0xB3, "0104552c536a00000000", "2b80945d18ee059108ee18ee0000000030010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x77, "010401", "2480945d20ee05a610ee20ee0000000031010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x77, "010201", "2480945d28ee05ae10ee28ee0000000032014000"),
    (0x02, 0x09, 0x40, 0x3F, 0x5B, "01", "2280945d30ee05b018ee30ee0000000033014000"),
    (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG, "0d81945d38ee059618ee38ee0000000034010000"),
    (0x02, 0x09, 0x00, 0x3F, 0x04, "010301", "2480945d40ee05c618ee40ee0000000035016000"),
    (0x02, 0x09, 0x40, 0x3F, 0x59, "02", "2280945d48ee05c840ee48ee0000000036010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG, "0d81945d50ee05fe40ee50ee0000000037010000"),
    (0x02, 0x09, 0x00, 0x3F, 0x04, "010301", "2480945d58ee05de40ee58ee0000000038010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x0A, "0100", "2380945d60ee05e140ee60ee0000000039010000"),
    (0x02, 0x01, 0x40, 0x02, 0x34, "0900006400", "2680945d68ee05ec40ee68ee000000003a010000"),
    (0x02, 0x09, 0x40, 0x3F, 0x59, "02", "2280945d70ee05f040ee70ee000000003b010000"),
    (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000", "2380945d78ee05f940ee78ee000000003c010000"),
    (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000", "2380945d80ee050178ee80ee000000003d010000"),
)

CONTROL_PAYLOADS = {
    # Confirmed visible Solo chassis motion.  Do not replace these with
    # stronger sampled stick values unless the button direction is rechecked
    # on the real S1; the GUI labels depend on this mapping.
    "forward": bytes.fromhex("0100542a00010840000210"),
    "back": bytes.fromhex("01b6022000010840000210"),
    "left": bytes.fromhex("0100b41500010840000210"),
    "right": bytes.fromhex("014a052000010840000210"),
    # Captured in connect-solo.pcapng during replay-visible gimbal motion.
    # The last state byte is 0x30, while chassis stick packets use 0x10.
    "gimbal_left": bytes.fromhex("020004200001283f000210"),
    "gimbal_right": bytes.fromhex("020004200001d840000210"),
    "gimbal_up": bytes.fromhex("0200042000010840004210"),
    "gimbal_down": bytes.fromhex("020004200001084000c610"),
    "gimbal_stop": GIMBAL_NEUTRAL_PAYLOAD,
    "trigger_button": bytes.fromhex("0000042000010840000230"),
    "trigger_button2": bytes.fromhex("0200042000010840000212"),
    "trigger_button3": bytes.fromhex("0200042000010840000231"),
    "stop": NEUTRAL_PAYLOAD,
}

DUSS_ACTIONS = {
    # Inferred from RoboMasterS1Challenge/robostacks1 command_list.h.
    # These are experimental on the UDP App path.
    # CAN-hack derived blaster module commands targeting module 0x17.
    "ir_fire": (0x02, 0x17, 0x00, 0x3F, 0x51, "11"),
    "gel_fire": (0x02, 0x17, 0x00, 0x3F, 0x51, "01"),
    "physical_fire": (0x02, 0x17, 0x00, 0x3F, 0x51, "01"),
    "physical_ir_fire": (0x02, 0x17, 0x00, 0x3F, 0x51, "11"),
    "physical_fire_once": (0x02, 0x17, 0x00, 0x3F, 0x51, "0101"),
    "physical_fire_twice": (0x02, 0x17, 0x00, 0x3F, 0x51, "0102"),
    "physical_ir_once": (0x02, 0x17, 0x00, 0x3F, 0x51, "1101"),
    "physical_fire_type2": (0x02, 0x17, 0x00, 0x3F, 0x51, "0201"),
    "physical_fire_type0": (0x02, 0x17, 0x00, 0x3F, 0x51, "0001"),
    "physical_fire_ack": (0x02, 0x17, 0x40, 0x3F, 0x51, "0101"),
    "physical_fire_chassis": (0x02, 0x09, 0x00, 0x3F, 0x51, "0101"),
    "physical_fire_gimbal": (0x02, 0x04, 0x00, 0x3F, 0x51, "0101"),
    "physical_fire_controller": (0x02, 0x09, 0x40, 0x3F, 0xB3, "03040000000000000000"),
    "physical_fire_controller2": (0x02, 0x09, 0x40, 0x3F, 0xB3, "02040100000000000000"),
    "physical_fire_controller3": (0x02, 0x09, 0x40, 0x3F, 0xB3, "02040001000000000000"),
    "physical_fire_controller4": (0x02, 0x09, 0x40, 0x3F, 0xB3, "010438aa4f6a00000000"),
    "physical_trigger_button": (0x02, 0x09, 0x00, 0x01, 0x04, "0200042000010840000232"),
    "physical_trigger_button2": (0x02, 0x09, 0x00, 0x01, 0x04, "0200042000010840000212"),
    "physical_trigger_button3": (0x02, 0x09, 0x00, 0x01, 0x04, "0200042000010840000231"),
    "video_resolution_0a03": (0x02, 0x01, 0x40, 0x02, 0x18, "0a03000000"),
    "video_resolution_0403": (0x02, 0x01, 0x40, 0x02, 0x18, "0403000000"),
    "video_antiflicker_50": (0x02, 0x01, 0x40, 0x02, 0x46, "01"),
    "video_antiflicker_60": (0x02, 0x01, 0x40, 0x02, 0x46, "02"),
    "video_3d_low": (0x02, 0x01, 0x40, 0x02, 0x46, "00"),
    "video_3d_medium": (0x02, 0x01, 0x40, 0x02, 0x46, "01"),
    "video_3d_high": (0x02, 0x01, 0x40, 0x02, 0x46, "02"),
    "blaster_prep": (0x02, 0x17, 0x00, 0x3F, 0x55, "7300ff000128000000"),
    "blaster_enable": (0x02, 0x17, 0x00, 0x3F, 0x55, "01"),
    "blaster_enable_ack": (0x02, 0x17, 0x40, 0x3F, 0x55, "01"),
    # Seen in connect-solo.pcapng around Solo setup / blaster interaction.
    "pcap_mode_010201": (0x02, 0x09, 0x40, 0x3F, 0x77, "010201"),
    "pcap_mode_010301": (0x02, 0x09, 0x40, 0x3F, 0x77, "010301"),
    "pcap_mode_010401": (0x02, 0x09, 0x40, 0x3F, 0x77, "010401"),
    "pcap_mode_010300": (0x02, 0x09, 0x40, 0x3F, 0x77, "010300"),
    "pcap_mode_010400": (0x02, 0x09, 0x40, 0x3F, 0x77, "010400"),
    "pcap_mode_010200": (0x02, 0x09, 0x40, 0x3F, 0x77, "010200"),
    "pcap_mode_000300": (0x02, 0x09, 0x00, 0x3F, 0x04, "000300"),
    "pcap_cmd_3f57": (0x02, 0x09, 0x40, 0x3F, 0x57, ""),
    "pcap_cmd_3f1f": (0x02, 0x01, 0x40, 0x3F, 0x1F, ""),
    "pcap_fire_0234": (0x02, 0x01, 0x40, 0x02, 0x34, "0900006400"),
    "pcap_fire_a3": (0x02, 0xF1, 0x40, 0x0A, 0xA3, "0000"),
    "pcap_blaster_on": (0x02, 0x09, 0x40, 0x3F, 0xB3, "02040000000000000000"),
    # Battle/Solo rule toggles observed in WinApp logs.  Kept for experiments;
    # the unified GUI does not expose a cooldown toggle.
    "battle_rule_stage_040300": (0x02, 0x09, 0x00, 0x3F, 0x04, "040300"),
    "battle_rule_stage_060301": (0x02, 0x09, 0x00, 0x3F, 0x04, "060301"),
    "battle_rule_enable": (0x02, 0x09, 0x40, 0x3F, 0x0A, "0100"),
    "battle_rule_team_red": (0x02, 0x09, 0x40, 0x3F, 0x34, "c8000000"),
    "battle_rule_keepalive": (0x02, 0x09, 0x00, 0x3F, 0x04, "090301"),
    "battle_rule_gun_config": (0x02, 0x09, 0x40, 0x3F, 0x09, IR_GUN_CONFIG),
    "battle_rule_gun_enable": (0x02, 0x09, 0x40, 0x3F, 0x59, "02"),
    "solo_rule_stage_000300": (0x02, 0x09, 0x00, 0x3F, 0x04, "000300"),
    "solo_rule_stage_010301": (0x02, 0x09, 0x00, 0x3F, 0x04, "010301"),
    "solo_rule_disable": (0x02, 0x09, 0x40, 0x3F, 0x59, "00"),
    "solo_rule_exit_battle": (0x02, 0x09, 0x40, 0x3F, 0xB3, "06040000000000000000"),
}

GUN_ACTIONS = {"gun"}


SUCCESS_SOLO_SETUP_SEQUENCE = (
    ("version_query", "direct", 0x02, 0x28, 0x40, 0x00, 0x01, "", "2180945da0ec052198eca0ec0000000001010000"),
    ("mode_fe", "direct", 0x02, 0x28, 0x40, 0x3F, 0xFE, "00", "2280945da8ec052a98eca8ec0000000002010000"),
    ("param_0000", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "0100000000ffffffff", "2a80945db0ec053aa8ecb0ec0000000003014036"),
    ("param_03d4", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "01d4030000ffffffff", "2a80945db8ec0532b0ecb8ec0000000004010000"),
    ("sdk_like_0730", "direct", 0x02, 0x07, 0x40, 0x07, 0x30, "4a5000004a5000000100", "2b80945dc0ec054bb0ecc0ec0000000005010000"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047740ed40ed00000000c8ecc8ec00000000b8ecd0ec000000001800"),
    ("param_07a8", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "01a8070000ffffffff", "2a80945dc8ec0542b8ecc8ec0000000006010000"),
    ("param_0b7c", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "017c0b0000ffffffff", "2a80945dd0ec055ab8ecd0ec0000000007010000"),
    ("param_0f50", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "01500f0000ffffffff", "2a80945dd8ec0552d0ecd8ec0000000008010000"),
    ("param_1324", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "0124130000ffffffff", "2a80945de0ec056ad0ece0ec0000000009016000"),
    ("param_16f8", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "01f8160000ffffffff", "2a80945de8ec0562d8ece8ec000000000a010000"),
    ("param_1acc", "direct", 0x02, 0x28, 0x40, 0x00, 0x4F, "01cc1a0000ffffffff", "2a80945df0ec057ad8ecf0ec000000000b010000"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d00000477a0eda0ed00000000f0ecf0ec00000000f0ecf0ec000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047768ee68ee00000000f0ecf0ec00000000f0ecf0ec000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d00000477d0eed0ee00000000f0ecf0ec00000000f0ecf0ec000000001800"),
    ("app_4801", "direct", 0x02, 0x09, 0x40, 0x48, 0x01, "0200000003", "2680945df8ec057ef0ecf8ec000000000c010000"),
    ("app_4804_enter", "direct", 0x02, 0x09, 0x40, 0x48, 0x04, "000201", "2480945d00ed0585f0ec00ed000000000d010000"),
    ("app_4803_a", "direct", 0x02, 0x09, 0x40, 0x48, 0x03, "02010000059f22626809000200c49ac5c409000200fd7b4c7809000200ceceb7ee090002009c00a449090002000100", "5080945d08ed05f9f0ec08ed000000000e010000"),
    ("app_4803_b", "direct", 0x02, 0x09, 0x40, 0x48, 0x03, "02010000059f22626809000200c49ac5c409000200fd7b4c7809000200ceceb7ee090002009c00a449090002000100", "5080945d10ed05e1f0ec10ed000000000f010000"),
    ("solo_mode_3f04", "direct", 0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945d18ed059df0ec18ed0000000010010000"),
    ("solo_3f77", "direct", 0x02, 0x09, 0x40, 0x3F, 0x77, "010500", "2480945d20ed05a5f0ec20ed0000000011010000"),
    ("solo_3f19", "direct", 0x02, 0x03, 0x40, 0x3F, 0x19, "00", "2280945d28ed05abf0ec28ed0000000012010000"),
    ("version_query_2", "direct", 0x02, 0x28, 0x40, 0x00, 0x01, "", "2180945d30ed05b0f0ec30ed0000000013014000"),
    ("solo_3f66_c3", "direct", 0x02, 0xC3, 0x40, 0x3F, 0x66, "0200", "2380945d38ed05baf0ec38ed0000000014016040"),
    ("solo_3f66_09", "direct", 0x02, 0x09, 0x40, 0x3F, 0x66, "0200", "2380945d40ed05c2f0ec40ed0000000015014000"),
    ("solo_3fa3_a9", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "a9000000000000000000000000000000000000000000000000000000000000000000", "4380945d48ed05aaf0ec48ed0000000016014000"),
    ("solo_3fa3_09", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "09000000000000000000000000000000000000000000000000000000000000000000", "4380945d50ed05b2f0ec50ed0000000017010000"),
    ("solo_3fa3_hash1", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "51{hash1}", "5280945d58ed05abf0ec58ed0000000018010000"),
    ("solo_3fa3_hash2", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "91{hash2}", "5280945d60ed0593f0ec60ed0000000019010000"),
    ("solo_4804", "direct", 0x02, 0x09, 0x40, 0x48, 0x04, "00020a", "2480945d68ed05edf0ec68ed000000001a010000"),
    ("solo_4803_short", "direct", 0x02, 0x09, 0x40, 0x48, 0x03, "020a000001973c9bf7090002000a00", "3080945d70ed05e1f0ec70ed000000001b010000"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047778ef78ef0000000018ed18ed0000000008ed70ed000000001800"),
    ("solo_3fa3_hash1b", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "08{hash1}", "5280945d78ed058b70ed78ed000000001c016000"),
    ("solo_3fa3_hash2b", "direct", 0x02, 0xA9, 0x40, 0x3F, 0xA3, "a8{hash2}", "5280945d80ed057370ed80ed000000001d010000"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047788f088f00000000078ed78ed0000000080ed80ed000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047778f178f10000000078ed78ed0000000080ed80ed000000001800"),
    ("sdk_ready_0739", "direct", 0x02, 0x07, 0x40, 0x07, 0x39, "", "2180945d88ed050880ed88ed000000001e010000"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047758f258f20000000080ed80ed0000000088ed88ed000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047758f358f30000000080ed80ed0000000088ed88ed000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d0000047758f458f40000000080ed80ed0000000088ed88ed000000001800"),
    ("neutral", "control", 0x02, 0x09, 0x00, 0x01, 0x04, NEUTRAL_PAYLOAD.hex(), "3a80945d00000477b0f5b0f50000000080ed80ed0000000088ed88ed000000001800"),
    ("solo_mode_3f04_keepalive", "direct", 0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945d90ed051588ed90ed000000001f010000"),
)

SUCCESS_SOLO_SETUP_SEND_ORDER = (
    10072, 10073, 10074, 10075, 10076, 10078, 10079, 10077,
    10080, 10081, 10082, 10083, 10084, 10085, 10086, 10087,
    10088, 10089, 10090, 10091, 10092, 10093, 10094, 10095,
    10096, 10097, 10098, 10099, 10100, 10101, 10102, 10103,
    10104, 10105, 10106, 10107, 10108, 10109, 10110, 10111,
    10112, 10113,
)

PRE_GUN_PREROLL_COMMANDS = {
    10121: (0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945d98ed051d90ed98ed0000000020010000"),
    10129: (0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945da0ed052598eda0ed0000000021010000"),
    10137: (0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945da8ed052da0eda8ed0000000022010000"),
    10146: (0x02, 0x09, 0x00, 0x3F, 0x04, "0b0300", "2480945db0ed0535a8edb0ed0000000023012035"),
    10147: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945db8ed053db0edb8ed0000000024010000"),
    10148: (0x02, 0x09, 0x40, 0x3F, 0x77, "010300", "2480945dc0ed0545b0edc0ed0000000025010000"),
    10149: (0x02, 0x09, 0x40, 0x3F, 0x77, "010501", "2480945dc8ed054db0edc8ed0000000026010000"),
    10157: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945dd0ed0555c8edd0ed0000000027010000"),
    10165: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945dd8ed055dd0edd8ed0000000028010000"),
    10173: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945de0ed0565d8ede0ed000000002901c001"),
    10181: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945de8ed056de0ede8ed000000002a010000"),
    10189: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945df0ed0575e8edf0ed000000002b010000"),
    10197: (0x02, 0x09, 0x00, 0x3F, 0x04, "000300", "2480945df8ed057df0edf8ed000000002c010000"),
}

DEMO_ACTIONS = [
    "pcap_mode_010201:0.05",
    "pcap_mode_010301:0.05",
    "pcap_mode_010401:0.05",
    "pcap_cmd_3f57:0.05",
    "pcap_cmd_3f1f:0.05",
    "forward:0.35",
    "stop:0.20",
    "back:0.30",
    "stop:0.20",
    "left:0.30",
    "stop:0.18",
    "right:0.30",
    "stop:0.20",
    "gimbal_left:0.35",
    "gimbal_stop:0.16",
    "gimbal_right:0.35",
    "gimbal_stop:0.16",
    "gimbal_up:0.30",
    "gimbal_stop:0.16",
    "gimbal_down:0.30",
    "gimbal_stop:0.16",
    "stop:0.15",
    "gun",
]


class Dc68Envelope:
    def __init__(self, session: bytes, tick_seed: int) -> None:
        if len(session) != 2:
            raise ValueError("session must be exactly 2 bytes")
        self.session = session
        self.tick_seed = tick_seed & 0xFFFF
        self.direct_tx_tick = (self.tick_seed + 8) & 0xFFFF
        self.direct_ref_tick = self.tick_seed
        self.latest_direct_tick = self.tick_seed
        self.direct_count = 0
        self.control_tx_tick = (self.tick_seed + 0xA8) & 0xFFFF
        self.control_ref_tick = self.tick_seed
        self.packet_index = 1
        self.pending_direct_ticks: dict[int, int] = {}

    def next_direct_tick(self) -> int:
        value = self.direct_tx_tick
        self.direct_tx_tick = (self.direct_tx_tick + 8) & 0xFFFF
        return value

    def next_control_tick(self) -> int:
        value = self.control_tx_tick
        self.control_tx_tick = (self.control_tx_tick + 8) & 0xFFFF
        return value

    def note_direct_sent(self) -> None:
        self.next_direct_tick()
        self.packet_index = (self.packet_index + 1) & 0xFF

    def set_direct_state(self, tick: int, packet_index: int) -> None:
        self.direct_tx_tick = tick & 0xFFFF
        self.direct_ref_tick = (tick - 8) & 0xFFFF
        self.latest_direct_tick = self.direct_ref_tick
        self.direct_count = 2
        self.packet_index = packet_index & 0xFF

    def wrap_direct(self, duss: bytes, attr_hint: int | bytes) -> bytes:
        tick = self.next_direct_tick()
        total_len = 20 + len(duss)
        outer = bytearray()
        outer += bytes([total_len & 0xFF, 0x80 | ((total_len >> 8) & 0x03)])
        outer += self.session
        outer += struct.pack("<H", tick)
        outer += b"\x05\x00"
        outer[7] = xor_header_check(outer[:7])
        outer += struct.pack("<H", self.direct_ref_tick)
        outer += struct.pack("<H", tick)
        outer += b"\x00\x00\x00\x00"
        if isinstance(attr_hint, bytes):
            flags = attr_hint[:2].ljust(2, b"\x00")
        else:
            flags = bytes([attr_hint & 0xFF, 0x00])
        outer += bytes([self.packet_index & 0xFF, 0x01])
        outer += flags
        if len(duss) >= 8:
            self.pending_direct_ticks[int.from_bytes(duss[6:8], "little")] = tick
        self.latest_direct_tick = tick
        self.direct_count += 1
        self.packet_index = (self.packet_index + 1) & 0xFF
        return bytes(outer) + duss

    def wrap_control(self, duss: bytes) -> bytes:
        tick = self.next_control_tick()
        total_len = 34 + len(duss)
        outer = bytearray()
        outer += bytes([total_len & 0xFF, 0x80])
        outer += self.session
        outer += bytes.fromhex("00000400")
        outer[7] = xor_header_check(outer[:7])
        outer += struct.pack("<H", tick) * 2
        outer += b"\x00\x00\x00\x00"
        outer += struct.pack("<H", self.control_ref_tick) * 2
        outer += b"\x00\x00\x00\x00"
        outer += struct.pack("<H", self.direct_ref_tick)
        outer += struct.pack("<H", self.latest_direct_tick)
        outer += b"\x00\x00\x00\x00"
        outer += struct.pack("<H", len(duss))
        return bytes(outer) + duss

    def observe_inbound(self, data: bytes) -> None:
        if len(data) < 12 or data[2:4] != self.session:
            return
        frames = [
            frame
            for frame in parse_duss_frames(data)
            if frame["header_crc_ok"] and frame["body_crc_ok"]
        ]
        is_stream_data_packet = len(data) != 34 and any(int(frame["offset"]) >= 34 for frame in frames)
        if is_stream_data_packet and len(data) >= 12:
            candidate = int.from_bytes(data[10:12], "little")
            if candidate:
                self.control_tx_tick = candidate
        is_window_packet = len(data) >= 28 and data[4:6] == b"\x00\x00"
        if is_window_packet:
            candidate = int.from_bytes(data[24:26], "little")
            if candidate:
                self.direct_ref_tick = candidate
            candidate = int.from_bytes(data[16:18], "little")
            if candidate:
                self.control_ref_tick = candidate
        for frame in frames:
            if not (frame["attr"] & 0x80):
                continue
            seq = int(frame["seq"])
            tick = self.pending_direct_ticks.pop(seq, None)
            if tick is not None:
                continue

    def build_preconnect(self) -> bytes:
        packet = bytearray(PRECONNECT_TEMPLATE)
        packet[2:4] = self.session
        packet[7] = xor_header_check(packet[:7])
        packet[8:10] = struct.pack("<H", self.tick_seed)
        return bytes(packet)

    def advance_for_reconnect(self, tick_seed: int | None = None) -> None:
        self.session = increment_session(self.session)
        self.tick_seed = (make_tick_seed() if tick_seed is None else tick_seed) & 0xFFFF
        self.direct_tx_tick = (self.tick_seed + 8) & 0xFFFF
        self.direct_ref_tick = self.tick_seed
        self.latest_direct_tick = self.tick_seed
        self.direct_count = 0
        self.control_tx_tick = (self.tick_seed + 0xA8) & 0xFFFF
        self.control_ref_tick = self.tick_seed
        self.packet_index = 1


def xor_header_check(header: bytes) -> int:
    value = 0
    for byte in header:
        value ^= byte
    return value


def parse_session(value: str) -> bytes:
    text = value.strip().lower()
    if text.startswith("0x"):
        number = int(text, 16)
        if not 0 <= number <= 0xFFFF:
            raise argparse.ArgumentTypeError("session integer must be 0..0xffff")
        return struct.pack("<H", number)
    if len(text) == 4:
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("session must be 4 hex characters or 0xNNNN") from exc
    raise argparse.ArgumentTypeError("session must be 4 hex characters such as dc68, or 0x68dc")


def make_session() -> bytes:
    number = secrets.randbelow(0x10000)
    if number == 0:
        number = 1
    return struct.pack("<H", number)


def increment_session(session: bytes) -> bytes:
    if len(session) != 2:
        raise ValueError("session must be exactly 2 bytes")
    number = (int.from_bytes(session, "little") + 1) & 0xFFFF
    if number == 0:
        number = 1
    return struct.pack("<H", number)


def make_tick_seed() -> int:
    return secrets.randbelow(0x2000) * 8


def parse_tick_seed(value: str) -> int:
    text = value.strip().lower()
    if text.startswith("0x"):
        number = int(text, 16)
        if not 0 <= number <= 0xFFFF:
            raise argparse.ArgumentTypeError("outer tick integer must be 0..0xffff")
        return number
    if len(text) == 4:
        try:
            return int.from_bytes(bytes.fromhex(text), "little")
        except ValueError as exc:
            raise argparse.ArgumentTypeError("outer tick must be 4 hex characters or 0xNNNN") from exc
    raise argparse.ArgumentTypeError("outer tick must be raw bytes such as d846, or integer 0x46d8")


def build_duss(
    sender: int,
    receiver: int,
    attr: int,
    cmdset: int,
    cmdid: int,
    payload: bytes,
    seq: int,
) -> bytes:
    length = 13 + len(payload)
    if not 13 <= length <= 0x3FF:
        raise ValueError(f"DUSS frame length out of range: {length}")
    frame = bytearray([0x55, length & 0xFF, 0x04 | ((length >> 8) & 0x03), 0x00, sender, receiver])
    frame += struct.pack("<H", seq & 0xFFFF)
    frame += bytes([attr, cmdset, cmdid])
    frame += payload
    frame += b"\x00\x00"
    frame[3] = crc8(bytes(frame[:3]))
    crc = crc16(bytes(frame[:-2]))
    frame[-2] = crc & 0xFF
    frame[-1] = (crc >> 8) & 0xFF
    return bytes(frame)


def build_control(payload: bytes, seq: int) -> bytes:
    return build_duss(0x02, 0x09, 0x00, 0x01, 0x04, payload, seq)


def build_reference_packet(reference_prefix: str, duss: bytes) -> bytes:
    if not reference_prefix:
        raise ValueError("reference outer prefix is required")
    return bytes.fromhex(reference_prefix) + duss


def replace_control_frames_with_seq(packet: bytes, payload: bytes, seq: int) -> tuple[bytes, int, int]:
    data = bytearray(packet)
    replaced = 0
    i = 0
    while i <= len(data) - 24:
        if (
            data[i] == 0x55
            and data[i + 1] == 0x18
            and data[i + 2] == 0x04
            and data[i + 9] == 0x01
            and data[i + 10] == 0x04
        ):
            data[i : i + 24] = build_control(payload, seq)
            seq = (seq + 1) & 0xFFFF
            replaced += 1
            i += 24
            continue
        i += 1
    return bytes(data), replaced, seq


def drain(sock: socket.socket, max_packets: int, envelope: Dc68Envelope | None = None) -> None:
    for _ in range(max_packets):
        readable, _, _ = select.select([sock], [], [], 0.0)
        if not readable:
            return
        data, addr = sock.recvfrom(65535)
        if envelope is not None:
            envelope.observe_inbound(data)
        print(f"[recv] {addr[0]}:{addr[1]} len={len(data)} hex={data[:32].hex()}{'...' if len(data) > 32 else ''}")
        for frame in parse_duss_frames(data):
            payload = frame["payload"]
            assert isinstance(payload, bytes)
            ok = "ok" if frame["header_crc_ok"] and frame["body_crc_ok"] else "bad-crc"
            print(
                f"       [duss {ok}] sender=0x{frame['sender']:02x} recv=0x{frame['receiver']:02x} "
                f"seq={frame['seq']} attr=0x{frame['attr']:02x} "
                f"cmd=0x{frame['cmdset']:02x}/0x{frame['cmdid']:02x} payload={payload.hex()}"
            )


def send_discovery(args: argparse.Namespace) -> None:
    discovery_token = bytes.fromhex(args.discovery_token)
    if args.dry_run:
        print(f"[send] discovery token len={len(discovery_token)}")
        time.sleep(args.discovery_delay)
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.local_ip, args.discovery_local_port))
    print(f"[send] discovery token len={len(discovery_token)}")
    sock.sendto(discovery_token, (args.robot_ip, args.discovery_robot_port))
    sock.close()
    time.sleep(args.discovery_delay)


def claim_appid(args: argparse.Namespace) -> None:
    appid = make_appid(args.appid)
    appid_text = appid.decode("ascii")
    print(f"[appid] selected AppID: {appid_text}")
    if args.dry_run:
        return
    sock = open_udp(args.appid_bind_ip, args.discovery_local_port, broadcast=True)
    deadline = time.monotonic() + args.appid_timeout
    selected_robot_ip = args.robot_ip
    last_claim = 0.0

    try:
        if selected_robot_ip:
            send_appid(sock, appid, selected_robot_ip, args.discovery_robot_port, "initial claim")
            last_claim = time.monotonic()

        while time.monotonic() < deadline:
            readable, _, _ = select.select([sock], [], [], 0.25)
            now = time.monotonic()
            if (
                selected_robot_ip
                and args.repeat_claim_seconds > 0
                and now - last_claim >= args.repeat_claim_seconds
            ):
                send_appid(sock, appid, selected_robot_ip, args.discovery_robot_port, "repeat claim")
                last_claim = now

            for ready in readable:
                data, addr = ready.recvfrom(65535)
                broadcast = parse_robot_broadcast(data)
                if broadcast is None:
                    continue

                src_ip, src_port = addr[0], addr[1]
                selected_robot_ip = args.robot_ip or src_ip
                state = "pairing" if broadcast.is_pairing else "idle"
                print(
                    f"[broadcast] {src_ip}:{src_port} state={state} "
                    f"ip={broadcast.robot_ip} mac={broadcast.robot_mac} appid={broadcast.appid_text}"
                )

                if broadcast.appid_bytes == appid:
                    send_appid(sock, appid, src_ip, args.discovery_robot_port, "matched ack")
                    print("[ok] robot broadcast now contains our AppID")
                    return

                if broadcast.appid_bytes == b"\x00" * 8 or args.override_existing:
                    send_appid(sock, appid, src_ip, args.discovery_robot_port, "claim AppID")
                    last_claim = time.monotonic()

        raise SystemExit("[fail] AppID connect timed out")
    finally:
        sock.close()


def drain_quiet(sock: socket.socket, max_packets: int = 50) -> int:
    count = 0
    for _ in range(max_packets):
        readable, _, _ = select.select([sock], [], [], 0.0)
        if not readable:
            return count
        sock.recvfrom(65535)
        count += 1
    return count


def wait_for_duss_ack(
    sock: socket.socket,
    seq: int,
    cmdset: int,
    cmdid: int,
    timeout: float,
    envelope: Dc68Envelope | None = None,
) -> bytes | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        readable, _, _ = select.select([sock], [], [], min(0.02, deadline - time.monotonic()))
        if not readable:
            continue
        data, _ = sock.recvfrom(65535)
        if envelope is not None:
            envelope.observe_inbound(data)
        for frame in parse_duss_frames(data):
            if (
                frame["header_crc_ok"]
                and frame["body_crc_ok"]
                and frame["seq"] == seq
                and frame["cmdset"] == cmdset
                and frame["cmdid"] == cmdid
                and frame["attr"] & 0x80
            ):
                payload = frame["payload"]
                assert isinstance(payload, bytes)
                return payload
    return None


def iter_solo_init_sequence(args: argparse.Namespace):
    hash1 = args.pair_hash1.encode("ascii").hex()
    hash2 = args.pair_hash2.encode("ascii").hex()
    for name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix in SUCCESS_SOLO_SETUP_SEQUENCE:
        payload_hex = payload_hex.format(hash1=hash1, hash2=hash2)
        yield name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix


def send_solo_setup(
    sock: socket.socket,
    target: tuple[str, int],
    envelope: Dc68Envelope,
    args: argparse.Namespace,
) -> int:
    preconnect = envelope.build_preconnect()
    print(
        f"[setup] preconnect session={preconnect[2:4].hex()} "
        f"session_le=0x{int.from_bytes(preconnect[2:4], 'little'):04x} "
        f"tick_seed={preconnect[8:10].hex()} "
        f"tick_seed_le=0x{int.from_bytes(preconnect[8:10], 'little'):04x}"
    )
    if not args.dry_run:
        sock.sendto(preconnect, target)
        time.sleep(args.setup_interval)
        drain(sock, args.drain_packets, envelope)

    setup_entries = {
        args.init_seq + index: entry
        for index, entry in enumerate(iter_solo_init_sequence(args))
    }
    for seq in SUCCESS_SOLO_SETUP_SEND_ORDER:
        if seq not in setup_entries:
            raise RuntimeError(f"missing setup entry for seq={seq}")
        name, kind, sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = setup_entries[seq]
        payload = bytes.fromhex(payload_hex)
        duss = build_duss(sender, receiver, attr, cmdset, cmdid, payload, seq)
        if args.reference_outer and reference_prefix:
            packet = build_reference_packet(reference_prefix, duss)
        elif kind == "control":
            packet = envelope.wrap_control(duss)
        else:
            outer_flags = bytes.fromhex(reference_prefix)[18:20]
            packet = envelope.wrap_direct(duss, outer_flags)
        print(f"[setup] {name} seq={seq} cmdset=0x{cmdset:02x} cmdid=0x{cmdid:02x} len={len(packet)}")
        if not args.dry_run:
            sock.sendto(packet, target)
            if kind == "direct" and attr & 0x40:
                wait_for_duss_ack(sock, seq, cmdset, cmdid, args.command_ack_timeout, envelope)
            drain(sock, args.drain_packets, envelope)
        time.sleep((1.0 / args.control_hz) if kind == "control" else args.setup_interval)

    seq = max(setup_entries) + 1
    for _ in range(args.neutral_warmup):
        duss = build_control(NEUTRAL_PAYLOAD, seq)
        packet = envelope.wrap_control(duss)
        print(f"[setup] neutral seq={seq}")
        if not args.dry_run:
            sock.sendto(packet, target)
            drain(sock, args.drain_packets, envelope)
        seq += 1
        time.sleep(1.0 / args.control_hz)
    return seq


def parse_actions(args: argparse.Namespace) -> list[tuple[str, object, float, str]]:
    actions: list[tuple[str, object, float, str]] = []
    for text in args.actions:
        parts = text.split(":")
        name = parts[0].strip().lower()
        if name == "hex":
            if len(parts) not in (2, 3):
                raise SystemExit("hex action format is hex:<11-byte-payload-hex>[:seconds]")
            payload = bytes.fromhex(parts[1])
            if len(payload) != 11:
                raise SystemExit("hex action payload must be exactly 11 bytes")
            seconds = float(parts[2]) if len(parts) == 3 else args.default_duration
            actions.append((f"hex:{parts[1]}", payload, max(0.02, seconds), "control"))
            continue
        if name == "duss":
            if len(parts) not in (7, 8):
                raise SystemExit("duss format is duss:<sender>:<receiver>:<attr>:<cmdset>:<cmdid>:<payload-hex>[:seconds]")
            sender, receiver, attr, cmdset, cmdid = (int(value, 0) for value in parts[1:6])
            payload = bytes.fromhex(parts[6])
            seconds = float(parts[7]) if len(parts) == 8 else 0.0
            actions.append((text, (sender, receiver, attr, cmdset, cmdid, payload), max(0.0, seconds), "duss"))
            continue
        if len(parts) > 2:
            raise SystemExit(f"bad action {text!r}; use name[:seconds], hex:<payload>[:seconds], or duss:<...>")
        if name in GUN_ACTIONS:
            actions.append(("gun", IR_GUN_CONTROL_SEQUENCE, 0.0, "control_sequence"))
            continue
        if name in DUSS_ACTIONS:
            sender, receiver, attr, cmdset, cmdid, payload_hex = DUSS_ACTIONS[name]
            seconds = float(parts[1]) if len(parts) == 2 and parts[1] else 0.0
            actions.append((name, (sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex)), max(0.0, seconds), "duss"))
            continue
        if name not in CONTROL_PAYLOADS:
            raise SystemExit(
                f"unknown action {name!r}; use {', '.join(CONTROL_PAYLOADS)}, "
                f"{', '.join(DUSS_ACTIONS)}, hex:<payload>, or duss:<...>"
            )
        payload = CONTROL_PAYLOADS[name]
        seconds_text = parts[1] if len(parts) == 2 else ""
        seconds = float(seconds_text) if seconds_text else args.default_duration
        actions.append((name, payload, max(0.02, seconds), "control"))
    actions.append(("stop", CONTROL_PAYLOADS["stop"], max(0.05, args.stop_seconds), "control"))
    return actions


def send_duss_sequence(
    sock: socket.socket,
    target: tuple[str, int],
    envelope: Dc68Envelope,
    args: argparse.Namespace,
    seq: int,
    name: str,
    commands: object,
) -> int:
    print(f"[duss-sequence] {name} commands={len(commands)}")
    for sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix in commands:
        duss = build_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex), seq)
        if args.reference_outer and reference_prefix:
            packet = build_reference_packet(reference_prefix, duss)
        else:
            outer_flags = bytes.fromhex(reference_prefix)[18:20]
            packet = envelope.wrap_direct(duss, outer_flags)
        if args.dry_run:
            print(f"  [gun-init] seq={seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} dry-run")
        else:
            acknowledged = False
            attempts = args.command_retries + 1 if attr & 0x40 else 1
            for attempt in range(1, attempts + 1):
                sock.sendto(packet, target)
                if not attr & 0x40:
                    acknowledged = True
                    break
                ack_payload = wait_for_duss_ack(sock, seq, cmdset, cmdid, args.command_ack_timeout, envelope)
                if ack_payload is not None:
                    print(
                        f"  [gun-init-ack] seq={seq} cmd=0x{cmdset:02x}/0x{cmdid:02x} "
                        f"payload={ack_payload.hex()} attempt={attempt}"
                    )
                    acknowledged = True
                    break
            if attr & 0x40 and not acknowledged:
                message = (
                    f"LED GUN initialization ACK timeout: seq={seq} "
                    f"cmd=0x{cmdset:02x}/0x{cmdid:02x}"
                )
                if args.require_gun_init_ack:
                    raise RuntimeError(message)
                print(f"  [gun-init-timeout] {message}; continuing")
        seq += 1
        time.sleep(args.setup_interval)
    return seq


def send_pre_gun_preroll(
    sock: socket.socket,
    target: tuple[str, int],
    envelope: Dc68Envelope,
    args: argparse.Namespace,
    seq: int,
) -> int:
    interval = 1.0 / args.control_hz
    if seq >= args.gun_init_seq:
        return seq
    print(f"[pre-gun] generate success-log preroll seq={seq}->{args.gun_init_seq}")
    while seq < args.gun_init_seq:
        command = PRE_GUN_PREROLL_COMMANDS.get(seq)
        if command is None:
            duss = build_control(NEUTRAL_PAYLOAD, seq)
            packet = envelope.wrap_control(duss)
            label = "neutral"
        else:
            sender, receiver, attr, cmdset, cmdid, payload_hex, reference_prefix = command
            duss = build_duss(sender, receiver, attr, cmdset, cmdid, bytes.fromhex(payload_hex), seq)
            packet = (
                build_reference_packet(reference_prefix, duss)
                if args.reference_outer and reference_prefix
                else envelope.wrap_direct(duss, bytes.fromhex(reference_prefix)[18:20])
            )
            label = f"cmd=0x{cmdset:02x}/0x{cmdid:02x} payload={payload_hex}"
        if args.dry_run and command is not None:
            print(f"  [pre-gun] seq={seq} {label}")
        if not args.dry_run:
            sock.sendto(packet, target)
            drain(sock, args.drain_packets, envelope)
        seq += 1
        time.sleep(interval)
    return seq


def send_designed_motion(
    sock: socket.socket,
    target: tuple[str, int],
    envelope: Dc68Envelope,
    args: argparse.Namespace,
    seq: int,
) -> int:
    interval = 1.0 / args.control_hz
    actions = parse_actions(args)
    if any(kind == "control_sequence" and name == "gun" for name, _payload, _seconds, kind in actions):
        if args.align_gun_init_seq and seq < args.gun_init_seq:
            print(
                f"[gun-align] seq jump {seq}->{args.gun_init_seq} "
                f"direct_tick=0x{args.gun_init_tick:04x} packet_index=0x{args.gun_init_packet_index:02x}"
            )
            seq = args.gun_init_seq
            envelope.set_direct_state(args.gun_init_tick, args.gun_init_packet_index)
        else:
            seq = send_pre_gun_preroll(sock, target, envelope, args, seq)
        seq = send_duss_sequence(sock, target, envelope, args, seq, "gun_init", IR_GUN_INIT_COMMANDS)

    for name, payload, seconds, kind in actions:
        if kind == "duss_sequence":
            seq = send_duss_sequence(sock, target, envelope, args, seq, name, payload)
            continue

        if kind == "control_sequence":
            print(f"[control-sequence] {name} frames={len(payload)} rate={args.control_hz:.1f}Hz")
            for control_payload in payload:
                duss = build_control(control_payload, seq)
                packet = envelope.wrap_control(duss)
                if not args.dry_run:
                    sock.sendto(packet, target)
                    drain(sock, args.drain_packets, envelope)
                seq += 1
                time.sleep(interval)
            continue

        if kind in {"duss", "carrier_duss"}:
            sender, receiver, attr, cmdset, cmdid, duss_payload = payload
            duss = build_duss(sender, receiver, attr, cmdset, cmdid, duss_payload, seq)
            packet = envelope.wrap_control(duss) if kind == "carrier_duss" else envelope.wrap_direct(duss, attr)
            print(
                f"[duss-action] {name} seq={seq} recv=0x{receiver:02x} "
                f"cmdset=0x{cmdset:02x} cmdid=0x{cmdid:02x} payload={duss_payload.hex()}"
            )
            if not args.dry_run:
                sock.sendto(packet, target)
                drain(sock, args.drain_packets, envelope)
            seq += 1
            if seconds:
                time.sleep(seconds)
            continue

        deadline = time.monotonic() + seconds
        print(f"[motion] {name} {seconds:.3f}s payload={payload.hex()}")
        while time.monotonic() < deadline:
            duss = build_control(payload, seq)
            packet = envelope.wrap_control(duss)
            if not args.dry_run:
                sock.sendto(packet, target)
                drain(sock, args.drain_packets, envelope)
            seq += 1
            time.sleep(interval)
    return seq


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RoboMaster S1 designed-motion client. Default generates commands; replay is explicit fallback only.",
    )
    parser.add_argument("--robot-ip", default="192.168.23.149")
    parser.add_argument("--robot-port", type=int, default=10607)
    parser.add_argument("--local-ip", default="192.168.23.192")
    parser.add_argument("--local-port", type=int, default=10609)
    parser.add_argument("--appid", required=True, help="Required 8 hex characters from the QR-derived AppID.")
    parser.add_argument("--appid-bind-ip", default="0.0.0.0")
    parser.add_argument("--appid-timeout", type=float, default=20.0)
    parser.add_argument("--repeat-claim-seconds", type=float, default=1.0)
    parser.add_argument("--override-existing", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--send-discovery", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--discovery-token", default=DISCOVERY_TOKEN.hex())
    parser.add_argument("--discovery-local-port", type=int, default=45678)
    parser.add_argument("--discovery-robot-port", type=int, default=56789)
    parser.add_argument("--discovery-delay", type=float, default=0.10)
    parser.add_argument("--pair-hash1", default=DEFAULT_PAIR_HASH1)
    parser.add_argument("--pair-hash2", default=DEFAULT_PAIR_HASH2)
    parser.add_argument(
        "--reference-outer",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Diagnostic only: use replay-success outer envelope templates while generating DUSS frames.",
    )
    parser.add_argument(
        "--session",
        type=parse_session,
        default=None,
        help="Outer UDP session bytes. Example: dc68. If omitted, PC side generates a new 16-bit session.",
    )
    parser.add_argument(
        "--previous-session",
        type=parse_session,
        default=None,
        help="Previous outer session bytes for reconnect. Current session becomes previous + 1.",
    )
    parser.add_argument(
        "--outer-tick",
        type=parse_tick_seed,
        default=None,
        help="Initial outer tick seed used in preconnect. Example raw bytes: d846. If omitted, PC side generates one.",
    )
    parser.add_argument("--setup-interval", type=float, default=0.006)
    parser.add_argument("--control-hz", type=float, default=45.0)
    parser.add_argument("--init-seq", type=int, default=10072)
    parser.add_argument("--neutral-warmup", type=int, default=0)
    parser.add_argument("--align-gun-init-seq", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--gun-init-seq", type=int, default=10204)
    parser.add_argument("--gun-init-tick", type=lambda value: int(value, 0), default=0xEE00)
    parser.add_argument("--gun-init-packet-index", type=lambda value: int(value, 0), default=0x2D)
    parser.add_argument("--actions", nargs="+", default=DEMO_ACTIONS)
    parser.add_argument("--demo", action="store_true", help="run a pcap-derived all-feature demo sequence")
    parser.add_argument("--default-duration", type=float, default=0.25)
    parser.add_argument("--stop-seconds", type=float, default=0.35)
    parser.add_argument("--drain-packets", type=int, default=1)
    parser.add_argument("--command-ack-timeout", type=float, default=0.35)
    parser.add_argument("--command-retries", type=int, default=2)
    parser.add_argument("--require-gun-init-ack", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    args.control_hz = min(max(args.control_hz, 5.0), 60.0)
    args.setup_interval = min(max(args.setup_interval, 0.001), 0.05)
    if len(args.pair_hash1) != 48 or len(args.pair_hash2) != 48:
        raise SystemExit("--pair-hash1 and --pair-hash2 must be 48 ASCII characters")
    if args.demo:
        args.actions = DEMO_ACTIONS

    claim_appid(args)
    print(
        "[mode] generated DUSS commands; "
        f"reference_outer={args.reference_outer}; no pcap payloads are sent"
    )
    if args.send_discovery:
        send_discovery(args)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if not args.dry_run:
        sock.bind((args.local_ip, args.local_port))
    sock.setblocking(False)
    target = (args.robot_ip, args.robot_port)

    if args.session is not None and args.previous_session is not None:
        raise SystemExit("--session and --previous-session are mutually exclusive")
    session_source = "explicit"
    if args.previous_session is not None:
        session = increment_session(args.previous_session)
        session_source = f"reconnect previous={args.previous_session.hex()} + 1"
    elif args.session is not None:
        session = args.session
    else:
        session = make_session()
        session_source = "new pc-generated"
    tick_seed = (args.outer_tick if args.outer_tick is not None else make_tick_seed()) & 0xFFFF
    envelope = Dc68Envelope(session=session, tick_seed=tick_seed)
    print(
        f"[session] selected outer session={session.hex()} "
        f"session_le=0x{int.from_bytes(session, 'little'):04x} "
        f"source={session_source} "
        f"tick_seed={struct.pack('<H', tick_seed).hex()} "
        f"tick_seed_le=0x{tick_seed:04x}"
    )
    try:
        seq = send_solo_setup(sock, target, envelope, args)
        send_designed_motion(sock, target, envelope, args, seq)
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
