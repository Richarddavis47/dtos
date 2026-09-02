"""v1.12.3 no-hindsight historical franchise-state regressions."""
from __future__ import annotations

import asyncio
import unittest
from typing import Any

from src.core.historical_franchise_state import (
    BoundaryMode, HistoricalBoundary, HistoricalFranchiseStateService,
    ReconstructionAvailability,
)
from src.core.historical_intelligence import (
    GlobalMarketCheckpoint, HistoricalIntelligenceService,
)
from src.core.history_context.store import CanonicalHistoryStore


class FixtureStore:
    def __init__(self, league: str = "league-a") -> None:
        self.league = league
        self.generation = "history-generation-1"
        self.queries: list[tuple[str, str | None, int | None]] = []
        self.rows = self._rows(league)

    @staticmethod
    def _row(league: str, entity: str, source: str, payload: dict[str, Any], **extra: Any) -> dict[str, Any]:
        return {
            "record_key": f"cache:{league}:2025:{entity}:{source}",
            "entity_type": entity, "league_id": league, "season": 2025,
            "week": extra.get("week"), "franchise_id": extra.get("franchise_id"),
            "player_id": extra.get("player_id"), "source_record_id": source,
            "occurred_at": extra.get("occurred_at"), "provider": "Sleeper",
            "availability": "observed", "confidence": 100,
            "timestamp_provenance": {"normalized_utc": extra.get("occurred_at")},
            "payload": payload,
        }

    @classmethod
    def _rows(cls, league: str) -> list[dict[str, Any]]:
        franchise_1 = f"{league}:franchise:1"
        franchise_2 = f"{league}:franchise:2"
        return [
            cls._row(league, "league_season", league, {
                "settings": {"teams": 2}, "scoring_settings": {"pass_td": 6},
                "roster_positions": ["QB", "RB", "WR", "FLEX"],
            }),
            cls._row(league, "roster_snapshot", "1", {
                "roster_id": 1, "players": ["player-new", "player-stay"],
                "starters": ["player-new"], "reserve": [], "taxi": [],
            }, franchise_id=franchise_1),
            cls._row(league, "roster_snapshot", "2", {
                "roster_id": 2, "players": ["player-old"], "starters": ["player-old"],
                "reserve": [], "taxi": [],
            }, franchise_id=franchise_2),
            cls._row(league, "pick_snapshot", "pick", {
                "season": 2027, "round": 1, "roster_id": 2, "owner_id": 1,
            }),
            cls._row(league, "trade", "trade-1", {
                "type": "trade", "status": "complete", "roster_ids": [1, 2],
                "adds": {"player-new": 1, "player-old": 2},
                "drops": {"player-new": 2, "player-old": 1},
                "draft_picks": [{
                    "season": 2027, "round": 1, "roster_id": 2,
                    "previous_owner_id": 2, "owner_id": 1,
                }],
            }, week=5, occurred_at="2025-10-01T12:00:00Z"),
            cls._row(league, "matchup", "4:1", {
                "matchup_id": 1, "team_points": {"1": 120, "2": 100},
                "winner": 1, "loser": 2,
            }, week=4),
            cls._row(league, "matchup", "6:1", {
                "matchup_id": 1, "team_points": {"1": 90, "2": 110},
                "winner": 2, "loser": 1,
            }, week=6),
            cls._row(league, "player_week", "4:1:player-old", {
                "points": 22, "fantasy_points": 22, "starter": True, "roster_id": 1,
            }, week=4, player_id="player-old", franchise_id=franchise_1),
            cls._row(league, "player_week", "4:1:player-stay", {
                "points": 14, "fantasy_points": 14, "starter": True, "roster_id": 1,
            }, week=4, player_id="player-stay", franchise_id=franchise_1),
        ]

    def records(self, league_id: str, entity_type: str | None, **kwargs: Any):
        self.queries.append((league_id, entity_type, kwargs.get("season")))
        rows = [row for row in self.rows if row["league_id"] == league_id and (entity_type is None or row["entity_type"] == entity_type)]
        return len(rows), rows

    def dataset_version(self, league_id: str) -> str:
        return f"{self.generation}:{league_id}"

    def identity_for_provider_id(self, player_id: str) -> dict[str, Any]:
        return {"provider_player_id": player_id, "metadata": {"position": "QB" if player_id == "player-new" else "WR"}}

    @staticmethod
    def _canonical_pick_id(payload: dict[str, Any], season: int) -> str | None:
        return f"PICK-{payload.get('season') or season}-R{payload['round']}-ORIG{payload['roster_id']}"


class HistoricalFranchiseStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FixtureStore()
        checkpoints = (
            GlobalMarketCheckpoint.create(asset_id="player-old", occurred_at="2025-09-20T00:00:00Z", provider="market", normalized_value=5000, confidence=90, classification="event_relevant", reason_codes=("trade",)),
            GlobalMarketCheckpoint.create(asset_id="player-new", occurred_at="2025-09-20T00:00:00Z", provider="market", normalized_value=6000, confidence=90, classification="event_relevant", reason_codes=("trade",)),
            GlobalMarketCheckpoint.create(asset_id="player-new", occurred_at="2025-10-10T00:00:00Z", provider="market", normalized_value=9000, confidence=95, classification="future", reason_codes=("material",)),
            GlobalMarketCheckpoint.create(asset_id="player-stay", occurred_at="2025-09-20T00:00:00Z", provider="market", normalized_value=2000, confidence=80, classification="event_relevant", reason_codes=("trade",)),
        )
        history = HistoricalIntelligenceService(self.store, checkpoints)
        self.service = HistoricalFranchiseStateService(history)
        self.event = history.transaction_history("league-a")[0]

    def test_pre_and_post_trade_reconstruct_player_and_pick_movement(self) -> None:
        before, after = self.service.around_event("league-a", "1", self.event.event_id)
        self.assertEqual({row.asset_id for row in before.players}, {"player-old", "player-stay"})
        self.assertEqual({row.asset_id for row in after.players}, {"player-new", "player-stay"})
        self.assertNotIn("PICK-2027-R1-ORIG2", {row.asset_id for row in before.draft_picks})
        self.assertIn("PICK-2027-R1-ORIG2", {row.asset_id for row in after.draft_picks})
        difference = self.service.difference(before, after)
        self.assertEqual(difference.players_added, ("player-new",))
        self.assertEqual(difference.players_removed, ("player-old",))

    def test_no_hindsight_market_lookup_uses_only_at_or_before(self) -> None:
        _before, after = self.service.around_event("league-a", "1", self.event.event_id)
        player = next(row for row in after.players if row.asset_id == "player-new")
        self.assertEqual(player.market_value, 6000)
        self.assertEqual(player.market_observed_at, "2025-09-20T00:00:00Z")

    def test_record_excludes_future_matchup(self) -> None:
        state = self.service.reconstruct("league-a", "1", HistoricalBoundary(
            season=2025, week=5, occurred_at="2025-10-01T12:00:00Z",
        ))
        self.assertEqual((state.record.wins, state.record.losses), (1, 0))
        self.assertEqual(state.record.games_observed, 1)
        self.assertEqual(state.lineup.actual_starters, ("player-stay",))
        self.assertEqual(state.lineup.evidence_week, 4)

    def test_unknown_market_is_not_zero_and_total_is_partial(self) -> None:
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(self.store))
        state = service.reconstruct("league-a", "1", HistoricalBoundary(
            season=2025, event_id=self.event.event_id, mode=BoundaryMode.AT_OR_BEFORE,
        ))
        self.assertIsNone(state.roster_market_value)
        self.assertEqual(state.known_market_value, 0)
        self.assertEqual(state.market_coverage_ratio, 0)
        self.assertEqual(state.availability, ReconstructionAvailability.PARTIAL)

    def test_same_state_is_deterministic_and_trace_is_opt_in(self) -> None:
        boundary = HistoricalBoundary(
            season=2025, event_id=self.event.event_id, mode=BoundaryMode.BEFORE,
        )
        first = self.service.reconstruct("league-a", "1", boundary)
        second = self.service.reconstruct("league-a", "1", boundary)
        traced = self.service.reconstruct("league-a", "1", boundary, include_trace=True)
        self.assertEqual(first.state_id, second.state_id)
        self.assertEqual(first.state_id, traced.state_id)
        self.assertEqual(first.trace, ())
        self.assertTrue(traced.trace)

    def test_multi_league_isolation_and_rule_specific_identity(self) -> None:
        league_b = FixtureStore("league-b")
        league_b.rows[0]["payload"]["scoring_settings"] = {"pass_td": 4}
        combined = FixtureStore()
        combined.rows.extend(league_b.rows)
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(combined))
        a_event = service.history.transaction_history("league-a")[0]
        b_event = service.history.transaction_history("league-b")[0]
        a = service.reconstruct("league-a", "1", HistoricalBoundary(2025, event_id=a_event.event_id))
        b = service.reconstruct("league-b", "1", HistoricalBoundary(2025, event_id=b_event.event_id))
        self.assertEqual(a.scoring_settings["pass_td"], 6)
        self.assertEqual(b.scoring_settings["pass_td"], 4)
        self.assertNotEqual(a.state_id, b.state_id)
        self.assertNotEqual(a.franchise_id, b.franchise_id)

    def test_reconstruction_has_zero_provider_calls_and_bounded_query_categories(self) -> None:
        self.service.reconstruct("league-a", "1", HistoricalBoundary(2025, event_id=self.event.event_id))
        self.assertEqual(self.service.metrics()["provider_calls"], 0)
        self.assertLessEqual(self.service.metrics()["source_record_queries"], 6)
        self.assertTrue(all(league == "league-a" for league, _entity, _season in self.store.queries))

    def test_missing_settings_or_roster_is_invalid_not_fabricated(self) -> None:
        self.store.rows = [row for row in self.store.rows if row["entity_type"] not in {"league_season", "roster_snapshot"}]
        state = self.service.reconstruct("league-a", "1", HistoricalBoundary(2025, event_id=self.event.event_id))
        self.assertEqual(state.availability, ReconstructionAvailability.INVALID)
        self.assertEqual(state.league_settings, {})
        self.assertEqual(state.players, ())

    def test_active_season_uses_canonical_current_context_without_provider_call(self) -> None:
        store = CanonicalHistoryStore()
        store.update_current("active-league", {
            "league": {"league_id": "active-league", "season": "2026"},
            "league_settings": {"teams": 1},
            "scoring_settings": {"pass_td": 4},
            "roster_positions": ["QB", "RB", "WR"],
            "teams": [{
                "roster_id": 4, "owner_id": "owner", "team_name": "Active",
                "players": [{
                    "id": "active-player", "position": "QB", "starter": True,
                    "roster_slot": "Starter",
                }],
            }],
            "normalized_players": {
                "active-player": {"name": "Active Player", "position": "QB"},
            },
            "transactions": [], "traded_picks": [],
        })
        service = HistoricalFranchiseStateService(HistoricalIntelligenceService(store))
        state = service.reconstruct(
            "active-league", "4", HistoricalBoundary(2026, week=1),
        )
        self.assertEqual({row.asset_id for row in state.players}, {"active-player"})
        self.assertEqual(state.scoring_settings, {"pass_td": 4})
        self.assertEqual(service.metrics()["provider_calls"], 0)

    def test_async_boundary_keeps_event_loop_responsive(self) -> None:
        async def exercise() -> None:
            boundary = HistoricalBoundary(2025, event_id=self.event.event_id)
            task = asyncio.create_task(
                self.service.reconstruct_async("league-a", "1", boundary),
            )
            await asyncio.sleep(0)
            self.assertFalse(task.cancelled())
            state = await task
            self.assertEqual(state.league_id, "league-a")

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
