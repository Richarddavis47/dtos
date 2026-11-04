"""Idempotent development setup; no product services or production access."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        parser.error("DTOS Cloud validation requires Python 3.12")
    directory = args.venv.resolve()
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(directory)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements-validation.txt")],
        cwd=ROOT, check=True,
    )
    # Keep a supplied system browser; never download a redundant copy for Cloud.
    if not os.environ.get("DTOS_CHROMIUM_EXECUTABLE") and not (
        sys.platform.startswith("linux") and
        (shutil.which("chromium") or shutil.which("chromium-browser"))
    ):
        subprocess.run([str(python), "-m", "playwright", "install", "chromium"], cwd=ROOT, check=True)
    subprocess.run([str(python), "-m", "pip", "check"], cwd=ROOT, check=True)
    subprocess.run([str(python), "-m", "tools.validation.browser_runtime"], cwd=ROOT, check=True)
    print(f"DTOS development setup complete: {python}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
