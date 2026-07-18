from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import ftplib
import hashlib
from pathlib import Path
import re
import secrets
import time
import xml.etree.ElementTree as ET

from .config import DEFAULT_CONFIG, LabSdkConfig


DEFAULT_UPLOAD_FILENAME = "python_raw.dsp"


@dataclass(frozen=True)
class LabProgramIdentity:
    guid: str
    sign: str
    title: str
    full_marker: int
    guid_marker: int


def _cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")


def replace_lab_dsp_python_code(dsp: str | bytes, python_code: str) -> str:
    text = dsp.decode("utf-8") if isinstance(dsp, bytes) else dsp
    replacement = f"<python_code><![CDATA[{_cdata(python_code)}]]></python_code>"
    text, count = re.subn(
        r"<python_code><!\[CDATA\[.*?\]\]></python_code>",
        lambda _match: replacement,
        text,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise ValueError("DSP python_code section was not found")
    return text


def parse_lab_dsp_metadata(dsp: str | bytes) -> tuple[str, str, str]:
    text = dsp.decode("utf-8") if isinstance(dsp, bytes) else dsp
    root = ET.fromstring(text)
    attribute = root.find("attribute")
    if attribute is None:
        raise ValueError("DSP attribute section was not found")
    guid = (attribute.findtext("guid") or "").strip().lower()
    sign = (attribute.findtext("sign") or "").strip().lower()
    title = (attribute.findtext("title") or "").strip()
    if len(guid) != 32 or len(sign) != 16:
        raise ValueError("DSP guid/sign metadata is invalid")
    return guid, sign, title


def parse_lab_dsp_code_type(dsp: str | bytes) -> str:
    text = dsp.decode("utf-8") if isinstance(dsp, bytes) else dsp
    root = ET.fromstring(text)
    attribute = root.find("attribute")
    if attribute is None:
        raise ValueError("DSP attribute section was not found")
    return (attribute.findtext("code_type") or "").strip().lower()


def rewrite_lab_dsp_identity(dsp: str | bytes, guid: str | None = None, sign: str | None = None) -> str:
    text = dsp.decode("utf-8") if isinstance(dsp, bytes) else dsp
    guid_value = (guid or secrets.token_hex(16)).strip().lower()
    sign_value = (sign or secrets.token_hex(8)).strip().lower()
    text = re.sub(r"<guid>[^<]*</guid>", f"<guid>{guid_value}</guid>", text, count=1)
    text = re.sub(r"<sign>[^<]*</sign>", f"<sign>{sign_value}</sign>", text, count=1)
    return text


def lab_guid_marker_for_metadata(guid: str, sign: str, title: str = "") -> int:
    known_markers = {
        ("1387cf163c3b4e22b781898d0d260b0e", "0ad9df86625254c2"): 0x0D,
        ("178a094f60b04dce84d919ce120af996", "a6c9ffdee29cd5da"): 0x6D,
        ("178a094f60b04dce84d919ce120af996", "6ec216749242c87a"): 0x9D,
    }
    return known_markers.get((guid.strip().lower(), sign.strip().lower()), 0x2D)


def lab_metadata_markers_for_dsp(dsp: str | bytes) -> tuple[int, int]:
    if parse_lab_dsp_code_type(dsp) == "python":
        return 0x21, 0x2D
    guid, sign, title = parse_lab_dsp_metadata(dsp)
    return 0x51, lab_guid_marker_for_metadata(guid, sign, title)


def render_bridge_python(config: LabSdkConfig = DEFAULT_CONFIG) -> str:
    text = load_bridge_python()
    replacements = {
        "__COMMAND_PORT__": str(int(config.control_port)),
        "__TELEMETRY_PORT__": str(int(config.telemetry_port)),
        "__CONTROL_PERIOD_SEC__": repr(float(config.control_period_sec)),
        "__TELEMETRY_PERIOD_SEC__": repr(float(config.telemetry_period_sec)),
        "__COMMAND_TIMEOUT_SEC__": repr(float(config.command_timeout_sec)),
        "__COMMAND_DECAY_PER_TICK__": repr(float(config.command_decay_per_tick)),
        "__COMMAND_ZERO_EPSILON__": repr(float(config.command_zero_epsilon)),
        "__COMMAND_ANGULAR_ZERO_EPSILON__": repr(float(config.command_angular_zero_epsilon)),
        "__MAX_CHASSIS_SPEED__": repr(float(config.max_chassis_speed)),
        "__MAX_CHASSIS_YAW_SPEED__": repr(float(config.max_chassis_yaw_speed)),
        "__MAX_GIMBAL_SPEED__": repr(float(config.max_gimbal_speed)),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


def build_lab_bridge_dsp(python_code: str | None = None, config: LabSdkConfig = DEFAULT_CONFIG) -> tuple[str, LabProgramIdentity]:
    template_path = Path(__file__).resolve().parent / "templates" / "extracted_lab_twister_py.dsp"
    if python_code is None:
        python_code = render_bridge_python(config)
    dsp = replace_lab_dsp_python_code(template_path.read_text(encoding="utf-8"), python_code)
    dsp = rewrite_lab_dsp_identity(dsp)
    guid, sign, title = parse_lab_dsp_metadata(dsp)
    full_marker, guid_marker = lab_metadata_markers_for_dsp(dsp)
    return dsp, LabProgramIdentity(guid, sign, title, full_marker, guid_marker)


def load_bridge_python() -> str:
    return (Path(__file__).resolve().parent / "templates" / "lab_control_bridge.py").read_text(encoding="utf-8")


def upload_lab_dsp(robot_ip: str, dsp: str | bytes, filename: str = DEFAULT_UPLOAD_FILENAME, timeout: float = 10.0) -> str:
    payload = dsp.encode("utf-8") if isinstance(dsp, str) else dsp
    digest = hashlib.md5(payload).hexdigest()
    with ftplib.FTP() as ftp:
        ftp.connect(robot_ip, 21, timeout=timeout)
        ftp.login("anonymous", "")
        ftp.cwd("python")
        ftp.voidcmd("TYPE I")
        ftp.storbinary(f"STOR {filename}", BytesIO(payload))
    return digest
