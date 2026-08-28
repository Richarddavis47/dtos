"""Isolated owner of the validation server, smoke run, and cleanup."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from src.platform.validation.lifecycle import TrackedServer
from src.platform.validation.process_detection import processes_for_run, windows_process_inventory
from src.platform.validation.worker import HttpValidationResult
from src.platform.validation.progress import (
    PROGRESS_FILE_ENVIRONMENT, PROGRESS_RUN_ENVIRONMENT, ValidationProgress,
)

ROOT = Path(__file__).resolve().parents[2]


def execute(run_id: str, progress: ValidationProgress | None = None) -> HttpValidationResult:
    result = HttpValidationResult(run_id=run_id)
    server = None
    record = progress.record if progress is not None else lambda *_args, **_kwargs: None
    record("worker_phase", phase="entry", status="started")
    with tempfile.TemporaryFile() as log:
        try:
            started = perf_counter()
            record("worker_phase", phase="startup", status="started")
            if progress is not None:
                os.environ[PROGRESS_FILE_ENVIRONMENT] = str(progress.path)
                os.environ[PROGRESS_RUN_ENVIRONMENT] = run_id
            server = TrackedServer.start(ROOT, log, run_id)
            result.port = server.port
            server.wait_until_ready()
            result.pid = server.runtime_pid
            result.startup = "PASS"
            result.timings["startup_seconds"] = round(perf_counter() - started, 3)
            record("worker_phase", phase="startup", status="completed", duration_ms=round((perf_counter() - started) * 1000, 3), runtime_pid=result.pid)

            started = perf_counter()
            record("worker_phase", phase="http_smoke", status="started")
            smoke = subprocess.run(
                [sys.executable, "-m", "tools.validation.smoke_http", "--base-url", f"http://127.0.0.1:{server.port}",
                 "--progress-file", str(progress.path) if progress is not None else "",
                 "--validation-run-id", run_id],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            result.timings["http_smoke_seconds"] = round(perf_counter() - started, 3)
            record("worker_phase", phase="http_smoke", status="completed", duration_ms=round((perf_counter() - started) * 1000, 3), returncode=smoke.returncode)
            if smoke.returncode:
                result.errors.append(f"HTTP smoke failed: {smoke.stderr or smoke.stdout}")
            else:
                result.http_smoke = "PASS"
        except Exception as exc:
            result.errors.append(f"Validation worker failed: {exc}")
        finally:
            if server is not None:
                started = perf_counter()
                record("worker_phase", phase="cleanup", status="started")
                try:
                    cleaned = server.cleanup()
                    result.cleanup = "PASS"
                    result.shutdown_method = cleaned.outcome
                except Exception as exc:
                    result.errors.append(f"Cleanup failed: {exc}")
                result.timings["cleanup_seconds"] = round(perf_counter() - started, 3)
                record("worker_phase", phase="cleanup", status="completed", duration_ms=round((perf_counter() - started) * 1000, 3), outcome=result.shutdown_method)
            try:
                tracked_matches = processes_for_run(windows_process_inventory(), run_id)
                if tracked_matches:
                    result.errors.append(f"Tracked DTOS process remains: {[item.pid for item in tracked_matches]}")
                else:
                    result.process_cleanup = "PASS"
            except Exception as exc:
                result.errors.append(f"Process verification failed: {exc}")
            if result.errors:
                log.seek(0)
                server_output = log.read().decode(errors="replace")[-4000:]
                if server_output:
                    result.errors.append(f"Server log: {server_output}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-file", type=Path, required=True)
    parser.add_argument("--progress-file", type=Path, required=True)
    parser.add_argument("--validation-run-id", required=True)
    args = parser.parse_args()
    result = HttpValidationResult(run_id=args.validation_run_id)
    progress = ValidationProgress(args.progress_file, args.validation_run_id)
    try:
        result = execute(args.validation_run_id, progress)
    except BaseException as exc:
        result.errors.append(f"Worker crashed: {exc}")
    finally:
        result.completed = True
        result.completed_at = datetime.now(timezone.utc).isoformat()
        args.result_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.result_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
        temporary.replace(args.result_file)
        progress.record("worker_phase", phase="result_write", status="completed", passed=result.passed)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
