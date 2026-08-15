"""Inventory and physically retire the configured dormant HistoricalStore.

The command is intentionally narrow: it recognizes only the configured legacy
database and its SQLite sidecars, refuses an unrecognized schema, verifies the
application's public zero-access gate, and never copies or vacuums the archive.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from app_metadata import VERSION
from config import HISTORY_DATABASE_FILE, HISTORY_STORAGE_ROOT

LEGACY_SIGNATURE = {
    "historical_records", "player_identity", "import_jobs",
    "import_checkpoints", "schema_migrations", "database_metadata",
}
SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def legacy_files(database: Path = HISTORY_DATABASE_FILE) -> tuple[Path, ...]:
    database = Path(database)
    return tuple(
        path for path in (database, *(Path(f"{database}{suffix}") for suffix in SIDECAR_SUFFIXES))
        if path.exists()
    )


def _schema(database: Path) -> set[str]:
    uri = f"file:{database.resolve().as_posix()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        return {
            str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            )
        }
    finally:
        connection.close()


def _open_owners(paths: tuple[Path, ...]) -> list[dict[str, Any]]:
    targets = {str(path.resolve()) for path in paths}
    owners: list[dict[str, Any]] = []
    for process in psutil.process_iter(["pid", "name", "open_files"]):
        try:
            opened = {
                str(Path(item.path).resolve()) for item in (process.info.get("open_files") or ())
            }
        except (OSError, psutil.Error):
            continue
        if opened & targets:
            owners.append({"pid": process.info["pid"], "name": process.info["name"]})
    return owners


def inventory(database: Path = HISTORY_DATABASE_FILE) -> dict[str, Any]:
    files = legacy_files(database)
    tables = _schema(Path(database)) if Path(database).exists() else set()
    return {
        "status": "present" if files else "absent",
        "legacy_file_present": Path(database).exists(),
        "files": [
            {"role": "database" if path == Path(database) else path.name.removeprefix(Path(database).name),
             "bytes": path.stat().st_size}
            for path in files
        ],
        "bytes": sum(path.stat().st_size for path in files),
        "schema_signature_valid": not files or LEGACY_SIGNATURE.issubset(tables),
        "legacy_signature_tables": sorted(LEGACY_SIGNATURE & tables),
        "open_owners": _open_owners(files),
        "configured_containment": Path(database).resolve().parent == Path(HISTORY_STORAGE_ROOT).resolve(),
    }


def _gate(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="POST", headers={"User-Agent": "DTOS-Retirement/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    legacy = payload.get("legacy_historical_store") or {}
    if legacy.get("historicalstore_retired") is not True:
        raise RuntimeError("Application has not enabled fail-closed HistoricalStore retirement.")
    if any(int(legacy.get(key) or 0) for key in (
        "legacy_read_attempts", "legacy_write_attempts", "legacy_create_attempts",
    )) or legacy.get("callers"):
        raise RuntimeError("Production zero-access retirement gate failed.")
    return legacy


def retire(*, gate_url: str, database: Path = HISTORY_DATABASE_FILE) -> dict[str, Any]:
    before = inventory(database)
    if not before["legacy_file_present"]:
        raise RuntimeError("Configured legacy HistoricalStore is already absent.")
    if not before["configured_containment"]:
        raise RuntimeError("Configured legacy HistoricalStore is outside the durable storage root.")
    if not before["schema_signature_valid"]:
        raise RuntimeError("Configured database does not match the retired HistoricalStore schema.")
    if before["open_owners"]:
        raise RuntimeError("A process still has the retired HistoricalStore open.")
    _gate(gate_url)
    free_before = shutil.disk_usage(Path(database).parent).free
    files = legacy_files(database)
    removed = [{"role": row["role"], "bytes": row["bytes"]} for row in before["files"]]
    for path in files:
        path.unlink()
    marker = {
        "schema_version": 1, "version": VERSION, "retired_at": _utcnow(),
        "bytes_removed": before["bytes"], "files_removed": removed,
    }
    marker_path = Path(HISTORY_STORAGE_ROOT) / ".historicalstore-retired.json"
    temporary = marker_path.with_name(f".{marker_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with temporary.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, marker_path)
    free_after = shutil.disk_usage(Path(database).parent).free
    return {
        "status": "retired", "retired_at": marker["retired_at"],
        "bytes_removed": before["bytes"], "files_removed": removed,
        "free_before": free_before, "free_after": free_after,
        "free_bytes_gained": free_after - free_before,
        "legacy_file_present": Path(database).exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory or retire dormant HistoricalStore files.")
    parser.add_argument("action", choices=("inventory", "retire"))
    parser.add_argument("--gate-url", default="http://127.0.0.1:10000/api/leagues/resources/measure")
    arguments = parser.parse_args()
    result = inventory() if arguments.action == "inventory" else retire(gate_url=arguments.gate_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
