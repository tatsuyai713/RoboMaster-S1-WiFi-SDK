#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


LAB_SDK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = LAB_SDK_ROOT.parent / "lab" / "robomaster_s1_lab_control_bridge.dsp"
DEFAULT_PYTHON_OUTPUT = (
    LAB_SDK_ROOT.parent / "lab" / "robomaster_s1_lab_control_bridge.py"
)
PACKAGED_OUTPUT = (
    LAB_SDK_ROOT
    / "robomaster_lab_sdk"
    / "templates"
    / "robomaster_s1_lab_control_bridge.dsp"
)
if str(LAB_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_SDK_ROOT))

from robomaster_lab_sdk.config import LabSdkConfig  # noqa: E402
from robomaster_lab_sdk.program import (  # noqa: E402
    build_lab_bridge_dsp,
    parse_lab_dsp_code_type,
    render_bridge_python,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a RoboMaster S1 Lab-mode DSP containing the control bridge."
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--control-port", type=int, default=40923)
    parser.add_argument("--telemetry-port", type=int, default=40924)
    parser.add_argument("--control-period", type=float, default=0.02)
    parser.add_argument("--telemetry-period", type=float, default=0.02)
    parser.add_argument("--command-timeout", type=float, default=0.3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = LabSdkConfig(
        control_port=args.control_port,
        telemetry_port=args.telemetry_port,
        control_period_sec=args.control_period,
        telemetry_period_sec=args.telemetry_period,
        command_timeout_sec=args.command_timeout,
    )
    dsp, identity = build_lab_bridge_dsp(config=config)
    if parse_lab_dsp_code_type(dsp) != "python":
        raise RuntimeError("generated DSP is not a Python Lab program")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dsp, encoding="utf-8")
    if args.output.resolve() == DEFAULT_OUTPUT.resolve():
        DEFAULT_PYTHON_OUTPUT.write_text(
            render_bridge_python(config),
            encoding="utf-8",
        )
        PACKAGED_OUTPUT.write_text(dsp, encoding="utf-8")
    print(
        f"{args.output} bytes={len(dsp.encode('utf-8'))} "
        f"guid={identity.guid} sign={identity.sign}"
    )
    if args.output.resolve() == DEFAULT_OUTPUT.resolve():
        print(f"{DEFAULT_PYTHON_OUTPUT} rendered-python")
        print(f"{PACKAGED_OUTPUT} packaged-copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
