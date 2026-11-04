"""Season archive API and presentation contract regressions."""
from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.history import create_history_router
from services.history import season_archive, season_archive_section
from src.core.historical_memory.store import HistoricalStore


class SeasonArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = HistoricalStore(Path(self.temporary.name) / "history.sqlite3")
        self.observed = "2025-12-31T00:00:00+00:00"
        self._append("league_season", "league", {"league_name": "Test League"})
        for roster_id, team, gm, wins in (
            (1, "Champions", "GM One", 10),
            (2, "Runners Up", "GM Two", 8),
        ):
            franchise = f"L:franchise:{roster_id}"
            self._append(
                "franchise_identity", str(roster_id),
                {
                    "sleeper_roster_id": str(roster_id),
                    "franchise_id": franchise,
                    "dtos_display_name": team,
                    "sleeper_username": gm,
                },
                franchise_id=franchise,
            )
            self._append(
                "season_standing", str(roster_id),
                {
                    "roster_id": roster_id, "rank": roster_id,
                    "wins": wins, "losses": 14 - wins, "ties": 0,
                    "points_for": 1500 - roster_id, "points_against": 1400,
                },
                franchise_id=franchise,
            )
        self._append(
            "playoff_result", "placements",
            {
                "placements": {"1": 1, "2": 2},
                "champion_roster_id": 1, "runner_up_roster_id": 2,
            },
        )
        self._append(
            "matchup", "1:1",
            {
                "matchup_id": "1", "franchises": [1, 2],
                "team_points": {"1": 120.5, "2": 110.0},
                "winner": 1, "tie": False, "postseason_context": False,
            },
            week=1,
        )
        self._append("trade", "trade-1", {"type": "trade"}, week=2)
        self._append("draft", "draft-1", {"picks_count": 1})
        self._append(
            "draft_pick", "draft-1:1",
            {"draft_id": "draft-1", "player_id": "p1", "pick_no": 1},
            player_id="p1",
        )
        self.store.upsert_identity(
            "p1", "Sleeper", "p1", "Player One", 100, self.observed,
            {"position": "QB"},
        )
        self._append(
            "player_week", "1:1:p1", {"fantasy_points": 25.0},
            week=1, player_id="p1", franchise_id="L:franchise:1",
        )

    def _append(
        self, entity: str, source: str, payload: dict, *, week: int | None = None,
        player_id: str | None = None, franchise_id: str | None = None,
    ) -> None:
        self.store.append(
            record_key=f"L:{entity}:2025:{week}:{source}",
            entity_type=entity, league_id="L", season=2025, week=week,
            franchise_id=franchise_id, player_id=player_id,
            source_record_id=source, observed_at=self.observed,
            retrieved_at=self.observed, provider="Sleeper",
            availability="observed", confidence=100,
            calculation_method="test", schema_version="1.0", payload=payload,
        )

    def test_archive_reconciles_human_standings_and_champion(self) -> None:
        with patch("services.history.historical_store", self.store):
            archive = season_archive("L", 2025)
        self.assertEqual(archive["champion"]["team_name"], "Champions")
        self.assertEqual(archive["standings"][0]["gm_name"], "GM One")
        self.assertEqual(archive["standings"][0]["postseason_finish"], 1)
        self.assertEqual(archive["provider_requests"], 0)

    def test_archive_exposes_week_draft_transaction_and_leader_context(self) -> None:
        with patch("services.history.historical_store", self.store):
            archive = season_archive("L", 2025)
        self.assertEqual(archive["counts"]["matchups"], 1)
        self.assertEqual(archive["counts"]["transactions"], 1)
        self.assertEqual(archive["counts"]["draft_picks"], 1)
        self.assertEqual(archive["leaders"][0]["player_name"], "Player One")

    def test_standings_section_does_not_hydrate_unrelated_evidence(self) -> None:
        calls: list[str | None] = []
        original = self.store.records

        def observed_records(league_id, entity_type=None, **kwargs):
            calls.append(entity_type)
            return original(league_id, entity_type, **kwargs)

        with patch("services.history.historical_store", self.store):
            with patch.object(self.store, "records", side_effect=observed_records):
                result = season_archive_section("L", 2025, "standings")
        self.assertEqual(len(result["standings"]), 2)
        self.assertNotIn("player_week", calls)
        self.assertNotIn("transaction", calls)
        self.assertNotIn("trade", calls)
        self.assertNotIn("matchup", calls)
        self.assertNotIn("draft_pick", calls)

    def test_leaders_use_database_aggregation_without_identity_n_plus_one(self) -> None:
        with patch("services.history.historical_store", self.store):
            with patch.object(
                self.store, "identity_for_provider_id",
                side_effect=AssertionError("identity N+1 is prohibited"),
            ):
                result = season_archive_section("L", 2025, "leaders")
        self.assertEqual(result["player_week_count"], 1)
        self.assertEqual(result["leaders"][0]["player_name"], "Player One")

    def test_leader_query_plan_is_season_scoped(self) -> None:
        query = """SELECT player_id,
        SUM(CAST(json_extract(payload, '$.fantasy_points') AS REAL)) AS points
        FROM historical_records INDEXED BY idx_history_season_player
        WHERE league_id=? AND entity_type='player_week' AND season=?
        AND player_id IS NOT NULL
        GROUP BY player_id ORDER BY points DESC,player_id LIMIT 40"""
        with self.store.connection() as connection:
            plan = " ".join(
                str(row[3]) for row in connection.execute(
                    "EXPLAIN QUERY PLAN " + query, ("L", 2025),
                )
            )
        self.assertIn("idx_history_season_player", plan)
        self.assertIn("league_id=? AND entity_type=? AND season=?", plan)

    def test_leader_identity_resolution_uses_one_bounded_query(self) -> None:
        statements: list[str] = []
        original_connection = self.store.connection

        @contextmanager
        def traced_connection():
            with original_connection() as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        with patch.object(self.store, "connection", traced_connection):
            count, leaders = self.store.season_player_leaders("L", 2025)
        selects = [
            statement for statement in statements
            if statement.lstrip().upper().startswith(("SELECT", "WITH"))
        ]
        self.assertEqual(count, 1)
        self.assertEqual(len(leaders), 1)
        self.assertEqual(len(selects), 3)
        self.assertEqual(sum("current_player_identity" in item for item in selects), 1)

    def test_optimized_leaders_match_reference_semantics(self) -> None:
        count, rows = self.store.records(
            "L", "player_week", season=2025, limit=10_000,
        )
        totals: dict[str, float] = {}
        for row in rows:
            player_id = str(row["player_id"])
            totals[player_id] = totals.get(player_id, 0.0) + float(
                row["payload"]["fantasy_points"]
            )
        expected = [
            (player_id, round(points, 2))
            for player_id, points in sorted(
                totals.items(), key=lambda item: (-item[1], item[0]),
            )
        ]
        optimized_count, optimized = self.store.season_player_leaders("L", 2025)
        self.assertEqual(optimized_count, count)
        self.assertEqual(
            [(row["player_id"], round(float(row["points"]), 2)) for row in optimized],
            expected,
        )

    def test_section_cache_is_scoped_to_store_and_dataset_generation(self) -> None:
        with patch("services.history.historical_store", self.store):
            first = season_archive_section("L", 2025, "draft")
            again = season_archive_section("L", 2025, "draft")
            self.assertEqual(first, again)
            self._append("draft_pick", "draft-1:2", {"pick_no": 2})
            changed = season_archive_section("L", 2025, "draft")
        self.assertEqual(len(first["picks"]), 1)
        self.assertEqual(len(changed["picks"]), 2)

    def test_routes_are_clickable_and_consistent(self) -> None:
        app = FastAPI()
        app.include_router(create_history_router(
            league_id="L", page=lambda title, body: HTMLResponse(title + body),
        ))
        with patch("routes.history.season_archive") as archive:
            with patch("routes.history.history_records") as records:
                records.return_value = {"count": 1, "records": [{"season": 2025, "payload": {"league_name": "Test"}}]}
                archive.return_value = {
                    "season": 2025, "display_status": "Complete",
                    "standings": [{"rank": 1, "team_name": "Champions", "gm_name": "GM One", "franchise_id": "L:franchise:1", "wins": 10, "losses": 4, "points_for": 1500, "points_against": 1400, "postseason_finish": 1}],
                    "weeks": [], "champion": {"team_name": "Champions"},
                    "runner_up": {"team_name": "Runners Up"},
                    "leaders": [], "availability": {"playoffs": True},
                    "counts": {"matchups": 0, "transactions": 0, "draft_picks": 0},
                }
                client = TestClient(app)
                response = client.get("/history/2025")
                self.assertEqual(response.status_code, 200)
                self.assertIn("Champions", response.text)
                self.assertEqual(client.get("/api/history/seasons/2025").status_code, 200)


if __name__ == "__main__":
    unittest.main()
