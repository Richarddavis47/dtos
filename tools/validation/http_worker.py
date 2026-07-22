"""Isolated owner of the validation server, smoke run, and cleanup."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from src.platform.validation.lifecycle import TrackedServer
from src.platform.validation.process_detection import processes_for_run, windows_process_inventory
from src.platform.validation.worker import HttpValidationResult

ROOT = Path(__file__).resolve().parents[2]


def execute(run_id: str) -> HttpValidationResult:
    result = HttpValidationResult(run_id=run_id)
    server = None
    with tempfile.TemporaryFile() as log:
        try:
            started = perf_counter()
            server = TrackedServer.start(ROOT, log, run_id)
            result.port = server.port
            server.wait_until_ready()
            result.pid = server.runtime_pid
            result.startup = "PASS"
            result.timings["startup_seconds"] = round(perf_counter() - started, 3)

            started = perf_counter()
            smoke = subprocess.run(
                [sys.executable, "-m", "tools.validation.smoke_http", "--base-url", f"http://127.0.0.1:{server.port}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            result.timings["http_smoke_seconds"] = round(perf_counter() - started, 3)
            if smoke.returncode:
                result.errors.append(f"HTTP smoke failed: {smoke.stderr or smoke.stdout}")
            else:
                result.http_smoke = "PASS"
        except Exception as exc:
            result.errors.append(f"Validation worker failed: {exc}")
        finally:
            if server is not None:
                started = perf_counter()
                try:
                    cleaned = server.cleanup()
                    result.cleanup = "PASS"
                    result.shutdown_method = cleaned.outcome
                except Exception as exc:
                    result.errors.append(f"Cleanup failed: {exc}")
                result.timings["cleanup_seconds"] = round(perf_counter() - started, 3)
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
    parser.add_argument("--validation-run-id", required=True)
    args = parser.parse_args()
    result = HttpValidationResult(run_id=args.validation_run_id)
    try:
        result = execute(args.validation_run_id)
    except BaseException as exc:
        result.errors.append(f"Worker crashed: {exc}")
    finally:
        result.completed = True
        result.completed_at = datetime.now(timezone.utc).isoformat()
        args.result_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.result_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
        temporary.replace(args.result_file)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
