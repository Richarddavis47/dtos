"""Launch an isolated HTTP worker and consume only its run-scoped artifact."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.platform.validation.worker import validate_worker_result

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIRECTORY = ROOT / ".validation" / "results"


def _failure(reason: str) -> int:
    print(f"HTTP validation infrastructure failure: {reason}")
    print("HTTP validation final result: FAIL")
    return 1


def result_file_for(run_id: str) -> Path:
    return RESULTS_DIRECTORY / f"{run_id}.json"


def main(timeout: float = 120) -> int:
    run_id = os.environ.get("DTOS_VALIDATION_RUN_ID") or uuid4().hex
    result_file = result_file_for(run_id)
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if result_file.exists():
        return _failure(f"A stale or duplicate result artifact already exists for run {run_id}.")
    launched_at = datetime.now(timezone.utc)
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    worker = subprocess.Popen(
        [sys.executable, "-m", "tools.validation.http_worker", "--result-file", str(result_file),
         "--validation-run-id", run_id],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    try:
        try:
            return_code = worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait(timeout=10)
            return _failure(f"Validation worker timed out after {timeout}s.")
        if not result_file.exists():
            return _failure(f"Worker exited with code {return_code} without the run-scoped result artifact.")
        if datetime.fromtimestamp(result_file.stat().st_mtime, timezone.utc) < launched_at:
            return _failure("Worker result artifact predates this validation run.")
        try:
            payload = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return _failure(f"Worker result is unreadable: {exc}")
        schema_errors = validate_worker_result(payload, run_id)
        if schema_errors:
            return _failure(" ".join(schema_errors))
        elapsed = (datetime.fromisoformat(payload["completed_at"]) - datetime.fromisoformat(payload["started_at"])).total_seconds()
        if elapsed < .5:
            return _failure(f"Worker reported implausible completion in {elapsed:.3f}s.")
        for key in ("startup", "http_smoke", "cleanup", "process_cleanup"):
            print(f"{key}: {payload[key]}")
        print(f"validation_run_id: {run_id}")
        print(f"runtime_pid: {payload.get('pid')}")
        print(f"shutdown_method: {payload.get('shutdown_method')}")
        print(f"timings: {json.dumps(payload['timings'], sort_keys=True)}")
        if payload["errors"]:
            print("errors: " + " | ".join(payload["errors"]))
        passed = return_code == 0 and payload["passed"]
        print(f"HTTP validation final result: {'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    finally:
        result_file.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
