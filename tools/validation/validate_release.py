"""Execute every DTOS v1 release gate from one Windows-safe entry point."""
from __future__ import annotations

import argparse
import os
import traceback
from uuid import uuid4
from pathlib import Path

from src.platform.validation import run_release_validation
from src.platform.validation.release import TRACE_FILE, trace_event

ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    parser = argparse.ArgumentParser(description="Run every DTOS release validation gate.")
    parser.parse_args()
    TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACE_FILE.unlink(missing_ok=True)
    process_group = None
    try:
        process_group = os.getpgrp()
    except AttributeError:
        pass
    trace_event("validator_start", process_group=process_group)
    exit_code = 1
    try:
        run_id = uuid4().hex
        trace_event("validation_run_id_created", run_id=run_id)
        results = run_release_validation(ROOT, run_id)
        total = sum(result.duration_seconds for result in results)
        print(f"DTOS release validation passed: {len(results)} gates in {total:.3f}s.")
        trace_event("validator_final_summary", gates=len(results), total_seconds=total)
        exit_code = 0
        return exit_code
    except BaseException as exc:
        trace_event("validator_uncaught_exception", exception_type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        raise
    finally:
        trace_event("validator_exit", exit_code=exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
