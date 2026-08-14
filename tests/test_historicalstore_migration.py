from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.history import capture_current_state, history_records
from src.core.history_context.guard import LegacyAccessError, LegacyAccessGuard
from src.core.history_context.metadata import MinimalMetadataStore
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore


class HistoricalStoreMigrationTests(unittest.TestCase):
    def test_shadow_guard_fails_closed_and_accounts_for_attempts(self) -> None:
        guard = LegacyAccessGuard(mode="shadow_forbidden")
        with self.assertRaises(LegacyAccessError):
            guard.read()
        with self.assertRaises(LegacyAccessError):
            guard.write()
        health = guard.health()
        self.assertEqual(health["legacy_read_attempts"], 1)
        self.assertEqual(health["legacy_write_attempts"], 1)
        self.assertEqual(health["status"], "failed")

    def test_importing_legacy_package_does_not_create_or_open_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "legacy.sqlite3"
            metadata = root / "metadata.sqlite3"
            script = (
                "import json; import src.core.historical_memory as module; "
                "print(json.dumps({'legacy_exists': __import__('pathlib').Path("
                "__import__('os').environ['DTOS_HISTORY_DB_FILE']).exists(), "
                "'canonical': type(module.historical_store).__name__, "
                "'status': module.historical_storage_status['status']}))"
            )
            environment = dict(os.environ)
            environment.update({
                "DTOS_HISTORY_DB_FILE": str(legacy),
                "DTOS_METADATA_DB_FILE": str(metadata),
                "DTOS_CACHE_FILE": str(root / "cache.json"),
                "DTOS_DURABLE_HISTORY_REQUIRED": "0",
            })
            result = subprocess.run(
                [sys.executable, "-c", script], cwd=Path(__file__).parents[1],
                env=environment, capture_output=True, text=True, check=True,
                timeout=30,
            )
            evidence = json.loads(result.stdout.strip())
            self.assertFalse(evidence["legacy_exists"])
            self.assertEqual(evidence["canonical"], "CanonicalHistoryStore")
            self.assertEqual(evidence["status"], "dormant")

    def test_current_capture_updates_only_bounded_operational_context(self) -> None:
        store = CanonicalHistoryStore()
        payload = {
            "league": {"league_id": "L", "season": "2026"},
            "normalized_players": {
                "p1": {"name": "Player One", "position": "QB"},
            },
            "teams": [],
        }
        with patch("services.history.historical_store", store):
            result = capture_current_state(payload, "2026-08-14T00:00:00+00:00")
        self.assertEqual(result, {
            "written": 0, "unchanged": 0, "legacy_write_attempts": 0,
        })
        self.assertEqual(store.identity_for_provider_id("p1")["display_name"], "Player One")

    def test_sleeper_cache_is_canonical_history_without_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            facts = {
                "league": {"league_id": "historic", "name": "League"},
                "users": [], "rosters": [],
                "matchups": {"1": [{
                    "matchup_id": 1, "roster_id": 1, "points": 20,
                    "players_points": {"p1": 20}, "starters": ["p1"],
                }]},
                "transactions": {}, "drafts": [], "draft_picks": [],
                "traded_picks": [], "winners_bracket": [], "losers_bracket": [],
            }
            cache.write(cache.normalize("L", 2025, facts))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache), patch(
                "services.history.historical_store", store,
            ):
                result = history_records("L", "player_week", season=2025)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["records"][0]["player_id"], "p1")

    def test_metadata_store_persists_only_compact_system_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory) / "metadata.sqlite3")
            store.record_season_cache_checkpoint("L", 2025, "checksum", "complete")
            store.record_sync_generation("L", "generation")
            health = store.health()
            self.assertEqual(health["ownership"], "permanent_system_metadata")
            self.assertLess(health["bytes"], 1_000_000)
            raw = store.path.read_bytes()
            self.assertNotIn(b"players_points", raw)
            self.assertNotIn(b"provider_payload", raw)

    def test_plain_legacy_metadata_uuid_is_normalized_without_archive_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory) / "metadata.sqlite3")
            with store.connection() as connection:
                connection.execute(
                    "UPDATE metadata SET value='plainuuid' "
                    "WHERE namespace='system' AND key='database_uuid'",
                )
            self.assertEqual(store.database_uuid(), "plainuuid")
            with store.connection() as connection:
                value = connection.execute(
                    "SELECT value FROM metadata WHERE namespace='system' "
                    "AND key='database_uuid'",
                ).fetchone()[0]
            self.assertEqual(json.loads(value), "plainuuid")

    def test_league_cache_namespaces_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            for league, name in (("A", "Alpha"), ("B", "Beta")):
                facts = {"league": {"league_id": league, "name": name}}
                cache.write(cache.normalize(league, 2025, facts))
            self.assertNotEqual(cache.path("A", 2025), cache.path("B", 2025))
            self.assertEqual(cache.read("A", 2025).facts["league"]["name"], "Alpha")
            self.assertEqual(cache.read("B", 2025).facts["league"]["name"], "Beta")


if __name__ == "__main__":
    unittest.main()
