from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from robomaster_s1_sdk import DiscoveredRobot, discover_robots

from .bridge import DEFAULT_CONTROL_PORT, DEFAULT_TELEMETRY_PORT, LabBridge, LabTelemetry
from .program import (
    lab_metadata_markers_for_dsp,
    parse_lab_dsp_metadata,
    replace_lab_dsp_python_code,
    upload_lab_dsp,
)
from .robot import Robot

DEFAULT_DSP_NAME = "sample_labo_2_edited.dsp"
DEFAULT_BRIDGE_REFERENCE_NAME = "extracted_lab_twister_py.dsp"
BRIDGE_CAPABLE_DSP_NAMES = {
    "robomaster_s1_lab_control_bridge.dsp",
    "sample_python_child_udp_probe.dsp",
}


@dataclass(frozen=True)
class LabUploadResult:
    selected_program: str
    title: str
    guid: str
    sign: str
    guid_marker: int
    full_marker: int
    byte_count: int
    digest: str
    upload_time: str


def is_bridge_capable(program_name: str) -> bool:
    return program_name.strip().lower() in BRIDGE_CAPABLE_DSP_NAMES


def extract_python_code(dsp: bytes | str) -> str:
    text = dsp.decode("utf-8") if isinstance(dsp, bytes) else dsp
    start = text.find("<python_code><![CDATA[")
    if start < 0:
        raise ValueError("DSP python_code section was not found")
    start += len("<python_code><![CDATA[")
    end = text.find("]]></python_code>", start)
    if end < 0:
        raise ValueError("DSP python_code section was not closed")
    return text[start:end]


def load_lab_program(lab_dir: Path, program_name: str) -> tuple[str | bytes, str, str, str, int, int, int]:
    selected_program = program_name.strip()
    if not selected_program:
        raise RuntimeError("Select a DSP file from the lab folder")
    dsp_path = (lab_dir / selected_program).resolve()
    lab_dir_resolved = lab_dir.resolve()
    if lab_dir_resolved not in (dsp_path, *dsp_path.parents):
        raise ValueError("Selected DSP path is outside the lab folder")
    if not dsp_path.exists():
        raise FileNotFoundError(f"Selected DSP was not found: {dsp_path}")
    dsp: str | bytes = dsp_path.read_bytes()
    if is_bridge_capable(selected_program):
        reference_path = lab_dir / DEFAULT_BRIDGE_REFERENCE_NAME
        if not reference_path.exists():
            raise FileNotFoundError(f"lab/{DEFAULT_BRIDGE_REFERENCE_NAME} is required")
        paired_python_path = dsp_path.with_suffix(".py")
        if selected_program.lower() == "robomaster_s1_lab_control_bridge.dsp" and paired_python_path.exists():
            bridge_python = paired_python_path.read_text(encoding="utf-8")
        else:
            bridge_python = dsp.decode("utf-8") if dsp_path.suffix.lower() == ".py" else extract_python_code(dsp)
        dsp = replace_lab_dsp_python_code(reference_path.read_bytes(), bridge_python)
    guid, sign, title = parse_lab_dsp_metadata(dsp)
    full_marker, guid_marker = lab_metadata_markers_for_dsp(dsp)
    byte_count = len(dsp.encode("utf-8") if isinstance(dsp, str) else dsp)
    return dsp, guid, sign, title, full_marker, guid_marker, byte_count


def upload_program(ep_robot: Robot, lab_dir: Path, program_name: str) -> LabUploadResult:
    dsp, guid, sign, title, full_marker, guid_marker, byte_count = load_lab_program(lab_dir, program_name)
    if full_marker == 0x21:
        ep_robot.send_duss(0x02, 0x09, 0x40, 0x3F, 0x4C, b"\x00")
        time.sleep(0.02)
    ep_robot.send_lab_metadata(guid, sign, full_marker)
    time.sleep(0.02)
    ep_robot.send_lab_guid_metadata(guid, guid_marker)
    time.sleep(0.02)
    if full_marker == 0x21:
        ep_robot.send_lab_upload_size(byte_count)
        time.sleep(0.02)
    digest = upload_lab_dsp(ep_robot.robot_ip, dsp)
    return LabUploadResult(
        selected_program=program_name,
        title=title,
        guid=guid,
        sign=sign,
        guid_marker=guid_marker,
        full_marker=full_marker,
        byte_count=byte_count,
        digest=digest,
        upload_time=time.strftime("%H:%M:%S"),
    )
