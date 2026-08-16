from __future__ import annotations

import json
import inspect
import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.historical_assets import create_historical_assets_router
from services.history import capture_current_state, history_records
from src.core.history_context.guard import (
    LegacyAccessError, LegacyAccessGuard, legacy_access_guard,
)
from src.core.history_context.metadata import MinimalMetadataStore
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.store import CanonicalHistoryStore
from src.core.historical_memory.graph import HistoricalAssetGraph
from src.core.intelligence_memory.chain import SeasonChain, SeasonReference


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
            self.assertEqual(evidence["status"], "retired")

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

    def test_dataset_version_reuses_verified_archive_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            writer = SleeperSeasonCache(root)
            facts = {
                "league": {"league_id": "L", "name": "League"},
                "users": [], "rosters": [], "matchups": {},
                "transactions": {}, "drafts": [], "draft_picks": [],
                "traded_picks": [], "winners_bracket": [], "losers_bracket": [],
            }
            writer.write(writer.normalize("L", 2025, facts))
            cache = SleeperSeasonCache(root)
            store = CanonicalHistoryStore()
            with patch(
                "src.core.history_context.store.sleeper_season_cache", cache,
            ), patch.object(cache, "read", wraps=cache.read) as read:
                first = store.dataset_version("L")
                self.assertEqual(read.call_count, 1)
                self.assertEqual(store.dataset_version("L"), first)
                self.assertEqual(read.call_count, 1)
                changed = {**facts, "transactions": {"1": [{"transaction_id": "t1"}]}}
                writer.write(writer.normalize("L", 2025, changed))
                self.assertNotEqual(store.dataset_version("L"), first)
                self.assertEqual(read.call_count, 2)

    def test_trade_reads_skip_unrelated_season_record_construction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            facts = {
                "league": {"league_id": "L", "name": "League"},
                "users": [], "rosters": [], "matchups": {"1": [{
                    "matchup_id": 1, "roster_id": 1,
                    "players_points": {"p1": 10}, "starters": ["p1"],
                }]},
                "transactions": {"2": [{
                    "transaction_id": "trade-1", "type": "trade",
                    "status_updated": 1_700_000_000_000,
                    "adds": {"p1": 1}, "drops": {"p2": 2},
                }, {
                    "transaction_id": "waiver-1", "type": "waiver",
                    "status_updated": 1_700_000_100_000,
                }]},
                "drafts": [], "draft_picks": [], "traded_picks": [],
                "winners_bracket": [], "losers_bracket": [],
            }
            cache.write(cache.normalize("L", 2025, facts))
            store = CanonicalHistoryStore()
            with patch(
                "src.core.history_context.store.sleeper_season_cache", cache,
            ), patch.object(
                store, "_season_records",
                side_effect=AssertionError("full season construction is prohibited"),
            ):
                count, rows = store.records("L", "trade", limit=100)
            self.assertEqual(count, 1)
            self.assertEqual(rows[0]["source_record_id"], "trade-1")
            self.assertEqual(rows[0]["entity_type"], "trade")

    def test_entity_counts_preserve_filtered_historical_graph_contract(self) -> None:
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
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                seasons, filtered = store.entity_counts_by_season(
                    "L", ("player_week", "draft_pick"),
                )
                _, unfiltered = store.entity_counts_by_season("L")
            self.assertEqual(seasons, [2025])
            self.assertEqual(filtered, {
                "2025": {"player_week": 1, "draft_pick": 0},
            })
            self.assertEqual(unfiltered["2025"]["player_week"], 1)
            self.assertEqual(unfiltered["2025"]["league_season"], 1)

    def test_compact_identity_coverage_preserves_complete_graph_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            facts = {
                "league": {"league_id": "historic", "name": "League"},
                "users": [], "rosters": [],
                "matchups": {"1": [{
                    "matchup_id": 1, "roster_id": 1, "points": 30,
                    "players_points": {"resolved": 20, "unresolved": 10},
                    "starters": ["resolved", "unresolved"],
                }]},
                "transactions": {}, "drafts": [], "draft_picks": [],
                "traded_picks": [], "winners_bracket": [], "losers_bracket": [],
            }
            cache.write(cache.normalize("L", 2025, facts))
            store = CanonicalHistoryStore()
            store.update_current("L", {
                "league": {"league_id": "L"},
                "normalized_players": {
                    "resolved": {"name": "Resolved Player", "position": "QB"},
                },
            })
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                coverage = store.compact_identity_coverage("L")
                empty = store.compact_identity_coverage("missing")
            self.assertEqual(coverage, {
                "resolved_identity_count": 1,
                "unresolved_identity_count": 1,
                "unresolved_player_ids": ["unresolved"],
                "historical_player_ids": ["resolved", "unresolved"],
                "resolved_provider_ids": ["resolved"],
            })
            self.assertEqual(empty, {
                "resolved_identity_count": 0,
                "unresolved_identity_count": 0,
                "unresolved_player_ids": [],
                "historical_player_ids": [],
                "resolved_provider_ids": [],
            })

    def test_compact_event_statistics_match_graph_event_legs_and_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            facts = {
                "league": {"league_id": "historic", "name": "League"},
                "users": [], "rosters": [], "matchups": {},
                "transactions": {"1": [{
                    "transaction_id": "trade-1", "type": "trade", "status": "complete",
                    "adds": {"p1": 1}, "drops": {"p2": 2},
                    "draft_picks": [{"season": 2026, "round": 1, "roster_id": 1}],
                }]},
                "drafts": [{"draft_id": "draft-1", "type": "rookie"}],
                "draft_picks": [{
                    "draft_id": "draft-1", "pick_no": 1, "round": 1,
                    "roster_id": 1, "player_id": "p1",
                }],
                "traded_picks": [], "winners_bracket": [], "losers_bracket": [],
            }
            cache.write(cache.normalize("L", 2025, facts))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                statistics = store.compact_event_statistics("L")
                graph_event_count = len(HistoricalAssetGraph(store, "L", {}).events())
                empty = store.compact_event_statistics("missing")
            self.assertEqual(statistics, {
                "asset_event_count": 5,
                "duplicate_event_ids": 0,
                "orphaned_events": 0,
            })
            self.assertEqual(statistics["asset_event_count"], graph_event_count)
            self.assertEqual(empty, {
                "asset_event_count": 0,
                "duplicate_event_ids": 0,
                "orphaned_events": 0,
            })

    def test_compact_event_statistics_detect_duplicate_event_identity_per_league(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            pick = {"draft_id": "draft", "pick_no": 1, "round": 1,
                    "roster_id": 1, "player_id": "p1"}
            facts = {"league": {"league_id": "A"}, "draft_picks": [pick, dict(pick)]}
            cache.write(cache.normalize("A", 2025, facts))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                duplicated = store.compact_event_statistics("A")
                isolated = store.compact_event_statistics("B")
            self.assertEqual(duplicated["asset_event_count"], 4)
            self.assertEqual(duplicated["duplicate_event_ids"], 2)
            self.assertEqual(isolated["asset_event_count"], 0)

    def test_historical_graph_coverage_uses_all_canonical_adapter_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            facts = {
                "league": {"league_id": "L", "name": "League"},
                "users": [], "rosters": [],
                "matchups": {"1": [{
                    "matchup_id": 1, "roster_id": 1, "points": 20,
                    "players_points": {"p1": 20}, "starters": ["p1"],
                }]},
            }
            cache.write(cache.normalize("L", 2025, facts))
            store = CanonicalHistoryStore()
            store.update_current("L", {
                "league": {"league_id": "L"},
                "normalized_players": {"p1": {"name": "Player", "position": "QB"}},
            })
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                coverage = HistoricalAssetGraph(
                    store, "L", {"players": {"p1": {}}},
                ).coverage()
            self.assertEqual(coverage["status"], "complete")
            self.assertEqual(coverage["seasons"], [2025])
            self.assertEqual(coverage["counts_by_season"]["2025"]["player_week"], 1)
            self.assertEqual(coverage["resolved_identity_count"], 1)
            self.assertEqual(coverage["duplicate_event_ids"], 0)
            self.assertEqual(coverage["orphaned_events"], 0)

    def test_history_coverage_api_uses_canonical_store_without_legacy_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2025, {
                "league": {"league_id": "L", "name": "League"},
                "users": [], "rosters": [], "matchups": {},
            }))
            store = CanonicalHistoryStore()
            app = FastAPI()
            app.include_router(create_historical_assets_router(
                league_id="L", require_data=lambda: {"players": {}},
                page=lambda _title, body: HTMLResponse(body),
            ))
            progress = {
                "canonical_history_progress": {
                    "status": "completed_with_pending", "completed_steps": 1,
                    "total_steps": 2,
                },
            }
            with patch("src.core.history_context.store.sleeper_season_cache", cache), patch(
                "routes.historical_assets.historical_store", store,
            ), patch(
                "routes.historical_assets.history_progress_contracts", return_value=progress,
            ):
                response = TestClient(app).get("/api/history/coverage")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "complete")
            self.assertFalse(response.json()["provider_memory_contract"]["historical_memory_fallback"])

    def test_asset_event_records_translate_canonical_player_and_pick_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2025, {
                "league": {"league_id": "L"},
                "drafts": [{"draft_id": "draft", "type": "rookie"}],
                "draft_picks": [{
                    "draft_id": "draft", "pick_no": 1, "round": 1,
                    "roster_id": 3, "picked_by": 2, "player_id": "old-player",
                }],
                "transactions": {"4": [{
                    "transaction_id": "trade-1", "type": "trade", "status": "complete",
                    "adds": {"old-player": 2}, "drops": {"old-player": 1},
                    "draft_picks": [{
                        "season": 2026, "round": 2, "roster_id": 3,
                        "previous_owner_id": 3, "owner_id": 2,
                    }],
                }]},
            }))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                player = store.asset_event_records("L", "DTOS-P-old-player")
                pick = store.asset_event_records("L", "PICK-2026-R2-ORIG3")
                missing = store.asset_event_records("L", "DTOS-P-missing")
                isolated = store.asset_event_records("OTHER", "DTOS-P-old-player")
                graph = HistoricalAssetGraph(store, "L", {})
                player_events = graph.events(asset_id="DTOS-P-old-player")
                pick_dossier = graph.pick_dossier("PICK-2025-R1-ORIG3")
            self.assertEqual(len(player["draft_pick"]), 1)
            self.assertEqual(len(player["trade"]), 1)
            self.assertEqual(len(pick["trade"]), 1)
            self.assertTrue(player_events)
            self.assertEqual(pick_dossier["selected_player_id"], "DTOS-P-old-player")
            self.assertEqual(len(missing["draft"]), 1)
            self.assertTrue(all(
                not rows for entity, rows in missing.items() if entity != "draft"
            ))
            self.assertTrue(all(not rows for rows in isolated.values()))

    def test_transaction_search_returns_bounded_normalized_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            for season in (2024, 2025):
                cache.write(cache.normalize("L", season, {
                    "league": {"league_id": "L"},
                    "transactions": {"2": [
                        {"transaction_id": f"trade-{season}", "type": "trade",
                         "status": "complete", "adds": {"p1": 1}},
                        {"transaction_id": f"waiver-{season}", "type": "waiver",
                         "status": "complete", "adds": {"p2": 2}, "drops": {"p3": 2}},
                    ]},
                }))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                trades = store.search_transaction_ids("L", "trade-", 10)
                waiver = store.search_transaction_ids("L", "waiver-2024", 1)
                none = store.search_transaction_ids("L", "absent", 10)
                isolated = store.search_transaction_ids("OTHER", "trade-", 10)
                graph_results = HistoricalAssetGraph(store, "L", {}).search("trade-2025")
            self.assertEqual([row["season"] for row in trades], [2025, 2024])
            self.assertEqual(waiver[0]["entity_type"], "transaction")
            self.assertIn("payload", waiver[0])
            self.assertEqual(none, [])
            self.assertEqual(isolated, [])
            self.assertEqual(graph_results[0]["result_type"], "trade")

    def test_distinct_pick_ids_preserve_original_roster_across_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2025, {
                "league": {"league_id": "L"},
                "draft_picks": [
                    {"pick_no": 1, "season": 2025, "round": 1, "roster_id": 1},
                    {"pick_no": 2, "season": 2025, "round": 2, "roster_id": 2},
                ],
                "traded_picks": [{
                    "season": 2026, "round": 1, "roster_id": 3,
                    "previous_owner_id": 3, "owner_id": 9,
                }],
                "transactions": {"1": [{
                    "transaction_id": "trade", "type": "trade", "status": "complete",
                    "draft_picks": [{"season": 2027, "round": 2, "roster_id": 4,
                                     "owner_id": 8}],
                }]},
            }))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                picks = store.distinct_pick_ids("L")
                isolated = store.distinct_pick_ids("OTHER")
            self.assertEqual(picks, [
                "PICK-2025-R1-ORIG1", "PICK-2025-R2-ORIG2",
                "PICK-2026-R1-ORIG3", "PICK-2027-R2-ORIG4",
            ])
            self.assertEqual(isolated, [])

    def test_player_search_includes_current_and_historical_only_provider_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            for season in (2024, 2025):
                cache.write(cache.normalize("L", season, {
                    "league": {"league_id": "L"},
                    "matchups": {"1": [{
                        "matchup_id": 1, "roster_id": 1, "points": 1,
                        "players_points": {"retired-7": 1}, "starters": ["retired-7"],
                    }]},
                }))
            store = CanonicalHistoryStore()
            store.update_current("L", {"league": {"league_id": "L"},
                                       "normalized_players": {"active-1": {
                                           "name": "Active Alpha", "position": "QB",
                                       }}})
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                self.assertEqual(store.search_player_ids("L", "Active Alpha", 10), ["active-1"])
                self.assertEqual(store.search_player_ids("L", "retired", 10), ["retired-7"])
                self.assertEqual(store.search_player_ids("OTHER", "retired", 10), [])

    def test_trade_discovery_filters_orders_and_limits_completed_trades(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2024, {"league": {"league_id": "L"},
                "transactions": {"1": [{"transaction_id": "old", "type": "trade",
                                           "status": "completed"}]}}))
            cache.write(cache.normalize("L", 2025, {"league": {"league_id": "L"},
                "transactions": {"1": [
                    {"transaction_id": "new", "type": "trade", "status": "complete"},
                    {"transaction_id": "failed", "type": "trade", "status": "failed"},
                    {"transaction_id": "pending", "type": "trade", "status": "pending"},
                ]}}))
            store = CanonicalHistoryStore()
            with patch("src.core.history_context.store.sleeper_season_cache", cache):
                all_completed = store.discoverable_trade_records("L", 10)
                newest = store.discoverable_trade_records("L", 1)
                empty = store.discoverable_trade_records("OTHER", 10)
            self.assertEqual([row["source_record_id"] for row in all_completed], ["new", "old"])
            self.assertEqual([row["source_record_id"] for row in newest], ["new"])
            self.assertEqual(empty, [])

    def test_active_canonical_history_adapter_signatures_remain_explicit(self) -> None:
        expected = {
            "records": ("league_id", "entity_type", "season", "week", "franchise_id",
                        "player_id", "limit", "offset"),
            "identities": (), "identity_for_provider_id": ("provider_player_id",),
            "identity_positions": (), "import_active": ("league_id",),
            "quality": ("league_id",), "latest_completed_foundation": ("league_id",),
            "season_player_leaders": ("league_id", "season", "limit"),
            "distinct_player_ids": ("league_id",), "distinct_pick_ids": ("league_id",),
            "search_player_ids": ("league_id", "needle", "limit"),
            "search_transaction_ids": ("league_id", "needle", "limit"),
            "transaction_record": ("league_id", "transaction_id"),
            "discoverable_trade_records": ("league_id", "limit"),
            "asset_event_records": ("league_id", "asset_id"),
            "player_week_totals": ("league_id",),
            "entity_counts_by_season": ("league_id", "entity_types"),
            "compact_event_statistics": ("league_id",),
            "compact_identity_coverage": ("league_id",),
            "dataset_version": ("league_id",), "dataset_version_metrics": (),
            "semantic_generations": ("league_id",), "identity_generations": (),
            "relevant_player_reasons": ("league_id",),
            "persist_relevant_player_universe": (
                "league_id", "rows", "generation", "updated_at",
            ),
            "update_current": ("league_id", "data"),
        }
        for method_name, parameter_names in expected.items():
            with self.subTest(method=method_name):
                method = getattr(CanonicalHistoryStore, method_name)
                actual = tuple(inspect.signature(method).parameters)[1:]
                self.assertEqual(actual, parameter_names)
        self.assertEqual(
            inspect.signature(CanonicalHistoryStore.discoverable_trade_records)
            .parameters["limit"].default,
            3,
        )

    def test_canonical_adapter_product_paths_do_not_touch_legacy_guard(self) -> None:
        legacy_access_guard.reset()
        store = CanonicalHistoryStore()
        store.entity_counts_by_season("missing")
        store.compact_identity_coverage("missing")
        store.compact_event_statistics("missing")
        store.asset_event_records("missing", "DTOS-P-missing")
        store.search_transaction_ids("missing", "trade", 3)
        store.distinct_pick_ids("missing")
        store.search_player_ids("missing", "player", 3)
        store.discoverable_trade_records("missing")
        self.assertEqual(legacy_access_guard.health()["legacy_read_attempts"], 0)
        self.assertEqual(legacy_access_guard.health()["legacy_write_attempts"], 0)

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

    def test_metadata_store_persists_complete_season_chain_without_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = MinimalMetadataStore(Path(directory) / "metadata.sqlite3")
            manifest = {
                "root_league_id": "L", "year_one": 2021,
                "seasons": [
                    {"season": season, "league_id": f"L{season}",
                     "cache_status": "cached" if season < 2026 else "pending_current"}
                    for season in range(2021, 2027)
                ],
            }
            store.record_season_chain("L", manifest)
            self.assertEqual(store.season_chain("L"), manifest)
            raw = store.path.read_bytes()
            self.assertNotIn(b"matchups", raw)
            self.assertNotIn(b"transactions", raw)

    def test_canonical_progress_uses_discovered_chain_not_partial_cache(self) -> None:
        from services import history

        manifest = {
            "year_one": 2021,
            "seasons": [
                {"season": season, "cache_status": (
                    "pending_current" if season == 2026
                    else "cached" if season == 2025
                    else "available_not_cached"
                )}
                for season in range(2021, 2027)
            ],
        }
        with patch.object(
            history.canonical_history_store, "season_chain", return_value=manifest,
        ), patch.object(
            history.canonical_history_store, "_cache_index", return_value={2025: "sum"},
        ):
            progress = history.canonical_history_progress("L", current_year=2026)
        self.assertEqual(progress["configured_seasons"], list(range(2021, 2027)))
        self.assertEqual(progress["completed_steps"], 1)
        self.assertEqual(progress["total_steps"], 6)
        self.assertEqual(progress["missing_seasons"], [2021, 2022, 2023, 2024])
        self.assertEqual(progress["pending_seasons"], [2026])
        self.assertEqual(progress["status"], "incomplete")

    def test_no_manifest_progress_spans_earliest_cache_through_current_year(self) -> None:
        from services import history

        cached = {season: f"sum-{season}" for season in range(2021, 2026)}
        with patch.object(
            history.canonical_history_store, "season_chain", return_value=None,
        ), patch.object(
            history.canonical_history_store, "_cache_index", return_value=cached,
        ):
            progress = history.canonical_history_progress("L", current_year=2026)
        self.assertEqual(progress["configured_seasons"], list(range(2021, 2027)))
        self.assertEqual(progress["completed_seasons"], list(range(2021, 2026)))
        self.assertEqual(progress["pending_seasons"], [2026])
        self.assertEqual(progress["completed_steps"], 5)
        self.assertEqual(progress["total_steps"], 6)
        self.assertEqual(progress["status"], "completed_with_pending")

    def test_no_manifest_gapped_cache_preserves_calendar_range(self) -> None:
        from services import history

        with patch.object(
            history.canonical_history_store, "season_chain", return_value=None,
        ), patch.object(
            history.canonical_history_store, "_cache_index",
            return_value={2021: "a", 2023: "b", 2025: "c"},
        ):
            progress = history.canonical_history_progress("L", current_year=2026)
        self.assertEqual(progress["configured_seasons"], list(range(2021, 2027)))
        self.assertEqual(progress["completed_seasons"], [2021, 2023, 2025])
        self.assertEqual(progress["missing_seasons"], [2022, 2024])
        self.assertEqual(progress["pending_seasons"], [2026])

    def test_manifest_universe_precedes_older_cached_rows(self) -> None:
        from services import history

        manifest = {"seasons": [
            {"season": season, "cache_status": (
                "pending_current" if season == 2026 else "cached"
            )}
            for season in range(2023, 2027)
        ]}
        cached = {season: f"sum-{season}" for season in range(2021, 2026)}
        with patch.object(
            history.canonical_history_store, "season_chain", return_value=manifest,
        ), patch.object(
            history.canonical_history_store, "_cache_index", return_value=cached,
        ):
            progress = history.canonical_history_progress("L", current_year=2026)
        self.assertEqual(progress["configured_seasons"], [2023, 2024, 2025, 2026])
        self.assertEqual(progress["completed_seasons"], [2023, 2024, 2025])
        self.assertEqual(progress["pending_seasons"], [2026])
        self.assertEqual(progress["status"], "completed_with_pending")

    def test_empty_cache_without_manifest_uses_bounded_current_season(self) -> None:
        from services import history

        with patch.object(
            history.canonical_history_store, "season_chain", return_value=None,
        ), patch.object(
            history.canonical_history_store, "_cache_index", return_value={},
        ):
            progress = history.canonical_history_progress("L", current_year=2026)
        self.assertEqual(progress["configured_seasons"], [2026])
        self.assertEqual(progress["pending_seasons"], [2026])
        self.assertEqual(progress["completed_steps"], 0)
        self.assertEqual(progress["total_steps"], 1)

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

    def test_chain_health_distinguishes_cached_missing_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory))
            cache.write(cache.normalize("L", 2025, {
                "league": {"league_id": "L", "season": "2025"},
            }))
            manifest = {"seasons": [
                {"season": 2024, "cache_status": "available_not_cached"},
                {"season": 2025, "cache_status": "cached"},
                {"season": 2026, "cache_status": "pending_current"},
            ]}
            health = cache.health("L", manifest)["league"]
            self.assertEqual(health["cached_seasons"], [2025])
            self.assertEqual(health["available_not_cached"], [2024])
            self.assertEqual(health["pending_current_seasons"], [2026])
            self.assertGreater(health["storage_estimate"]["projected_complete_bytes"], 0)

    def test_backfill_records_full_chain_and_continues_after_one_season_failure(self) -> None:
        from services import history

        class Source:
            async def discover(self, league_id: str) -> SeasonChain:
                rows = tuple(
                    SeasonReference(
                        f"L{season}", season,
                        f"L{season - 1}" if season > 2021 else None,
                        "available", "league_object",
                    )
                    for season in range(2026, 2020, -1)
                )
                return SeasonChain(league_id, rows, True, "provider_chain_terminated")

            async def completed_season_facts(
                self, league_id: str, season: int,
            ) -> dict[str, object]:
                if season == 2024:
                    raise OSError("fixture provider failure")
                return {"league": {"league_id": league_id, "season": str(season)}}

        async def run() -> dict[str, object]:
            history._BACKFILL_TASK = None
            return await history.start_background_backfill(None)

        with tempfile.TemporaryDirectory() as directory:
            cache = SleeperSeasonCache(Path(directory) / "cache")
            metadata = MinimalMetadataStore(Path(directory) / "metadata.sqlite3")
            with patch.object(history, "LEAGUE_ID", "L"), patch.object(
                history, "sleeper_season_cache", cache,
            ), patch.object(
                history, "minimal_metadata_store", metadata,
            ), patch(
                "src.core.intelligence_memory.sleeper_source.SleeperHistoricalSource",
                Source,
            ):
                result = asyncio.run(run())
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["unavailable_seasons"], [2024])
            self.assertEqual(cache.available_seasons("L"), (2021, 2022, 2023, 2025))
            manifest = metadata.season_chain("L")
            self.assertEqual(
                [row["season"] for row in manifest["seasons"]],
                [2026, 2025, 2024, 2023, 2022, 2021],
            )
            states = {row["season"]: row["cache_status"] for row in manifest["seasons"]}
            self.assertEqual(states[2026], "pending_current")
            self.assertEqual(states[2024], "unavailable")
            self.assertEqual(states[2021], "cached")

    def test_historical_cache_is_a_supported_market_blocking_phase(self) -> None:
        from src.platform.lifecycle import LifecycleCoordinator

        coordinator = LifecycleCoordinator()
        epoch = coordinator.begin_startup("fixture")
        coordinator.complete_startup(epoch, "fixture ready")
        with coordinator.phase("historical_cache"):
            self.assertFalse(coordinator.market_build_allowed())
        self.assertTrue(coordinator.market_build_allowed())


if __name__ == "__main__":
    unittest.main()
