"""Durable Historical League Memory storage contracts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.historical_memory.storage import validate_historical_storage
from src.core.historical_memory.store import HistoricalStore


class HistoricalStorageTests(unittest.TestCase):
    def test_required_database_must_be_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "disk"
            root.mkdir()
            status = validate_historical_storage(
                database=Path(directory) / "outside.sqlite3", root=root,
                required=True,
            )
        self.assertFalse(status.healthy)
        self.assertFalse(status.contained)

    def test_missing_mount_fails_without_creating_ephemeral_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            status = validate_historical_storage(
                database=root / "history.sqlite3", root=root, required=True,
            )
            self.assertFalse(root.exists())
        self.assertFalse(status.healthy)
        self.assertIn("absent", status.reason)

    def test_existing_non_mount_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.core.historical_memory.storage.os.path.ismount", return_value=False):
                status = validate_historical_storage(
                    database=root / "history.sqlite3", root=root, required=True,
                )
        self.assertFalse(status.healthy)
        self.assertIn("not a mounted filesystem", status.reason)

    def test_mounted_writable_storage_is_accepted_and_probe_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.core.historical_memory.storage.os.path.ismount", return_value=True):
                status = validate_historical_storage(
                    database=root / "history.sqlite3", root=root, required=True,
                )
            probes = list(root.glob(".dtos-write-probe-*"))
        self.assertTrue(status.healthy)
        self.assertTrue(status.writable)
        self.assertEqual(probes, [])

    def test_unwritable_mount_reports_clear_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.core.historical_memory.storage.os.path.ismount", return_value=True), patch(
                "src.core.historical_memory.storage.os.open", side_effect=PermissionError("denied"),
            ):
                status = validate_historical_storage(
                    database=root / "history.sqlite3", root=root, required=True,
                )
        self.assertFalse(status.healthy)
        self.assertIn("not writable", status.reason)

    def test_atomic_initialization_does_not_replace_valid_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "history.sqlite3"
            first = HistoricalStore(database)
            first.create_job({
                "job_id": "preserved", "league_id": "L",
                "requested_seasons": [], "requested_data_types": [],
                "status": "queued", "created_at": "2026-01-01T00:00:00+00:00",
                "total_steps": 0, "completed_steps": 0,
                "inserted_records": 0, "updated_records": 0,
                "unchanged_records": 0, "skipped_records": 0,
                "failed_records": 0, "retry_count": 0,
                "requested_by": "test", "schema_version": "1",
                "importer_version": "1",
            })
            reopened = HistoricalStore(database)
            jobs = reopened.jobs("L")
        self.assertEqual(jobs[0]["job_id"], "preserved")

    def test_read_model_manifest_is_durable_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoricalStore(Path(directory) / "history.sqlite3")
            cache = HistoricalReadModelCache()
            cache.get(store, "L", {"players": {}})
            manifest_path = Path(directory) / "historical_read_model_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], "1.1")
        self.assertEqual(manifest["cache_key"], cache.metadata()["cache_key"])
        self.assertTrue(manifest["dataset_version"])


if __name__ == "__main__":
    unittest.main()
