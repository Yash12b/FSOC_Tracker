#!/usr/bin/env python3
"""Build the standalone desktop executable for FSOC Tracker."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "fsoc_tracker.spec"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _resolve_python() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> int:
    if not SPEC.exists():
        raise FileNotFoundError(f"PyInstaller spec not found: {SPEC}")

    py_executable = _resolve_python()
    cmd = [
        py_executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(SPEC),
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
    ]

    print(f"Building desktop app from {SPEC}")
    subprocess.run(cmd, cwd=str(ROOT), check=True)

    bundle = DIST / "FSOC-Tracker"
    if not bundle.exists():
        app_bundle = DIST / "FSOC-Tracker.app"
        if app_bundle.exists():
            bundle = app_bundle
    if bundle.exists():
        print(f"Bundle ready: {bundle}")
    else:
        print(f"Build completed. Check dist/ for output in {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
