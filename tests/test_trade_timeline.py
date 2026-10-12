"""Canonical publisher/reader/HTTP boundaries for historical trade timelines."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from src.core.history_context import store as history_module
from src.core.history_context.store import CanonicalHistoryStore
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.historical_memory.read_model import HistoricalReadModelCache
from src.core.intelligence_memory.store import IntelligenceCheckpointStore
from src.core.intelligence_memory.service import IntelligenceMemoryService
from src.core.intelligence_memory.pipeline import CheckpointPipeline
from src.core.intelligence_memory.models import (
    PickLineage,
    CheckpointTrigger,
    ProvenanceType,
    EvidenceCompleteness,
)
from src.core.intelligence_memory.market_memory import market_context_id
from tests.test_market_observation_producer_identity import prepared

SOURCE = Path(__file__).parent / "fixtures" / "trade_timeline_sources.json"
DAY = "1313066632158924800"
ARK = "1319750579458686976"


class TradeTimelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = SleeperSeasonCache(Path(self.temp.name) / "season")
        self.patch = patch.object(history_module, "sleeper_season_cache", self.cache)
        self.patch.start()
        self.memory = IntelligenceCheckpointStore(
            Path(self.temp.name) / "memory.sqlite3"
        )
        self.service = IntelligenceMemoryService(self.memory)
        self.pipeline = CheckpointPipeline(self.service)
        self.store = CanonicalHistoryStore()
        self.sources = json.loads(SOURCE.read_text())["leagues"]
        self.data = {}

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def load(self, index=0):
        facts = copy.deepcopy(self.sources[index])
        league = facts["league"]["league_id"]
        self.cache.write(self.cache.normalize(league, 2026, facts))
        players = {
            p["player_id"]: {
                "full_name": p["metadata"]["first_name"]
                + " "
                + p["metadata"]["last_name"],
                "position": p["metadata"]["position"],
            }
            for p in facts["draft_picks"]
        }
        users = {r["user_id"]: r for r in facts["users"]}
        data = {
            "league": facts["league"],
            "players": players,
            "normalized_players": {
                k: {"name": v["full_name"], "position": v["position"]}
                for k, v in players.items()
            },
            "drafts": facts["drafts"],
            "draft_picks": facts["draft_picks"],
            "teams": [
                {
                    "roster_id": r["roster_id"],
                    "owner_id": r["owner_id"],
                    "owner": users.get(r["owner_id"], {}).get("display_name"),
                    "team_name": (
                        users.get(r["owner_id"], {}).get("metadata") or {}
                    ).get("team_name"),
                    "players": [{"id": p} for p in r.get("players") or []],
                }
                for r in facts["rosters"]
            ],
        }
        self.store.update_current(league, data)
        self.pipeline.ingest_drafts(data, facts["draft_picks"])
        self.data[league] = data
        return HistoricalAssetGraph(self.store, league, data, self.memory)

    def capture(
        self,
        asset,
        quote,
        event="2026-03-01T00:00:00Z",
        *,
        value=500,
        kind="player",
        semantics=True,
        known=None,
    ):
        data, _ = prepared()
        evidence = CheckpointPipeline._market_observations(data, "player:1")
        evidence = tuple(
            replace(
                r,
                observed_at=quote,
                raw_value=value,
                normalized_value=value,
                metadata={
                    **r.metadata,
                    **({"source_knowledge_at": known} if known else {}),
                }
                if semantics
                else {},
            )
            for r in evidence
        )
        return self.service.capture(
            trigger=CheckpointTrigger.TRADE_EXECUTION,
            asset_id=asset,
            asset_type=kind,
            timestamp=event,
            season=2026,
            provenance=ProvenanceType.LIVE_CAPTURED,
            league_id=DAY,
            event_id=asset,
            market_value=value,
            confidence=90,
            completeness=EvidenceCompleteness.COMPLETE,
            observations=evidence,
        )

    def test_love_original4_selecting5_exact_writer_and_graph(self):
        graph = self.load()
        pick = graph.pick_dossier("PICK-2026-R1-ORIG4")
        self.assertEqual(pick["selected_player_id"], "DTOS-P-13287")
        self.assertEqual(pick["original_franchise_id"], DAY + ":franchise:4")
        event = next(e for e in pick["events"] if e["event_type"] == "pick_exercise")
        self.assertEqual(event["to_franchise_id"], DAY + ":franchise:5")
        stored = self.memory.exact_lineage(
            league_id=DAY, draft_id="1313066632167325696", selection=1
        )
        self.assertEqual(
            (stored.original_roster_id, stored.selecting_roster_id), ("4", "5")
        )

    def test_multiple_same_round_all_exact_selections_distinct(self):
        graph = self.load()
        events = graph.events()
        picks = [e for e in events if e["event_type"] == "pick_exercise"]
        self.assertEqual(len(picks), 40)
        self.assertEqual(len({e["asset_id"] for e in picks}), 40)
        selections = [e for e in events if e["asset_type"] == "selection"]
        self.assertEqual(len({e["asset_id"] for e in selections}), 40)

    def test_auction_does_not_convert_future_franchise_picks(self):
        graph = self.load(1)
        events = graph.events()
        selections = [e for e in events if e["asset_type"] == "selection"]
        self.assertEqual(len(selections), 260)
        self.assertEqual(len({e["asset_id"] for e in selections}), 260)
        self.assertFalse(any(e["event_type"] == "pick_exercise" for e in events))

    def test_boston_pick_conversion_then_observed_trade(self):
        graph = self.load()
        model = graph.trade_timeline("1333655835015942144")
        branch = next(
            b for b in model["branches"] if b["asset_id"] == "PICK-2026-R2-ORIG7"
        )
        conversion = next(e for e in branch["events"] if e.get("selected_player_id"))
        self.assertEqual(conversion["selected_player_id"], "DTOS-P-13346")
        self.assertTrue(
            any(
                e["source_record_id"] == "1414718106177122304" for e in branch["events"]
            )
        )
        self.assertEqual(branch["state"], "Converted into confirmed drafted player")
        self.assertNotIn("descendant_value", model)

    def test_actual_source_league_and_foreign_roster_ids(self):
        first = self.load()
        second = self.load(1)
        self.assertTrue(all(e["source_league_id"] == DAY for e in first.events()))
        self.assertTrue(all(e["source_league_id"] == ARK for e in second.events()))
        self.assertTrue(
            all(
                str(e.get("to_franchise_id") or "").startswith(ARK + ":")
                for e in second.events()
                if e.get("to_franchise_id")
            )
        )
        self.assertIsNone(self.store.transaction_record(ARK, "1333655835015942144"))

    def test_future_and_later_knowledge_quotes_are_rejected_by_real_producer(self):
        self.capture("player:late", "2026-03-02T00:00:00Z")
        self.capture(
            "player:knowledge", "2026-02-01T00:00:00Z", known="2026-03-02T00:00:00Z"
        )
        for asset in ["player:late", "player:knowledge"]:
            self.assertIsNone(
                self.memory.observation_at_or_before(
                    asset_id=asset,
                    market_context_id=market_context_id(
                        asset_type="player", scoring_profile_id=None
                    ),
                    event_at="2026-03-01T00:00:00Z",
                )
            )

    def test_older_quote_keeps_clock_and_not_exact(self):
        self.capture("player:1", "2026-02-01T00:00:00Z")
        graph = HistoricalAssetGraph(self.store, DAY, intelligence_store=self.memory)
        context = graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [{"asset_id": "DTOS-P-1", "to_franchise_id": DAY + ":franchise:1"}],
        )
        self.assertEqual(context["assets"][0]["observed_at"], "2026-02-01T00:00:00Z")
        self.assertEqual(context["assets"][0]["match_state"], "DATED_ESTIMATE")
        self.assertLess(context["confidence"], 65)
        self.assertEqual(context["process_state"], "not_gradable")

    def test_price_units_opaque_legacy_fail_closed(self):
        self.capture("player:1", "2026-03-01T00:00:00Z")
        self.capture("player:2", "2026-03-01T00:00:00Z", semantics=False, value=5000)
        graph = HistoricalAssetGraph(self.store, DAY, intelligence_store=self.memory)
        result = graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [
                {"asset_id": "DTOS-P-" + p, "to_franchise_id": DAY + ":franchise:" + p}
                for p in ["1", "2"]
            ],
        )
        self.assertEqual(result["side_totals"], {})
        self.assertEqual(result["process_state"], "not_gradable")

    def test_compatible_exact_zero_and_future_pick_context_alias(self):
        self.capture("player:1", "2026-03-01T00:00:00Z", value=0)
        self.capture(
            "pick:2027:1:4", "2026-03-01T00:00:00Z", value=0, kind="future_pick"
        )
        graph = HistoricalAssetGraph(self.store, DAY, intelligence_store=self.memory)
        result = graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [
                {"asset_id": "DTOS-P-1", "to_franchise_id": DAY + ":franchise:1"},
                {
                    "asset_id": "PICK-2027-R1-ORIG4",
                    "to_franchise_id": DAY + ":franchise:2",
                },
            ],
        )
        self.assertEqual(
            result["side_totals"], {DAY + ":franchise:1": 0, DAY + ":franchise:2": 0}
        )
        self.assertEqual(result["fairness_state"], "comparable_exact_evidence")

    def test_missing_pick_not_substituted_by_player_or_current_value(self):
        self.capture("player:1", "2026-03-01T00:00:00Z")
        graph = HistoricalAssetGraph(self.store, DAY, intelligence_store=self.memory)
        result = graph._trade_time_intelligence(
            {"occurred_at": "2026-03-01T00:00:00Z"},
            [
                {
                    "asset_id": "PICK-2027-R1-ORIG4",
                    "to_franchise_id": DAY + ":franchise:2",
                }
            ],
        )
        self.assertEqual(result["valued_assets"], 0)
        self.assertEqual(result["side_totals"], {})

    def test_partial_started_scoring_zero_and_duplicates(self):
        graph = self.load()
        facts = copy.deepcopy(self.sources[0])
        facts["matchups"] = {
            str(w): [
                {
                    "roster_id": 1,
                    "players": ["missing", "zero"],
                    "starters": ["missing", "zero"],
                    "players_points": {"zero": 0},
                    "matchup_id": 1,
                }
            ]
            for w in range(1, 19)
        }
        # Identical observation repeats do not add points twice.
        facts["matchups"]["1"] *= 2
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        graph = HistoricalAssetGraph(self.store, DAY, self.data[DAY], self.memory)
        with patch.object(self.store, '_record_page', wraps=self.store._record_page) as scans:
            missing = graph.player_season_summaries("missing")[0]
            zero = graph.player_season_summaries("zero")[0]
        self.assertEqual(sum(len(c.args) > 1 and c.args[1] == 'player_week'
                             for c in scans.call_args_list), 1)
        self.assertIsNone(missing["starter_points"])
        self.assertEqual(missing["completeness_percentage"], 0)
        self.assertEqual(zero["starter_points"], 0)
        self.assertEqual(zero["games_observed"], 18)
        self.assertIsNone(zero["end_of_season_franchise_id"])
        self.assertEqual(zero["last_scored_franchise_id"], DAY + ":franchise:1")

    def test_null_chronology_http_and_coverage_preserve_events(self):
        self.load()
        facts = copy.deepcopy(self.sources[0])
        facts["transactions"]["1"][0]["created"] = None
        facts["transactions"]["1"][0]["status_updated"] = None
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        app = self.app()
        with (
            patch("routes.historical_assets.historical_store", self.store),
            TestClient(app) as client,
        ):
            for url in [
                "/api/history/transactions",
                "/api/history/trades/coverage",
                "/api/history/players/13346",
                "/trades/history/1333655835015942144",
            ]:
                response = client.get(url)
                self.assertEqual(response.status_code, 200, (url, response.text[:200]))
            self.assertIn(
                "Original trade time unavailable",
                client.get("/trades/history/1333655835015942144").text,
            )

    def test_drop_closes_interval_without_claiming_final_owner(self):
        self.load()
        facts = copy.deepcopy(self.sources[0])
        facts["transactions"]["6"] = [
            {
                "transaction_id": "drop",
                "type": "free_agent",
                "status": "complete",
                "created": 1800000000000,
                "adds": {},
                "drops": {"13346": 1},
            }
        ]
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        graph = HistoricalAssetGraph(self.store, DAY, {}, self.memory)
        intervals = graph.ownership_intervals("DTOS-P-13346")
        self.assertFalse(any(i["season_end_owner"] for i in intervals))
        self.assertTrue(any(i["disposed_at"] for i in intervals))

    def test_unknown_original_not_replaced_by_current_owner(self):
        from src.core.historical_intelligence.service import _pick_identity

        self.assertIsNone(
            _pick_identity({"season": 2027, "round": 1, "owner_id": 4}, 2026)
        )

    def test_legacy_untouched_and_repeat_reads_no_growth(self):
        self.memory.put_lineage(
            PickLineage(
                "legacy",
                "pick:2026:1:4",
                2026,
                1,
                "4",
                selected_player_id="player:unknown",
            )
        )
        graph = self.load()
        with self.memory._connect() as db:
            before = [tuple(r) for r in db.execute("select * from pick_lineage")]
        graph.trade_timeline("1333655835015942144")
        sizes = {
            str(p): p.stat().st_size
            for p in Path(self.temp.name).rglob("*")
            if p.is_file()
        }
        for _ in range(20):
            graph.trade_timeline("1333655835015942144")
        self.assertEqual(
            sizes,
            {
                str(p): p.stat().st_size
                for p in Path(self.temp.name).rglob("*")
                if p.is_file()
            },
        )
        with self.memory._connect() as db:
            self.assertEqual(
                before, [tuple(r) for r in db.execute("select * from pick_lineage")]
            )

    def test_current_transaction_only_generation_invalidates(self):
        self.load()
        model = HistoricalReadModelCache()
        old = model.get(self.store, DAY, self.data[DAY])
        old.events()
        new = copy.deepcopy(self.data[DAY])
        new["transactions"] = [
            {
                "transaction_id": "NEW",
                "type": "trade",
                "status": "complete",
                "created": 1800000000000,
                "adds": {"13346": 2},
                "drops": {"13346": 1},
            }
        ]
        self.store.update_current(DAY, new)
        self.assertIsNot(old, model.get(self.store, DAY, new))

    def test_bounded_index_reuse_for_expansion(self):
        graph = self.load()
        with patch.object(self.store, "records", wraps=self.store.records) as queries:
            graph.trade_timeline("1333655835015942144")
            initial = queries.call_count
            for _ in range(20):
                graph.trade_timeline("1333655835015942144")
            self.assertEqual(initial, queries.call_count)
            self.assertLess(initial, 15)

    def test_http_readable_exact_assets_and_dossier_return(self):
        self.load()
        with (
            patch("routes.historical_assets.historical_store", self.store),
            TestClient(self.app()) as client,
        ):
            response = client.get("/trades/history/1333655835015942144")
            self.assertEqual(response.status_code, 200)
            self.assertIn("Denzel Boston", response.text)
            pick = client.get(
                "/picks/PICK-2026-R2-ORIG7?from_trade=1333655835015942144"
            )
            self.assertIn("Back to original trade timeline", pick.text)
            self.assertNotIn("Not exercised", pick.text)
            data = client.get("/api/trades/history/1333655835015942144").json()
            self.assertEqual(data["timeline"]["league_id"], DAY)
            self.assertLessEqual(data["timeline"]["events_rendered"], 100)

    def test_equal_clock_and_missing_transition_stop_continuation(self):
        self.load()
        facts = copy.deepcopy(self.sources[0])
        original = copy.deepcopy(facts["transactions"]["1"][0])
        first = {
            "transaction_id": "amb1",
            "type": "trade",
            "status": "complete",
            "created": 1773000000000,
            "roster_ids": [4, 5],
            "draft_picks": [
                {
                    "season": "2026",
                    "round": 2,
                    "roster_id": 7,
                    "previous_owner_id": 4,
                    "owner_id": 5,
                }
            ],
        }
        second = {**first, "transaction_id": "amb2"}
        facts["transactions"]["2"] = [first, second]
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        graph = HistoricalAssetGraph(self.store, DAY, self.data[DAY], self.memory)
        model = graph.trade_timeline(original["transaction_id"])
        branch = next(
            b for b in model["branches"] if b["asset_id"] == "PICK-2026-R2-ORIG7"
        )
        self.assertTrue(
            any("Equal event clocks" in reason for reason in branch["limitations"])
        )
        self.assertFalse(any(e["source_record_id"] == "amb2" for e in branch["events"]))
        first["draft_picks"][0]["previous_owner_id"] = 9
        facts["transactions"]["2"] = [first]
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        model = HistoricalAssetGraph(
            self.store, DAY, self.data[DAY], self.memory
        ).trade_timeline(original["transaction_id"])
        branch = next(
            b for b in model["branches"] if b["asset_id"] == "PICK-2026-R2-ORIG7"
        )
        self.assertTrue(
            any(
                "Missing ownership transition" in reason
                for reason in branch["limitations"]
            )
        )

    def test_shared_package_event_dedup_and_manager_scope(self):
        graph = self.load()
        model = graph.trade_timeline("1333655835015942144")
        ids = [
            (event["asset_id"], event["source_record_id"], event["type"])
            for b in model["branches"]
            for event in b["events"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(
            all("Season-observed" in p["manager_scope"] for p in model["participants"])
        )
        self.assertFalse(any("value_total" in b for b in model["branches"]))
        self.assertEqual(model["events_rendered"], len(ids))

    def test_equivalent_utc_clocks_do_not_reject_valid_evidence(self):
        self.capture(
            "player:equal", "2026-03-01T00:00:00Z", event="2026-03-01T00:00:00+00:00"
        )
        for boundary in ("2026-03-01T00:00:00Z", "2026-03-01T00:00:00+00:00"):
            observation = self.memory.observation_at_or_before(
                asset_id="player:equal",
                market_context_id=market_context_id(
                    asset_type="player", scoring_profile_id=None
                ),
                event_at=boundary,
            )
            self.assertIsNotNone(observation)
            self.assertEqual(observation.observed_at, "2026-03-01T00:00:00Z")

    def test_prior_integrity2_grades_and_snapshots_are_preserved(self):
        from src.core.fois.repository import FOISRepository
        from src.core.fois.engine import FOISEngine
        from src.core.fois.facts import FOISFacts

        repo = FOISRepository(Path(self.temp.name) / "fois.sqlite3")
        score = FOISEngine().evaluate(FOISFacts("a", "a:franchise:1", "owner", ()))
        prior = replace(score, evidence_integrity_version="fois-evidence-integrity-2")
        repo.save(prior, "original-evidence")
        with repo._connection() as db:
            before = tuple(db.execute("SELECT * FROM fois_scores_v2").fetchone())
            snapshots = [
                tuple(row) for row in db.execute("SELECT * FROM fois_snapshot_history")
            ]
        self.assertFalse(
            repo.save(replace(score, overall_score=99), "new-clock-contract")
        )
        with repo._connection() as db:
            self.assertEqual(
                before, tuple(db.execute("SELECT * FROM fois_scores_v2").fetchone())
            )
            self.assertEqual(
                snapshots,
                [
                    tuple(row)
                    for row in db.execute("SELECT * FROM fois_snapshot_history")
                ],
            )
        self.assertIn(
            "NOT_REVALIDATED",
            " ".join(repo.league("a", score.model_version)[0].warnings),
        )

    def test_event_index_excludes_irrelevant_scoring_universe(self):
        self.load()
        facts = copy.deepcopy(self.sources[0])
        facts["matchups"] = {
            "1": [
                {
                    "roster_id": 1,
                    "starters": [],
                    "players_points": {str(n): 1 for n in range(100_100)},
                }
            ]
        }
        self.cache.write(self.cache.normalize(DAY, 2026, facts))
        graph = HistoricalAssetGraph(self.store, DAY, self.data[DAY], self.memory)
        model = graph.trade_timeline("1333655835015942144")
        self.assertIsNotNone(model)
        families, _ = self.store._event_index(DAY)
        self.assertNotIn("player_week", families)
        player = graph.player_dossier('999')
        self.assertEqual(player['season_summaries'][0]['fantasy_points'], 1)
        self.assertIsNone(player['season_summaries'][0]['overall_rank'])
        self.assertIn('comparison ranks unavailable', ' '.join(player['limitations']))

    def test_sparse_quote_publication_invalidates_cached_history(self):
        self.load()
        cache = HistoricalReadModelCache()
        with patch(
            "src.core.intelligence_memory.intelligence_checkpoint_store", self.memory
        ):
            old = cache.get(self.store, DAY, self.data[DAY])
            self.assertIs(old, cache.get(self.store, DAY, self.data[DAY]))
            self.capture("player:newquote", "2026-03-01T00:00:00Z")
            self.assertIsNot(old, cache.get(self.store, DAY, self.data[DAY]))
            current = cache.get(self.store, DAY, self.data[DAY])
            self.assertIs(current, cache.get(self.store, DAY, self.data[DAY]))

    def app(self):
        app = FastAPI()
        app.include_router(
            create_historical_assets_router(
                league_id=DAY,
                require_data=lambda: self.data[DAY],
                page=lambda title, body: HTMLResponse("<h1>" + title + "</h1>" + body),
            )
        )
        return app
