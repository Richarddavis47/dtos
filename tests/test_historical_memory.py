from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.history import capture_current_state
from src.core.historical_memory.aggregation import aggregate_production
from src.core.historical_memory.importer import HistoricalImporter
from src.core.historical_memory.scoring import calculate_fantasy_points, normalize_usage
from src.core.historical_memory.signals import role_trend_signal
from src.core.historical_memory.store import HistoricalStore
from src.core.historical_memory.valuation import apply_historical_evidence
from tests.test_player_api import fixture_data


def provider() -> dict[str, object]:
    leagues = {
        "L2": {"league_id": "L2", "season": "2022", "previous_league_id": "L1", "name": "New Name", "scoring_settings": {"rec": 1}, "roster_positions": ["QB", "BN"], "settings": {}, "total_rosters": 1},
        "L1": {"league_id": "L1", "season": "2021", "previous_league_id": None, "name": "Old Name", "scoring_settings": {"rec": .5}, "roster_positions": ["QB", "BN"], "settings": {}, "total_rosters": 1},
    }
    result: dict[str, object] = {}
    result["/state/nfl"] = {"season": "2023", "season_type": "off", "week": 1}
    for league_id, league in leagues.items():
        result[f"/league/{league_id}"] = league
        result[f"/league/{league_id}/users"] = [{"user_id": "owner", "display_name": "Owner", "metadata": {"team_name": league["name"]}}]
        result[f"/league/{league_id}/rosters"] = [{"roster_id": 1, "owner_id": "owner", "settings": {"wins": 1, "losses": 0, "fpts": 100}}]
        result[f"/league/{league_id}/drafts"] = []
        result[f"/league/{league_id}/winners_bracket"] = []
        result[f"/league/{league_id}/losers_bracket"] = []
        for week in range(1, 19):
            result[f"/league/{league_id}/matchups/{week}"] = (
                [{"roster_id": 1, "matchup_id": 1, "players": ["same-name-a", "same-name-b"], "starters": ["same-name-a"], "players_points": {"same-name-a": 10.0, "same-name-b": 0.0}, "points": 10.0}]
                if week == 1 else []
            )
            result[f"/league/{league_id}/transactions/{week}"] = []
    return result


class HistoricalMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        rows = provider()

        async def fetch(path: str) -> object:
            return rows.get(path, [])

        self.importer = HistoricalImporter(self.store, fetch)

    async def asyncTearDown(self) -> None:
        self.temp.cleanup()

    async def test_team_rename_preserves_prior_name(self) -> None:
        result = await self.importer.backfill("L2")
        self.assertEqual(result["status"], "complete")
        count, rows = self.store.records("L2", "franchise_identity")
        self.assertEqual(count, 2)
        self.assertEqual({row["payload"]["dtos_display_name"] for row in rows}, {"Old Name", "New Name"})

    async def test_rerun_is_idempotent(self) -> None:
        first = await self.importer.backfill("L2")
        second = await self.importer.backfill("L2")
        self.assertGreater(first["records_written"], 0)
        self.assertEqual(second["records_written"], 0)
        self.assertEqual(second["records_unchanged"], first["records_written"])
        self.assertEqual(second["reconciliation"]["chosen_source"], "Sleeper")

    async def test_weekly_roster_is_versioned_by_season_and_week(self) -> None:
        await self.importer.backfill("L2")
        count, rows = self.store.records("L2", "weekly_roster")
        self.assertEqual(count, 2)
        self.assertEqual({row["season"] for row in rows}, {2021, 2022})
        self.assertTrue(all(row["week"] == 1 for row in rows))

    async def test_matchup_outcome_and_standings_rank_are_deterministic(self) -> None:
        await self.importer.backfill("L2")
        matchup_count, matchups = self.store.records("L2", "matchup")
        standing_count, standings = self.store.records("L2", "season_standing")
        self.assertEqual(matchup_count, 2)
        self.assertTrue(all(row["payload"]["tie"] is False for row in matchups))
        self.assertEqual(standing_count, 2)
        self.assertTrue(all(row["payload"]["rank"] == 1 for row in standings))

    async def test_future_matchup_shells_are_not_observed_as_zero(self) -> None:
        rows = provider()
        rows["/state/nfl"] = {"season": "2022", "season_type": "pre", "week": 1}

        async def fetch(path: str) -> object:
            return rows.get(path, [])

        store = HistoricalStore(Path(self.temp.name) / "preseason.sqlite3")
        await HistoricalImporter(store, fetch).backfill("L2")
        current_count, _ = store.records("L2", "player_week", season=2022)
        historical_count, _ = store.records("L2", "player_week", season=2021)
        self.assertEqual(current_count, 0)
        self.assertGreater(historical_count, 0)

    async def test_duplicate_display_names_do_not_merge_player_ids(self) -> None:
        await self.importer.backfill("L2")
        count_a, _ = self.store.records("L2", "player_week", player_id="same-name-a")
        count_b, _ = self.store.records("L2", "player_week", player_id="same-name-b")
        self.assertEqual((count_a, count_b), (2, 2))

    async def test_partial_failure_is_checkpointed(self) -> None:
        async def broken(path: str) -> object:
            if path.endswith("/users"):
                raise RuntimeError("provider stopped")
            return provider().get(path, [])

        result = await HistoricalImporter(self.store, broken).backfill("L2")
        self.assertEqual(result["status"], "partial")
        self.assertIn("2021:league", result["checkpoint"])
        self.assertTrue(result["errors"])

    def test_custom_scoring_is_season_specific_and_reproducible(self) -> None:
        ppr = calculate_fantasy_points({"rec": 5, "rec_yd": 50}, {"rec": 1, "rec_yd": .1})
        half = calculate_fantasy_points({"rec": 5, "rec_yd": 50}, {"rec": .5, "rec_yd": .1})
        self.assertEqual(ppr["fantasy_points"], 10)
        self.assertEqual(half["fantasy_points"], 7.5)

    def test_missing_stats_are_not_zero(self) -> None:
        result = calculate_fantasy_points(None, {"rec": 1})
        self.assertIsNone(result["fantasy_points"])
        self.assertEqual(result["availability"], "unavailable")

    def test_observed_zero_differs_from_unavailable_usage(self) -> None:
        self.assertEqual(normalize_usage(0, provider_supported=True)["availability"], "observed")
        self.assertEqual(normalize_usage(None, provider_supported=True)["availability"], "unavailable")
        self.assertEqual(normalize_usage(None, provider_supported=False)["availability"], "provider_not_supported")

    def test_aggregation_is_deterministic(self) -> None:
        summary = aggregate_production([{"fantasy_points": 10}, {"fantasy_points": 20}, {"fantasy_points": None}])
        self.assertEqual(summary["season_total"], 30)
        self.assertEqual(summary["points_per_game"], 15)
        self.assertEqual(summary["games_played"], 2)

    def test_empty_aggregation_preserves_unavailable(self) -> None:
        summary = aggregate_production([{"fantasy_points": None}])
        self.assertIsNone(summary["season_total"])
        self.assertEqual(summary["availability"], "unavailable")

    def test_role_signal_requires_samples_and_is_explainable(self) -> None:
        insufficient = role_trend_signal("snap share", [.2, .3], "weeks 1-2")
        growth = role_trend_signal("snap share", [.2, .25, .5, .6], "weeks 1-4")
        self.assertEqual(insufficient.status, "insufficient_data")
        self.assertEqual(growth.status, "role_growth")
        self.assertTrue(growth.evidence)

    def test_historical_valuation_is_confidence_capped(self) -> None:
        contribution = apply_historical_evidence(
            700, "RB", {"games_played": 16, "points_per_game": 20},
        )
        self.assertLessEqual(contribution.weight, .10)
        self.assertLessEqual(abs(contribution.adjusted_value - 700), 20)
        self.assertTrue(contribution.evidence)

    def test_small_sample_does_not_change_value(self) -> None:
        contribution = apply_historical_evidence(
            700, "WR", {"games_played": 3, "points_per_game": 30},
        )
        self.assertEqual(contribution.adjusted_value, 700)
        self.assertEqual(contribution.weight, 0)

    def test_identity_versions_are_append_only(self) -> None:
        self.store.upsert_identity("p1", "Sleeper", "1", "Name", 100, "2021-01-01", {})
        self.store.upsert_identity("p1", "Sleeper", "1", "New Name", 100, "2022-01-01", {})
        self.assertEqual(len(self.store.identities()), 2)

    def test_migration_version_is_recorded(self) -> None:
        with self.store.connection() as connection:
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations")]
        self.assertEqual(versions, [1])

    def test_current_team_and_prediction_snapshots_are_immutable(self) -> None:
        data = fixture_data()
        data["league"]["league_id"] = "L2"
        data["league"]["season"] = "2022"
        data["week"] = 1
        data["normalized_players"] = {}
        data["market_data"] = {"providers": {}}
        expected_franchises = {
            f"L2:franchise:{team['roster_id']}" for team in data["teams"]
        }
        observations = (
            "2022-09-01T00:00:00+00:00",
            "2022-09-08T00:00:00+00:00",
        )
        with patch("services.history.historical_store", self.store):
            first = capture_current_state(data, observations[0])
            duplicate = capture_current_state(data, observations[0])
            original_count, original_rows = self.store.records(
                "L2", "team_intelligence_snapshot",
            )
            original_payloads = {
                row["franchise_id"]: row["payload"] for row in original_rows
            }
            data["teams"][0]["points_for"] = 1500
            later = capture_current_state(data, observations[1])
        team_count, team_rows = self.store.records(
            "L2", "team_intelligence_snapshot", season=2022,
        )
        prediction_count, prediction_rows = self.store.records(
            "L2", "prediction", season=2022,
        )
        expected_per_type = len(expected_franchises) * len(observations)
        self.assertGreater(first["written"], 0)
        self.assertEqual(duplicate["written"], 0)
        self.assertGreater(later["written"], 0)
        self.assertEqual(original_count, len(expected_franchises))
        self.assertEqual(team_count, expected_per_type)
        self.assertEqual(prediction_count, expected_per_type)
        self.assertEqual(
            {row["franchise_id"] for row in team_rows}, expected_franchises,
        )
        self.assertEqual(
            {row["franchise_id"] for row in prediction_rows},
            expected_franchises,
        )
        team_identities = {
            (
                row["league_id"], row["franchise_id"], row["season"],
                row["week"], row["observed_at"],
                row["payload"]["snapshot_type"],
                row["payload"]["model_version"],
            )
            for row in team_rows
        }
        prediction_identities = {
            (
                row["league_id"], row["franchise_id"], row["season"],
                row["week"], row["observed_at"],
                row["payload"]["snapshot_type"],
                row["payload"]["model_version"],
            )
            for row in prediction_rows
        }
        self.assertEqual(len(team_identities), expected_per_type)
        self.assertEqual(len(prediction_identities), expected_per_type)
        earliest_rows = {
            row["franchise_id"]: row["payload"]
            for row in team_rows
            if row["observed_at"] == observations[0]
        }
        self.assertEqual(earliest_rows, original_payloads)
        unrelated_count, _ = self.store.records(
            "not-L2", "team_intelligence_snapshot",
        )
        self.assertEqual(unrelated_count, 0)
