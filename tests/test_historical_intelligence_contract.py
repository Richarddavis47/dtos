"""Canonical historical-intelligence isolation, identity, and time contracts."""
from __future__ import annotations

import unittest
from typing import Any

from src.core.historical_intelligence import (
    CheckpointDirection, EvidenceAvailability, EvidenceScope,
    GlobalMarketCheckpoint, HistoricalEventType, HistoricalIntelligenceService,
)


class FixtureHistoryStore:
    def __init__(self, rows: dict[str, list[dict[str, Any]]]) -> None:
        self.rows = rows
        self.generations = {league_id: "generation-1" for league_id in rows}
        self.queries: list[tuple[str, str | None]] = []

    def dataset_version(self, league_id: str) -> str:
        return self.generations[league_id]

    def records(
        self, league_id: str, entity_type: str | None, **_kwargs: Any,
    ) -> tuple[int, list[dict[str, Any]]]:
        self.queries.append((league_id, entity_type))
        selected = [
            row for row in self.rows.get(league_id, [])
            if entity_type is None or row["entity_type"] == entity_type
        ]
        return len(selected), selected


def record(
    league: str, entity: str, source: str, *, season: int = 2025,
    week: int | None = 5, occurred_at: str | None = "2025-10-01T12:00:00Z",
    payload: dict[str, Any] | None = None, player_id: str | None = None,
    franchise_id: str | None = None,
) -> dict[str, Any]:
    return {
        "record_key": f"cache:{league}:{season}:{entity}:{source}",
        "entity_type": entity, "league_id": league, "season": season,
        "week": week, "franchise_id": franchise_id, "player_id": player_id,
        "source_record_id": source, "occurred_at": occurred_at,
        "provider": "Sleeper", "availability": "observed", "confidence": 100,
        "timestamp_provenance": {
            "provider": "Sleeper", "field": "created",
            "normalized_utc": occurred_at,
        },
        "payload": payload or {},
    }


class HistoricalIntelligenceContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shared_player = "player-1"
        self.league_a_trade = record(
            "league-a", "trade", "tx-a",
            payload={
                "type": "trade", "status": "complete", "roster_ids": [1, 2],
                "adds": {self.shared_player: 1},
                "drops": {"player-2": 2},
                "draft_picks": [{"season": 2027, "round": 1, "roster_id": 2}],
            },
        )
        self.league_b_trade = record(
            "league-b", "trade", "tx-b",
            payload={
                "type": "trade", "status": "complete", "roster_ids": [7, 8],
                "adds": {self.shared_player: 7},
            },
        )
        self.checkpoints = (
            GlobalMarketCheckpoint.create(
                asset_id=self.shared_player, occurred_at="2025-09-20T00:00:00Z",
                provider="public-market", normalized_value=700, confidence=90,
                classification="event_relevant", reason_codes=("trade_relevance",),
            ),
            GlobalMarketCheckpoint.create(
                asset_id=self.shared_player, occurred_at="2025-10-02T00:00:00Z",
                provider="public-market", normalized_value=725, confidence=92,
                classification="material_market_move",
                reason_codes=("material_market_move",),
            ),
        )
        self.store = FixtureHistoryStore({
            "league-a": [
                self.league_a_trade,
                record("league-a", "transaction", "waiver-a", payload={
                    "type": "waiver", "adds": {"player-3": 1},
                }),
                record("league-a", "draft_pick", "draft-a", week=None,
                       occurred_at=None, player_id="rookie-1",
                       payload={"pick_no": 1, "round": 1, "roster_id": 1}),
                record("league-a", "matchup", "5:1", payload={
                    "matchup_id": 1, "winner": 1, "loser": 2,
                    "team_points": {"1": 120, "2": 110},
                }),
                record("league-a", "season_standing", "1", week=None,
                       occurred_at=None, franchise_id="league-a:franchise:1",
                       payload={"wins": 10, "losses": 4, "rank": 1}),
                record("league-a", "playoff_result", "final", week=None,
                       occurred_at=None,
                       payload={"champion_roster_id": 1, "runner_up_roster_id": 2}),
            ],
            "league-b": [self.league_b_trade],
        })
        self.service = HistoricalIntelligenceService(self.store, self.checkpoints)

    def test_multi_league_events_are_isolated(self) -> None:
        league_a = self.service.events_for_league("league-a")
        league_b = self.service.events_for_league("league-b")
        self.assertEqual({event.league_id for event in league_a}, {"league-a"})
        self.assertEqual({event.league_id for event in league_b}, {"league-b"})
        self.assertNotIn("tx-a", {event.source_record_id for event in league_b})
        self.assertNotIn("tx-b", {event.source_record_id for event in league_a})

    def test_shared_player_identity_joins_private_events_and_global_checkpoint(self) -> None:
        self.assertEqual(len(self.service.events_for_player("league-a", self.shared_player)), 1)
        self.assertEqual(len(self.service.events_for_player("league-b", self.shared_player)), 1)
        checkpoint = self.service.nearest_market_checkpoint(
            self.shared_player, "2025-10-01T12:00:00Z",
        )
        self.assertEqual(checkpoint.asset_id, self.shared_player)
        self.assertEqual(checkpoint.public_contract()["asset_id"], self.shared_player)

    def test_global_checkpoint_contract_has_no_private_league_fields(self) -> None:
        payload = self.checkpoints[0].public_contract()
        forbidden = {"league_id", "league_name", "manager", "roster_ids", "package"}
        self.assertTrue(forbidden.isdisjoint(payload))
        self.assertEqual(self.checkpoints[0].reason_codes, ("trade_relevance",))

    def test_trade_has_stable_event_time_and_scoped_identities(self) -> None:
        trade = self.service.transaction_history("league-a")[0]
        self.assertEqual(trade.event_type, HistoricalEventType.TRADE)
        self.assertEqual(trade.scope, EvidenceScope.LEAGUE)
        self.assertEqual(trade.source_record_id, "tx-a")
        self.assertEqual(trade.season, 2025)
        self.assertEqual(trade.week, 5)
        self.assertEqual(trade.occurred_at, "2025-10-01T12:00:00Z")
        self.assertEqual(trade.timestamp_provenance["field"], "created")
        self.assertEqual(
            trade.franchise_ids,
            ("league-a:franchise:1", "league-a:franchise:2"),
        )
        self.assertEqual(trade.league_season_context_id, "league-a:season:2025")
        again = HistoricalIntelligenceService(self.store).transaction_history("league-a")[0]
        self.assertEqual(trade.event_id, again.event_id)

    def test_current_and_completed_transactions_share_one_contract_and_deduplicate(self) -> None:
        self.service.replace_current_transactions("league-a", 2025, (
            {**self.league_a_trade["payload"], "transaction_id": "tx-a", "week": 5,
             "created": 1759320000000},
            {"transaction_id": "tx-current", "type": "free_agent", "week": 8,
             "created": 1761000000000, "adds": {"player-4": 1}},
        ))
        events = self.service.transaction_history("league-a")
        self.assertEqual(sum(event.source_record_id == "tx-a" for event in events), 1)
        active = next(event for event in events if event.source_record_id == "tx-current")
        self.assertEqual(active.event_type, HistoricalEventType.FREE_AGENT_ACQUISITION)
        self.assertEqual(active.provider, "Sleeper")

    def test_at_or_before_checkpoint_never_uses_future_evidence(self) -> None:
        selected = self.service.nearest_market_checkpoint(
            self.shared_player, "2025-10-01T12:00:00Z",
            direction=CheckpointDirection.AT_OR_BEFORE,
        )
        future = self.service.nearest_market_checkpoint(
            self.shared_player, "2025-10-01T12:00:00Z",
            direction=CheckpointDirection.AFTER,
        )
        self.assertEqual(selected.occurred_at, "2025-09-20T00:00:00Z")
        self.assertEqual(future.occurred_at, "2025-10-02T00:00:00Z")

    def test_checkpoint_link_is_derived_and_does_not_rewrite_raw_event(self) -> None:
        raw = self.service.transaction_history("league-a")[0]
        linked = self.service.link_checkpoint(
            "league-a", raw.event_id, self.checkpoints[0].checkpoint_id,
        )
        self.assertEqual(raw.market_checkpoint_ids, ())
        self.assertEqual(linked.market_checkpoint_ids, (self.checkpoints[0].checkpoint_id,))
        self.assertEqual(linked.availability, EvidenceAvailability.DERIVED)

    def test_sparse_checkpoint_does_not_require_universe_snapshot(self) -> None:
        service = HistoricalIntelligenceService(self.store, (self.checkpoints[0],))
        self.assertIsNotNone(service.nearest_market_checkpoint(
            self.shared_player, "2025-10-01T12:00:00Z",
        ))
        self.assertIsNone(service.nearest_market_checkpoint(
            "unrelated-player", "2025-10-01T12:00:00Z",
        ))

    def test_bounded_queries_build_only_the_selected_league_once(self) -> None:
        self.service.events_for_player("league-a", self.shared_player)
        first_queries = tuple(self.store.queries)
        self.service.events_for_franchise("league-a", "1")
        self.service.events_for_league(
            "league-a", event_type=HistoricalEventType.TRADE, season=2025,
        )
        self.assertEqual(tuple(self.store.queries), first_queries)
        self.assertTrue(all(league == "league-a" for league, _ in first_queries))
        self.assertEqual(self.service.metrics()["league_builds"], 1)

    def test_raw_history_categories_are_available_through_one_contract(self) -> None:
        types = {event.event_type for event in self.service.events_for_league("league-a")}
        self.assertTrue({
            HistoricalEventType.TRADE,
            HistoricalEventType.WAIVER_ACQUISITION,
            HistoricalEventType.ROOKIE_DRAFT_SELECTION,
            HistoricalEventType.MATCHUP_RESULT,
            HistoricalEventType.SEASON_RESULT,
            HistoricalEventType.CHAMPIONSHIP,
        }.issubset(types))

    def test_missing_provider_time_remains_unknown(self) -> None:
        draft = next(
            event for event in self.service.events_for_league("league-a")
            if event.event_type is HistoricalEventType.ROOKIE_DRAFT_SELECTION
        )
        self.assertIsNone(draft.occurred_at)
        self.assertIsNone(draft.timestamp_provenance["normalized_utc"])

    def test_event_identity_lookup_requires_matching_league(self) -> None:
        event = self.service.transaction_history("league-a")[0]
        self.assertEqual(
            self.service.event_by_identity("league-a", event.event_id), event,
        )
        self.assertIsNone(self.service.event_by_identity("league-b", event.event_id))


if __name__ == "__main__":
    unittest.main()
