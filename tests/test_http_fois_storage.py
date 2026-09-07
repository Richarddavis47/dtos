"""The canonical HTTP fixture must not depend on ambient FOIS SQLite state."""
import os
from contextlib import closing
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.validation.http_worker import execute, isolated_default_fois_storage, validation_startup_schedule


class HttpFoisStorageTests(unittest.TestCase):
    def test_fixture_schedule_matches_linux_and_restores_after_failure(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                with validation_startup_schedule():
                    self.assertEqual(os.environ["DTOS_BACKGROUND_START_DELAY"], "0")
                    raise RuntimeError("fixture failure")
            self.assertNotIn("DTOS_BACKGROUND_START_DELAY", os.environ)
        for delay in ("0", "30", "60"):
            with patch.dict(os.environ, {"DTOS_BACKGROUND_START_DELAY": delay}, clear=True):
                with validation_startup_schedule():
                    self.assertEqual(os.environ["DTOS_BACKGROUND_START_DELAY"], delay)
                self.assertEqual(os.environ["DTOS_BACKGROUND_START_DELAY"], delay)

    def test_real_database_is_owned_and_cleaned_even_after_failure(self):
        from src.core.fois.repository import FOISRepository

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                with isolated_default_fois_storage():
                    path = Path(os.environ["DTOS_FOIS_DB_FILE"])
                    repository = FOISRepository(path)
                    self.assertEqual(repository.league("fixture", "fixture-model"), ())
                    self.assertTrue(path.is_file())
                    raise RuntimeError("fixture failure")
            self.assertFalse(path.parent.exists())
            self.assertNotIn("DTOS_FOIS_DB_FILE", os.environ)

    def test_explicit_storage_overrides_are_preserved(self):
        for name in ("DTOS_FOIS_DB_FILE", "DTOS_HISTORY_STORAGE_ROOT", "DTOS_INTELLIGENCE_CHECKPOINT_FILE", "DTOS_DATA_WAREHOUSE_FILE"):
            with self.subTest(name=name), patch.dict(os.environ, {name: "explicit"}, clear=True):
                with isolated_default_fois_storage():
                    self.assertEqual(os.environ[name], "explicit")
                self.assertEqual(dict(os.environ), {name: "explicit"})

    def test_warehouse_is_durable_but_run_owned_not_ambient(self):
        from src.core.data_platform import SnapshotWarehouse

        with patch.dict(os.environ, {}, clear=True):
            with isolated_default_fois_storage():
                path = Path(os.environ["DTOS_DATA_WAREHOUSE_FILE"])
                self.assertEqual(path.parent, Path(os.environ["DTOS_FOIS_DB_FILE"]).parent)
                self.assertEqual(SnapshotWarehouse(path).history("fixture"), ())
                path.write_text("[]", encoding="utf-8")
                self.assertTrue(path.is_file())
            self.assertFalse(path.exists())
            self.assertNotIn("DTOS_DATA_WAREHOUSE_FILE", os.environ)

    def test_checkpoint_schema_is_current_and_run_owned(self):
        import sqlite3
        from src.core.intelligence_memory.store import IntelligenceCheckpointStore

        with patch.dict(os.environ, {}, clear=True):
            with isolated_default_fois_storage():
                path = Path(os.environ["DTOS_INTELLIGENCE_CHECKPOINT_FILE"])
                IntelligenceCheckpointStore(path)
                with closing(sqlite3.connect(path)) as connection:
                    schema = connection.execute(
                        "SELECT sql FROM sqlite_master WHERE name='global_market_observations'",
                    ).fetchone()[0]
                self.assertNotIn("UNIQUE(asset_id, market_context_id, semantic_fingerprint)", schema)
                self.assertEqual(path.parent, Path(os.environ["DTOS_FOIS_DB_FILE"]).parent)
            self.assertFalse(path.parent.exists())
            self.assertNotIn("DTOS_INTELLIGENCE_CHECKPOINT_FILE", os.environ)

    def test_independent_runs_do_not_share_database(self):
        with patch.dict(os.environ, {}, clear=True):
            with isolated_default_fois_storage():
                first = os.environ["DTOS_FOIS_DB_FILE"]
            with isolated_default_fois_storage():
                self.assertNotEqual(first, os.environ["DTOS_FOIS_DB_FILE"])

    def test_worker_owns_storage_after_server_startup_failure(self):
        observed = []

        def fail_start(*_args):
            observed.append(Path(os.environ["DTOS_FOIS_DB_FILE"]))
            self.assertTrue(observed[0].parent.exists())
            raise RuntimeError("startup failure")

        with patch.dict(os.environ, {}, clear=True), patch(
            "tools.validation.http_worker.TrackedServer.start", side_effect=fail_start,
        ), patch("tools.validation.http_worker.windows_process_inventory", return_value=[]):
            result = execute("isolated-storage-test")
            self.assertFalse(result.passed)
            self.assertEqual(result.process_cleanup, "PASS")
            self.assertNotIn("DTOS_FOIS_DB_FILE", os.environ)
        self.assertFalse(observed[0].parent.exists())
