"""Detect genuine orphaned DTOS server hosts without self-matching shell text."""
from __future__ import annotations

import argparse
import os

from src.platform.validation.process_detection import (
    ProcessRecord, genuine_dtos_servers, is_dtos_server, processes_for_run,
    windows_process_inventory,
)

__all__ = ["ProcessRecord", "genuine_dtos_servers", "is_dtos_server", "windows_process_inventory"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-run-id")
    args = parser.parse_args()
    records = windows_process_inventory()
    matches = (
        processes_for_run(records, args.validation_run_id)
        if args.validation_run_id
        else genuine_dtos_servers(records, os.getpid(), os.getppid())
    )
    if matches:
        detail = "\n".join(
            f"name={item.name} pid={item.pid} parent={item.parent_pid} executable={item.executable} arguments={item.arguments}"
            for item in matches
        )
        raise RuntimeError("Genuine DTOS server process remains:\n" + detail)
    print("Process cleanup passed: no genuine DTOS Python/Uvicorn server remains.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
