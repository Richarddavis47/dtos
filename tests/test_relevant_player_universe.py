from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.core.historical_memory import HistoricalStore
from src.core.relevant_players import (
    apply_relevant_player_filter, build_relevant_player_universe,
)
from src.core.valuation.universe import ValuationUniverse


class RelevantPlayerUniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temporary.name) / "history.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def data(count: int = 154) -> dict:
        players = {
            str(index): {"name": f"Player {index}", "position": "WR", "status": "Active", "dtos_value": 1000 - index}
            for index in range(1, count + 1)
        }
        providers = {"FantasyCalc": {str(index): {"value": 10000 - index, "confidence": 80} for index in range(1, count + 1)}}
        return {
            "normalized_players": players,
            "teams": [{"roster_id": 1, "team_name": "One", "owner": "GM", "players": [{"id": "154", "roster_slot": "Starter"}, {"id": "153", "roster_slot": "Taxi"}]}],
            "market_data": {"providers": providers, "provider_status": {}},
            "pick_ledger": [{"season": 2027, "round": 1, "original_roster_id": 1, "current_owner_id": 1}],
        }

    def test_top_150_and_owned_overrides_are_canonical(self) -> None:
        contract = build_relevant_player_universe(self.data(), self.store, "league")
        members = {row["player_id"]: row for row in contract["members"]}
        self.assertEqual(contract["counts"]["additional_free_agents"], 150)
        self.assertIn("current_roster", members["154"]["reason_codes"])
        self.assertIn("current_reserve", members["153"]["reason_codes"])
        self.assertIn("top_free_agent", members["1"]["reason_codes"])
        self.assertNotIn("152", members)
        self.assertEqual(contract["coverage"]["free_agent_boundary"]["rank"], 150)

    def test_every_consumer_filters_from_one_membership_contract(self) -> None:
        data = self.data()
        data["relevant_player_universe"] = build_relevant_player_universe(data, self.store, "league", free_agent_limit=1)
        universe = ValuationUniverse(data, {"last_sync": "2026-01-01T00:00:00+00:00"})
        self.assertEqual({row["asset_id"] for row in universe.assets if row["asset_type"] == "player"}, {"player:1", "player:153", "player:154"})
        self.assertTrue(any(row["asset_type"] == "pick" for row in universe.assets))

    def test_excluded_player_objects_are_released(self) -> None:
        data = self.data()
        contract = build_relevant_player_universe(
            data, self.store, "league", free_agent_limit=1,
        )
        apply_relevant_player_filter(data, contract)
        self.assertEqual(set(data["normalized_players"]), set(contract["member_ids"]))
        self.assertEqual(
            set(data["market_data"]["providers"]["FantasyCalc"]),
            set(contract["member_ids"]),
        )

    def test_membership_and_migration_are_idempotent(self) -> None:
        data = self.data()
        first = build_relevant_player_universe(data, self.store, "league")
        second = build_relevant_player_universe(data, self.store, "league")
        self.assertEqual(first["generation"], second["generation"])
        with self.store.connection() as connection:
            count = connection.execute("SELECT count(*) FROM relevant_player_universe WHERE league_id='league'").fetchone()[0]
            versions = [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
        self.assertEqual(count, len(second["members"]))
        self.assertEqual(versions, list(range(1, 10)))

    def test_duplicate_names_remain_separate_canonical_ids(self) -> None:
        data = self.data(2)
        data["normalized_players"]["1"]["name"] = "Same Name"
        data["normalized_players"]["2"]["name"] = "Same Name"
        contract = build_relevant_player_universe(data, self.store, "league")
        self.assertIn("1", contract["member_ids"])
        self.assertIn("2", contract["member_ids"])
