"""Isolated executable boundary for one Live Visual browser capture."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _bounded_error(exc: BaseException) -> dict[str, str]:
    return {"status": "failed", "error_type": type(exc).__name__,
            "error": "isolated visual capture failed"}


def run(input_path: Path, result_path: Path) -> int:
    """Execute one capture from a compact private input contract."""
    try:
        if os.name == "posix":
            os.nice(5)
        value = json.loads(input_path.read_text(encoding="utf-8"))
        request_value = value["request"]
        from src.core.inspection.live_browser import capture_page
        from src.core.inspection.live_visual import CaptureRequest

        request = CaptureRequest(
            surface_id=str(request_value["surface_id"]), title=str(request_value["title"]),
            human_url=str(request_value["human_url"]), semantic_url=str(request_value["semantic_url"]),
            viewport=str(request_value["viewport"]), fingerprint=str(request_value["fingerprint"]),
            canonical=dict(request_value.get("canonical") or {}),
        )
        result: dict[str, Any] = capture_page(
            str(value["capture_origin"]), request, Path(value["output_path"]),
        )
        payload: dict[str, Any] = {"status": "complete", "presentation": result}
        exit_code = 0
    except BaseException as exc:
        payload = _bounded_error(exc)
        exit_code = 1
    result_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8",
    )
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    values = parser.parse_args()
    return run(values.input, values.result)


if __name__ == "__main__":
    raise SystemExit(main())
