from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path


KEYSTREAM = bytes.fromhex(
    "9b10a51e972c813af348fdb60fa419922b80358e279c11aa03b80da6"
)
MAGIC = bytes.fromhex("ca6c")
HEADER8_APPID_MASK = bytes.fromhex("71ca63d86dc67f34")
DEFAULT_BOX_SIZE = 12
DEFAULT_BORDER = 4


@dataclass(frozen=True)
class WiFiQrData:
    ssid: str
    password: str
    appid: str
    header8: str
    payload: bytes
    qr_text: str


def utf8_continuation_count(data: bytes) -> int:
    return sum(1 for byte in data if (byte & 0xC0) == 0x80)


def calc_ssid_length_field(ssid_bytes: bytes) -> int:
    return len(ssid_bytes) + utf8_continuation_count(ssid_bytes) + 1


def calc_length_header_auto(ssid_bytes: bytes, password_bytes: bytes) -> bytes:
    value = 0xBC00 + calc_ssid_length_field(ssid_bytes) + (len(password_bytes) << 6)
    return value.to_bytes(2, "little")


def xor_body(ssid: str, password: str) -> bytes:
    plain = (ssid + password).encode("utf-8")
    if len(plain) > len(KEYSTREAM):
        raise ValueError(
            f"SSID+Password is {len(plain)} bytes, but the known QR keystream is {len(KEYSTREAM)} bytes."
        )
    return bytes(value ^ key for value, key in zip(plain, KEYSTREAM))


def normalize_header8_hex(header8: str) -> str:
    value = header8.strip().lower().replace(" ", "").replace("-", "")
    if value.startswith("0x"):
        value = value[2:]
    if len(value) != 16:
        raise ValueError("header8 must be exactly 8 bytes / 16 hex characters")
    bytes.fromhex(value)
    return value


def normalize_appid(appid: str) -> str:
    value = appid.strip().lower()
    if len(value) != 8 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("AppID must be exactly 8 hex characters, for example b6359877")
    return value


def make_header8_from_appid(appid: str) -> str:
    raw = normalize_appid(appid).encode("ascii")
    return bytes(value ^ mask for value, mask in zip(raw, HEADER8_APPID_MASK)).hex()


def decode_appid_from_header8(header8: str) -> str:
    encrypted = bytes.fromhex(normalize_header8_hex(header8))
    raw = bytes(value ^ mask for value, mask in zip(encrypted, HEADER8_APPID_MASK))
    if len(raw) == 8 and all(byte in b"0123456789abcdef" for byte in raw):
        return raw.decode("ascii")
    return f"non-hex:{raw.hex()}"


def make_payload(ssid: str, password: str, header8: str) -> bytes:
    header8_bytes = bytes.fromhex(normalize_header8_hex(header8))
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")
    length_header = calc_length_header_auto(ssid_bytes, password_bytes)
    return length_header + header8_bytes + MAGIC + xor_body(ssid, password)


def payload_to_qr_text(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def build_wifi_qr_data(ssid: str, password: str, appid: str) -> WiFiQrData:
    appid = normalize_appid(appid)
    header8 = make_header8_from_appid(appid)
    payload = make_payload(ssid, password, header8)
    return WiFiQrData(ssid=ssid, password=password, appid=appid, header8=header8, payload=payload, qr_text=payload_to_qr_text(payload))


def make_qr_image(qr_text: str, box_size: int = DEFAULT_BOX_SIZE, border: int = DEFAULT_BORDER):
    import qrcode

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(qr_text)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def save_qr(qr_text: str, output: str | Path, box_size: int = DEFAULT_BOX_SIZE, border: int = DEFAULT_BORDER) -> Path:
    path = Path(output)
    image = make_qr_image(qr_text, box_size=box_size, border=border)
    image.save(path)
    return path
