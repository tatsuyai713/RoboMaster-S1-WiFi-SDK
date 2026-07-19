from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


LAB_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = LAB_ROOT.parent
SOLO_ROOT = PROJECT_ROOT / "SDK"


class SdkIndependenceTests(unittest.TestCase):
    def test_lab_has_no_solo_sdk_import_or_dependency(self) -> None:
        offenders = []
        for path in LAB_ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".toml"}:
                continue
            if path == Path(__file__):
                continue
            if "robomaster_s1_sdk" in path.read_text(
                encoding="utf-8",
                errors="ignore",
            ):
                offenders.append(str(path.relative_to(LAB_ROOT)))
        self.assertEqual(offenders, [])

    def test_solo_has_no_lab_sdk_import_or_dependency(self) -> None:
        offenders = []
        for path in SOLO_ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".toml"}:
                continue
            if "robomaster_lab_sdk" in path.read_text(
                encoding="utf-8",
                errors="ignore",
            ):
                offenders.append(str(path.relative_to(SOLO_ROOT)))
        self.assertEqual(offenders, [])

    def test_lab_imports_with_only_lab_sdk_on_pythonpath(self) -> None:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(LAB_ROOT)
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from robomaster import robot; "
                        "from robomaster_lab_sdk.base import Robot; "
                        "assert robot.Robot and Robot"
                    ),
                ],
                cwd=directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)

if __name__ == "__main__":
    unittest.main()
