from __future__ import annotations

import sqlite3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.history_context.guard import (
    LegacyAccessError, LegacyAccessGuard, legacy_access_guard,
)
from src.core.historical_memory.store import HistoricalStore
from tools import retire_historical_store as retirement
from tools import history_report


class HistoricalStoreRetirementTests(unittest.TestCase):
    def tearDown(self) -> None:
        legacy_access_guard.reset()

    def test_retired_guard_counts_constructor_and_creates_no_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            guard = LegacyAccessGuard(mode="retired")
            with patch("src.core.history_context.guard.HISTORY_DATABASE_FILE", path):
                with self.assertRaises(LegacyAccessError):
                    guard.guard_constructor(path)
            self.assertFalse(path.exists())
            health = guard.health()
            self.assertEqual(health["legacy_create_attempts"], 1)
            self.assertIsNotNone(health["last_attempt_caller"])

    def test_historicalstore_constructor_fails_closed_for_configured_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            legacy_access_guard.mode = "retired"
            with patch("src.core.history_context.guard.HISTORY_DATABASE_FILE", path):
                with self.assertRaises(LegacyAccessError):
                    HistoricalStore(path)
            self.assertFalse(path.exists())
            self.assertEqual(legacy_access_guard.health()["legacy_create_attempts"], 1)

    def test_unrelated_test_store_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "configured.sqlite3"
            test_path = Path(directory) / "fixture.sqlite3"
            with patch("src.core.history_context.guard.HISTORY_DATABASE_FILE", configured):
                store = HistoricalStore(test_path)
                self.assertTrue(store.path.exists())
            self.assertEqual(legacy_access_guard.health()["legacy_create_attempts"], 0)

    def test_retirement_rehearsal_removes_only_database_and_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "legacy.sqlite3"
            shared = root / "dtos_metadata.sqlite3"
            connection = sqlite3.connect(database)
            try:
                for table in retirement.LEGACY_SIGNATURE:
                    connection.execute(f"CREATE TABLE {table}(id INTEGER)")
                connection.commit()
            finally:
                connection.close()
            wal = Path(f"{database}-wal")
            wal.write_bytes(b"legacy-sidecar")
            shared.write_bytes(b"shared")
            with patch.object(retirement, "HISTORY_STORAGE_ROOT", root), patch.object(
                retirement, "_gate", return_value={},
            ), patch.object(retirement, "_open_owners", return_value=[]):
                result = retirement.retire(gate_url="http://unused", database=database)
            self.assertEqual(result["status"], "retired")
            self.assertFalse(database.exists())
            self.assertFalse(wal.exists())
            self.assertTrue(shared.exists())
            self.assertTrue((root / ".historicalstore-retired.json").exists())

    def test_inventory_rejects_unrecognized_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "unknown.sqlite3"
            sqlite3.connect(database).close()
            with patch.object(retirement, "_open_owners", return_value=[]):
                result = retirement.inventory(database)
            self.assertFalse(result["schema_signature_valid"])

    def test_application_startup_does_not_recreate_absent_legacy_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "dtos_history.sqlite3"
            environment = dict(os.environ)
            environment.update({
                "DTOS_HISTORY_STORAGE_ROOT": str(root),
                "DTOS_HISTORY_DB_FILE": str(legacy),
                "DTOS_METADATA_DB_FILE": str(root / "metadata.sqlite3"),
                "DTOS_INTELLIGENCE_CHECKPOINT_FILE": str(root / "intelligence.sqlite3"),
                "DTOS_PROJECTION_DB_FILE": str(root / "projections.sqlite3"),
                "DTOS_SLEEPER_SEASON_CACHE_ROOT": str(root / "season-cache"),
                "DTOS_CACHE_FILE": str(root / "cache.json"),
                "DTOS_DURABLE_HISTORY_REQUIRED": "0",
                "DTOS_LIVE_VISUAL_CAPTURE": "0",
            })
            script = (
                "import json; import dtos_app; "
                "from pathlib import Path; from config import HISTORY_DATABASE_FILE; "
                "from src.core.history_context import legacy_access_guard; "
                "print(json.dumps({'exists': Path(HISTORY_DATABASE_FILE).exists(), "
                "'health': legacy_access_guard.health()}))"
            )
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=Path(__file__).parents[1],
                env=environment, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evidence = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertFalse(evidence["exists"])
            self.assertTrue(evidence["health"]["historicalstore_retired"])
            self.assertEqual(evidence["health"]["legacy_create_attempts"], 0)

    def test_gate_requires_retired_zero_access_contract(self) -> None:
        valid = {
            "historicalstore_retired": True, "legacy_read_attempts": 0,
            "legacy_write_attempts": 0, "legacy_create_attempts": 0,
            "callers": {},
        }
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            "legacy_historical_store": valid,
        }).encode()
        with patch("urllib.request.urlopen", return_value=response):
            self.assertEqual(retirement._gate("http://gate"), valid)

    def test_legacy_history_report_cannot_open_or_create_database(self) -> None:
        with patch("builtins.print") as output:
            self.assertEqual(history_report.main(), 2)
        payload = json.loads(output.call_args.args[0])
        self.assertEqual(payload["status"], "retired")
        self.assertEqual(payload["replacement"], "/api/history/coverage")


if __name__ == "__main__":
    unittest.main()
