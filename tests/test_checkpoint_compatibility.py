"""Season-scoped historical checkpoint compatibility regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.historical_memory.jobs import ImportJob
from src.core.historical_memory.models import IMPORTER_VERSION
from src.core.historical_memory.store import HistoricalStore


class CheckpointCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "history.sqlite3"
        self.store = HistoricalStore(self.path)

    def identity(self, player: str, observed: str = "2026-01-01") -> None:
        self.store.upsert_identity(
            player, "Sleeper", player, player, 100, observed,
            {"provider_ids": {"GSIS": f"gsis-{player}"}},
        )

    def evidence(self, league: str, season: int, player: str) -> None:
        self.store.append(
            record_key=f"{league}:player_week:{season}:1:{player}:1.2",
            entity_type="player_week", league_id=league, season=season, week=1,
            player_id=player, source_record_id=f"{season}:1:{player}",
            observed_at=f"{season}-09-01", retrieved_at=f"{season}-09-01",
            provider="nflverse", availability="observed", confidence=100,
            calculation_method="player_week_enrichment", schema_version="1.0",
            payload={"points": 10.0},
        )

    def checkpoint(self, league: str, season: int, status: str = "completed") -> None:
        job = ImportJob(
            self.store, league, (season,), ("player_week",), provider="nflverse",
        )
        job.create()
        self.store.checkpoint(
            checkpoint_key=f"{league}:{season}:player_week:nflverse:{IMPORTER_VERSION}",
            job_id=job.job_id, league_id=league, season=season, week=None,
            data_type="player_week", provider="nflverse",
            importer_version=IMPORTER_VERSION, status=status,
            completed_at="2026-01-02",
        )

    def progress(self, league: str, *seasons: int) -> dict[str, object]:
        return self.store.canonical_enrichment_progress(
            league, tuple(seasons), provider="nflverse",
            importer_version=IMPORTER_VERSION,
        )

    def make_legacy(self, league: str, season: int) -> None:
        with self.store.connection() as connection:
            connection.execute(
                """UPDATE import_checkpoints SET identity_generation=0,
                identity_dependency_digest=NULL,compatibility_status=NULL,
                compatibility_reason=NULL,compatibility_mismatch=NULL
                WHERE league_id=? AND season=? AND provider='nflverse'""",
                (league, season),
            )

    def test_unrelated_remap_does_not_invalidate_season(self) -> None:
        self.identity("used")
        self.evidence("L", 2022, "used")
        self.checkpoint("L", 2022)
        self.identity("unrelated")
        self.store.upsert_identity(
            "replacement", "Sleeper", "unrelated", "Replacement", 90,
            "2026-02-01", {"provider_ids": {"GSIS": "changed"}},
        )
        self.assertEqual(self.progress("L", 2022)["completed_seasons"], [2022])

    def test_referenced_remap_invalidates_only_affected_seasons(self) -> None:
        for season, player in ((2021, "shared"), (2022, "other"), (2023, "shared")):
            self.identity(player)
            self.evidence("L", season, player)
            self.checkpoint("L", season)
        self.store.upsert_identity(
            "remapped", "Sleeper", "shared", "Remapped", 100, "2026-03-01",
            {"provider_ids": {"GSIS": "new-shared"}},
        )
        result = self.progress("L", 2021, 2022, 2023)
        self.assertEqual(result["completed_seasons"], [2022])
        self.assertEqual(result["invalidated_seasons"], [2021, 2023])
        self.assertEqual(
            result["compatibility"]["2021"]["reason_code"],
            "referenced_identity_dependency_changed",
        )

    def test_display_name_and_observation_changes_remain_compatible(self) -> None:
        self.identity("used")
        self.evidence("L", 2022, "used")
        self.checkpoint("L", 2022)
        before = self.store.identity_generations()["mapping"]
        self.store.upsert_identity(
            "used", "Sleeper", "used", "New display name", 100,
            "2026-04-01", {"provider_ids": {"GSIS": "gsis-used"}},
        )
        self.assertEqual(self.store.identity_generations()["mapping"], before)
        self.assertEqual(self.progress("L", 2022)["completed_seasons"], [2022])

    def test_legacy_valid_evidence_migrates_metadata_only_and_is_idempotent(self) -> None:
        self.identity("used")
        self.evidence("L", 2022, "used")
        self.checkpoint("L", 2022)
        self.make_legacy("L", 2022)
        before = self.store.records("L")[1]
        self.store = HistoricalStore(self.path)
        first = self.store.checkpoints("L")[0]
        self.assertEqual(first["compatibility_status"], "compatible")
        self.assertEqual(first["compatibility_reason"], "compatible")
        with self.store.connection() as connection:
            audit_count = connection.execute(
                "SELECT count(*) FROM checkpoint_compatibility_audit"
            ).fetchone()[0]
        self.store = HistoricalStore(self.path)
        with self.store.connection() as connection:
            repeated = connection.execute(
                "SELECT count(*) FROM checkpoint_compatibility_audit"
            ).fetchone()[0]
        self.assertEqual(repeated, audit_count)
        self.assertEqual(self.store.records("L")[1], before)

    def test_legacy_missing_or_unresolved_evidence_remains_invalid(self) -> None:
        self.checkpoint("missing", 2022)
        self.make_legacy("missing", 2022)
        self.evidence("unresolved", 2022, "unknown")
        self.checkpoint("unresolved", 2022)
        self.make_legacy("unresolved", 2022)
        self.store = HistoricalStore(self.path)
        rows = {row["league_id"]: row for league in ("missing", "unresolved")
                for row in self.store.checkpoints(league)}
        self.assertEqual(rows["missing"]["compatibility_reason"], "evidence_incomplete")
        self.assertEqual(rows["unresolved"]["compatibility_reason"], "identity_resolution_failed")
        self.assertRegex(rows["unresolved"]["compatibility_mismatch"], r"^[0-9a-f]{16}$")

    def test_identity_audit_only_records_committed_material_changes(self) -> None:
        self.identity("used")
        with self.store.connection() as connection:
            initial = connection.execute(
                "SELECT count(*) FROM identity_mapping_audit"
            ).fetchone()[0]
        self.assertFalse(self.store.upsert_identity(
            "used", "Sleeper", "used", "used", 100, "2026-01-01",
            {"provider_ids": {"GSIS": "gsis-used"}},
        ))
        self.store.upsert_identity(
            "changed", "Sleeper", "used", "Changed", 100, "2026-02-01",
            {"provider_ids": {"GSIS": "changed"}}, workflow_run_id="run-safe",
        )
        with self.store.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM identity_mapping_audit ORDER BY audit_id"
            ).fetchall()
        self.assertEqual(len(rows), initial + 1)
        self.assertEqual(rows[-1]["workflow_run_id"], "run-safe")
        self.assertEqual(rows[-1]["committed"], 1)

    def test_cross_league_and_pending_checkpoint_isolation(self) -> None:
        self.identity("used")
        for league in ("A", "B"):
            self.evidence(league, 2025, "used")
            self.checkpoint(league, 2025)
        self.checkpoint("A", 2026, "pending")
        self.store.upsert_identity(
            "changed", "Sleeper", "used", "Changed", 100, "2026-05-01",
            {"provider_ids": {"GSIS": "changed"}},
        )
        self.assertEqual(self.progress("A", 2025, 2026)["pending_seasons"], [2026])
        self.assertEqual(self.progress("A", 2025, 2026)["invalidated_seasons"], [2025])
        self.assertEqual(self.progress("B", 2025)["invalidated_seasons"], [2025])


if __name__ == "__main__":
    unittest.main()
