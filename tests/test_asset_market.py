"""Asset Market canonical contracts, ranking, search, and read isolation."""
from __future__ import annotations

import copy
import gc
import os
import subprocess
import tempfile
import threading
import time
import unittest
import weakref
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.market import create_market_router
from src.core.asset_market import (
    AssetMarketCache, MarketWarmingError, asset_market_cache,
)
from src.core.asset_market.read_model import (
    MarketMemoryBudgetError, build_read_model, enforce_memory_budget,
    memory_admission,
)
from src.core.asset_market.engine import SemanticWorkerError
from src.core.historical_memory.store import HistoricalStore
from src.core.historical_memory import historical_graph


def _brain_asset(
    asset_id: str, market: int | None, contender: int | None,
    rebuilder: int | None,
) -> dict:
    return {
        "asset_id": asset_id, "scores": {"coverage": 75, "confidence": 80, "agreement": 70},
        "valuation_layers": {
            "market_value": {"value": market},
            "contender_value": {"value": contender},
            "rebuilder_value": {"value": rebuilder},
        },
        "categories": [{"name": "Market", "available": True}],
        "evidence_sources": [{"provider_id": "fixture", "category": "Market"}],
        "missing_evidence": ["Projection"], "explanation": "Fixture evidence.",
    }


class AssetMarketTests(unittest.TestCase):
    def setUp(self) -> None:
        asset_market_cache.wait_for_background()
        asset_market_cache.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.store = HistoricalStore(Path(self.temp.name) / "history.sqlite3")
        self.league_id = "league-1"
        self.data = {
            "league": {"league_id": self.league_id},
            "players": {
                "10213": {"full_name": "Josh Allen", "position": "QB", "team": "BUF", "age": 30, "status": "Active", "years_exp": 8, "dtos_value": 90},
                "2": {"full_name": "Rookie Tight End", "position": "TE", "team": "NYJ", "age": 21, "status": "Active", "years_exp": 0, "dtos_value": 50},
                "3": {"full_name": "Retired Runner", "position": "RB", "age": 38, "status": "Retired", "years_exp": 12},
            },
            "teams": [{
                "roster_id": 1, "team_name": "Puka Cola Quantum", "owner": "Richard",
                "players": [{"id": "10213", "roster_slot": "starter"}],
            }],
            "pick_ledger": [{
                "season": 2028, "round": 1, "original_roster_id": 1,
                "original_team": "Puka Cola Quantum", "current_owner_id": 1,
                "current_owner": "Puka Cola Quantum",
            }],
            "market_data": {"providers": {}, "provider_status": {}},
            "valuation_intelligence": {
                "schema_version": "1.0", "generated_at": "2026-08-06T00:00:00+00:00",
                "availability": "available",
                "assets": {
                    "player:10213": _brain_asset("player:10213", 9200, 9500, 7000),
                    "player:2": _brain_asset("player:2", 5000, 4200, 6800),
                    "player:3": _brain_asset("player:3", 5000, None, None),
                    "pick:2028:1:1": _brain_asset("pick:2028:1:1", 6000, 5000, 7500),
                },
                "timeline": {}, "summary": {}, "diagnostics": {},
                "safety": {"unsafe_adjustments": 0},
            },
        }
        self.state = {"data": self.data, "last_sync": "2026-08-06T00:00:00+00:00"}
        self._append("player_week", "former-week", "99", {"fantasy_points": 10.0})
        self._append("player_week", "retired-week", "3", {"fantasy_points": 8.0})
        self.store.upsert_identity(
            "DTOS-P-99", "Sleeper", "99", "Former Player", 100,
            "2024-01-01T00:00:00+00:00", {"position": "WR"},
        )
        self._append("trade", "trade-123", None, {
            "transaction_id": "trade-123", "type": "trade", "status": "complete",
            "roster_ids": [1, 2], "adds": {}, "drops": {}, "draft_picks": [],
            "source_league_id": self.league_id,
        })
        self.cache = AssetMarketCache()
        self.market = self.cache.get(self.data, self.state, self.store, self.league_id)

    def tearDown(self) -> None:
        asset_market_cache.wait_for_background()
        asset_market_cache.clear()
        self.temp.cleanup()

    @staticmethod
    def _ready_get(client: TestClient, path: str):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            response = client.get(path)
            if response.status_code != 503:
                return response
            time.sleep(0.01)
        raise AssertionError(f"Asset Market did not publish for {path}")

    def _append(
        self, entity_type: str, source: str, player_id: str | None,
        payload: dict, *, store: HistoricalStore | None = None,
    ) -> None:
        (store or self.store).append(
            record_key=f"{entity_type}:{source}", entity_type=entity_type,
            league_id=self.league_id, source_record_id=source,
            observed_at="2025-09-01T00:00:00+00:00",
            retrieved_at="2025-09-01T00:00:00+00:00", provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload=payload, season=2025, week=1, player_id=player_id,
        )

    def test_complete_canonical_asset_discovery_and_classification(self) -> None:
        health = self.market.health()
        self.assertEqual(health["counts"]["total"], 4)
        self.assertEqual(health["duplicate_asset_ids"], 0)
        self.assertEqual(self.market.by_id["player:10213"]["availability"], "rostered")
        self.assertEqual(self.market.by_id["player:2"]["availability"], "day_traders_free_agent")
        self.assertEqual(self.market.by_id["player:3"]["availability"], "retired")

    def test_published_health_exposes_atomic_artifact_dataset_scope(self) -> None:
        health = self.cache.health()
        expected = (self.market.dataset_version, "artifact_build")
        self.assertEqual(
            (health["historical_dataset_version"],
             health["historical_dataset_version_scope"]), expected,
        )
        self.assertEqual(
            (health["cache"]["historical_dataset_version"],
             health["cache"]["historical_dataset_version_scope"]), expected,
        )
        self.assertEqual(
            health["cache"]["artifact_compatibility"], "compatible",
        )

    def test_cold_warming_health_does_not_fabricate_dataset_scope(self) -> None:
        health = AssetMarketCache().health()
        self.assertIsNone(health.get("historical_dataset_version"))
        self.assertIsNone(health.get("historical_dataset_version_scope"))
        self.assertIsNone(health["cache"].get("historical_dataset_version"))
        self.assertIsNone(
            health["cache"].get("historical_dataset_version_scope"),
        )

    def test_durable_compatible_generation_survives_process_cache_restart(self) -> None:
        first_path = self.market._artifact_path
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("compatible durable generation must not rebuild"),
        ):
            loaded = restarted.get(self.data, self.state, self.store, self.league_id)
        self.assertEqual(loaded._artifact_path, first_path)
        self.assertEqual(loaded.directory(limit=4), self.market.directory(limit=4))
        self.assertEqual(
            restarted._request_marker,
            restarted.request_marker(self.data, self.state, self.store, self.league_id),
        )
        with patch.object(restarted, "_start_background") as worker:
            self.assertIs(
                restarted.get(
                    self.data, self.state, self.store, self.league_id,
                    background=True,
                ),
                loaded,
            )
        worker.assert_not_called()
        health = restarted.health()
        self.assertEqual(
            health["historical_dataset_version_scope"], "artifact_build",
        )
        self.assertEqual(
            health["cache"]["historical_dataset_version_scope"], "artifact_build",
        )

    def test_startup_restore_uses_manifest_and_performs_no_construction(self) -> None:
        manifest = AssetMarketCache.artifact_manifest_path(self.store)
        self.assertTrue(manifest.is_file())
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("compatible startup restore must not build"),
        ):
            self.assertTrue(restarted.restore_compatible(
                self.data, self.state, self.store, self.league_id,
            ))
        health = restarted.health()["cache"]
        self.assertEqual(health["artifact_compatibility"], "compatible")
        self.assertEqual(health["artifact_loads"], 1)
        self.assertEqual(health["attempted_constructions"], 0)
        self.assertGreaterEqual(health["artifact_candidates"], 1)

    def test_cold_cache_reports_discovery_pending_before_bounded_discovery(self) -> None:
        health = AssetMarketCache().health()["cache"]
        self.assertEqual(health["artifact_compatibility"], "discovery_pending")

    def test_timestamp_only_sync_and_brain_changes_reuse_artifact(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["valuation_intelligence"]["generated_at"] = (
            "2026-08-07T12:34:56+00:00"
        )
        state = {**self.state, "last_sync": "2026-08-07T12:34:55+00:00"}
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("timestamp-only changes must reuse"),
        ):
            loaded = restarted.get(changed, state, self.store, self.league_id)
        self.assertEqual(loaded._artifact_path, self.market._artifact_path)
        self.assertEqual(
            restarted.health()["cache"]["artifact_compatibility"], "compatible",
        )
        self.assertEqual(
            restarted.health()["historical_dataset_version_scope"],
            "artifact_build",
        )

    def test_nested_observation_metadata_does_not_invalidate_artifact(self) -> None:
        changed = copy.deepcopy(self.data)
        asset = changed["valuation_intelligence"]["assets"]["player:10213"]
        asset["valuation_layers"]["market_value"].update({
            "generated_at": "2026-08-07T12:34:56+00:00",
            "retrieved_at": "2026-08-07T12:34:55+00:00",
        })
        asset["evidence_sources"][0].update({
            "observed_at": "2026-08-07T12:34:54+00:00",
            "latency_ms": 987.654,
        })
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("observation metadata must not rebuild"),
        ):
            loaded = restarted.get(
                changed, self.state, self.store, self.league_id,
            )
        self.assertEqual(loaded._artifact_path, self.market._artifact_path)
        self.assertEqual(
            restarted.health()["cache"]["artifact_compatibility"], "compatible",
        )

    def test_history_only_observation_reuses_compact_artifact(self) -> None:
        self._append("transaction", "history-only-transaction", None, {
            "transaction_id": "history-only-transaction", "type": "waiver",
        })
        restarted = AssetMarketCache()
        with patch(
            "src.core.asset_market.engine.build_read_model",
            side_effect=AssertionError("history-only evidence must not rebuild"),
        ):
            loaded = restarted.get(
                self.data, self.state, self.store, self.league_id,
            )
        self.assertEqual(loaded._artifact_path, self.market._artifact_path)
        self.assertEqual(
            loaded.detail("player:10213")["historical_dataset_version"],
            self.store.dataset_version(self.league_id),
        )

    def test_material_brain_value_change_invalidates_artifact(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["valuation_intelligence"]["assets"]["player:10213"][
            "valuation_layers"
        ]["market_value"]["value"] = 9301
        expected = self.cache.artifact_contract(
            changed, self.state, self.store, self.league_id,
        )
        generation = self.cache.durable_generation(
            changed, self.state, self.store, self.league_id, expected,
        )
        artifact, reason = self.cache._discover_artifact(
            self.store, generation, expected,
        )
        self.assertIsNone(artifact)
        self.assertEqual(reason, "brain_semantic_output_changed")
        replacement_cache = AssetMarketCache()
        replacement = replacement_cache.get(
            changed, self.state, self.store, self.league_id,
        )
        self.assertNotEqual(replacement._artifact_path, self.market._artifact_path)
        self.assertEqual(
            replacement.by_id["player:10213"]["values"]["market_value"], 9301,
        )
        self.assertIs(
            replacement_cache.get(changed, self.state, self.store, self.league_id),
            replacement,
        )
        self.assertEqual(replacement_cache.build_count, 1)

    def test_ownership_change_invalidates_artifact(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["teams"][0]["players"] = []
        replacement = AssetMarketCache().get(
            changed, self.state, self.store, self.league_id,
        )
        self.assertNotEqual(replacement._artifact_path, self.market._artifact_path)
        self.assertEqual(
            replacement.by_id["player:10213"]["availability"],
            "day_traders_free_agent",
        )

    def test_consumed_provider_value_invalidates_artifact(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["market_data"]["providers"] = {
            "FantasyCalc": {
                "10213": {"value": 9000, "confidence": 80, "rank": 1},
            },
        }
        replacement = AssetMarketCache().get(
            changed, self.state, self.store, self.league_id,
        )
        self.assertNotEqual(replacement._artifact_path, self.market._artifact_path)
        providers = replacement._read_model.canonical("player:10213")["providers"]
        self.assertEqual(providers[2]["raw_value"], 9000.0)

    def test_artifact_discovery_reports_corrupt_and_never_discloses_path(self) -> None:
        other = HistoricalStore(Path(self.temp.name) / "corrupt-history.sqlite3")
        candidate = other.path.with_name(
            f".{other.path.stem}.asset-market-corrupt.sqlite3"
        )
        candidate.write_bytes(b"not sqlite")
        expected = self.cache.artifact_contract(
            self.data, self.state, other, self.league_id,
        )
        path, reason = self.cache._discover_artifact(
            other, "missing-generation", expected,
        )
        self.assertIsNone(path)
        self.assertEqual(reason, "artifact_corrupt")
        self.assertNotIn(str(candidate.parent), reason)

    def test_artifact_metadata_hydration_yields_between_bounded_chunks(self) -> None:
        yields: list[int] = []
        chunks: list[dict[str, object]] = []
        result = self.market._read_model.cooperative_summary_metadata(
            chunk_size=1,
            yield_control=lambda: yields.append(1),
            chunk_observer=chunks.append,
        )
        self.assertEqual(result["counts"], self.market.health()["counts"])
        self.assertEqual(result["duplicate_asset_ids"], 0)
        self.assertEqual(len(chunks), len(self.market.assets))
        self.assertEqual(len(yields), len(chunks))
        self.assertTrue(all(int(chunk["rows"]) <= 1 for chunk in chunks))

    def test_cold_construction_yields_between_bounded_chunks(self) -> None:
        yields: list[int] = []

        def rows():
            for sequence in range(5):
                yield ({
                    "asset_id": f"player:{sequence}",
                    "asset_type": "player",
                    "display_name": f"Player {sequence}",
                    "availability": "free_agent",
                    "values": {},
                }, {"asset_id": f"player:{sequence}"})

        target = Path(self.temp.name) / "cooperative.sqlite3"
        model = build_read_model(
            target, "cooperative", rows(), {}, chunk_size=2,
            yield_control=lambda: yields.append(1),
        )
        self.assertEqual(model.asset_count, 5)
        self.assertEqual(yields, [1, 1, 1])

    def test_spawned_semantic_generation_matches_reference_digest(self) -> None:
        expected = self.cache.semantic_identities(self.data, self.state)
        observed = self.cache._isolated_semantic_identities(
            self.data, self.state,
            self.cache.request_marker(
                self.data, self.state, self.store, self.league_id,
            ),
            self.league_id,
        )
        self.assertEqual(observed, expected)
        metrics = self.cache.metrics()["semantic_preparation"]
        self.assertEqual(metrics["execution"], "spawned_subprocess")
        self.assertTrue(metrics["reaped"])
        self.assertEqual(metrics["records"], expected["asset_count"])
        self.assertEqual(metrics["semantic_identities"], {
            name: expected[name] for name in (
                "asset_universe_digest", "brain_semantic_output_digest",
                "ownership_dependency_digest", "provider_evidence_digest",
            )
        })

    def test_semantic_generation_is_deterministic_across_repeated_processes(self) -> None:
        marker = self.cache.request_marker(
            self.data, self.state, self.store, self.league_id,
        )
        first = self.cache._isolated_semantic_identities(
            self.data, self.state, marker, self.league_id,
        )
        second = self.cache._isolated_semantic_identities(
            self.data, self.state, marker, self.league_id,
        )
        self.assertEqual(second, first)

    def test_semantic_process_handles_variable_asset_complexity(self) -> None:
        data = copy.deepcopy(self.data)
        data["valuation_intelligence"]["assets"]["player:10213"].update({
            "comparison": {
                "windows": [{"values": list(range(100))} for _ in range(4)],
            },
            "provider_evidence": [
                {"provider": f"provider-{index}", "values": list(range(40))}
                for index in range(8)
            ],
        })
        observed = self.cache._isolated_semantic_identities(
            data, self.state,
            self.cache.request_marker(data, self.state, self.store, self.league_id),
            self.league_id,
        )
        reference = self.cache.semantic_identities(data, self.state)
        self.assertEqual(observed, reference)
        self.assertLess(self.cache.metrics()["semantic_preparation"]["input_bytes"], 1_000_000)

    def test_semantic_spawn_failure_is_sanitized_and_fails_closed(self) -> None:
        def unavailable(*_args, **_kwargs):
            raise FileNotFoundError("private worker path")

        cache = AssetMarketCache(semantic_process_factory=unavailable)
        with self.assertRaisesRegex(SemanticWorkerError, "FileNotFoundError"):
            cache._isolated_semantic_identities(
                self.data, self.state,
                cache.request_marker(
                    self.data, self.state, self.store, self.league_id,
                ),
                self.league_id,
            )
        metrics = cache.metrics()["semantic_preparation"]
        self.assertEqual(metrics["failure"], "spawn_or_pipe_failure")
        self.assertNotIn("private worker path", str(metrics))

    def test_semantic_timeout_terminates_and_reaps_child(self) -> None:
        class Sink:
            def write(self, value):
                return len(value)

            def flush(self):
                return None

            def close(self):
                return None

        class TimedOut:
            pid = os.getpid()
            returncode = None

            def __init__(self):
                self.stdin = Sink()
                self.terminated = False

            def communicate(self, timeout=None):
                if not self.terminated:
                    raise subprocess.TimeoutExpired("semantic-worker", timeout)
                self.returncode = -15
                return b"", b""

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.terminated = True

            def wait(self, timeout=None):
                self.returncode = -15
                return self.returncode

            def poll(self):
                return self.returncode

        process = TimedOut()
        cache = AssetMarketCache(
            semantic_process_factory=lambda *_args, **_kwargs: process,
        )
        with patch(
            "src.core.asset_market.engine.SEMANTIC_CHILD_TIMEOUT_SECONDS", 0.001,
        ), self.assertRaisesRegex(SemanticWorkerError, "timed out"):
            cache._isolated_semantic_identities(
                self.data, self.state,
                cache.request_marker(
                    self.data, self.state, self.store, self.league_id,
                ),
                self.league_id,
            )
        metrics = cache.metrics()["semantic_preparation"]
        self.assertEqual(metrics["failure"], "timeout")
        self.assertTrue(metrics["reaped"])
        self.assertEqual(metrics["exit_status"], -15)

    def test_semantic_output_contract_rejects_wrong_generation_and_digest(self) -> None:
        valid = {
            "protocol": "dtos-market-semantic-v1",
            "request_generation": "request",
            "status": "ok",
            "digests": {
                "asset_universe": "0" * 64,
                "brain_semantic_output": "1" * 64,
                "ownership_dependency": "2" * 64,
                "provider_evidence": "3" * 64,
            },
            "asset_count": 2,
            "valuation_schema_version": "1.0",
            "timing": {"records": 2, "input_bytes": 100},
        }
        with self.assertRaisesRegex(SemanticWorkerError, "identity"):
            self.cache._validate_semantic_output(
                {**valid, "request_generation": "stale"},
                "request", 2, "1.0", 100,
            )
        malformed = copy.deepcopy(valid)
        malformed["digests"]["provider_evidence"] = "not-a-digest"
        with self.assertRaisesRegex(SemanticWorkerError, "digest"):
            self.cache._validate_semantic_output(
                malformed, "request", 2, "1.0", 100,
            )

    def test_publication_performs_no_bulk_summary_reconstruction(self) -> None:
        published = AssetMarketCache()
        with patch.object(
            self.market._read_model,
            "cooperative_summary_metadata",
            side_effect=AssertionError("publication must use prepared metadata"),
        ):
            result = published._publish(
                self.market, "fixture-key", "fixture-store",
            )
        self.assertIs(result, self.market)
        self.assertIs(published._market, self.market)
        self.assertEqual(published.health()["cache"]["build_count"], 1)

    def test_publication_notifies_optional_presentation_observer_once(self) -> None:
        published = AssetMarketCache()
        observed: list[str] = []
        published.on_publish(lambda: observed.append("published"))
        published._publish(self.market, "fixture-key", "fixture-store")
        self.assertEqual(observed, ["published"])

    def test_presentation_observer_failure_cannot_rollback_market(self) -> None:
        published = AssetMarketCache()
        published.on_publish(
            lambda: (_ for _ in ()).throw(RuntimeError("optional capture failed")),
        )
        result = published._publish(
            self.market, "fixture-key", "fixture-store",
        )
        self.assertIs(result, self.market)
        self.assertIs(published.current(), self.market)

    def test_replacement_publication_retains_incompatibility_reason(self) -> None:
        published = AssetMarketCache()
        published._publish(self.market, "original-key", "fixture-store")
        with published._lock:
            published._artifact_compatibility = "brain_semantic_output_changed"
        published._publish(self.market, "replacement-key", "fixture-store")
        self.assertEqual(
            published.health()["cache"]["artifact_compatibility"],
            "brain_semantic_output_changed",
        )

    def test_background_generation_preserves_identity_and_serialized_output(self) -> None:
        background = AssetMarketCache()
        with self.assertRaises(MarketWarmingError):
            background.get(
                self.data, self.state, self.store, self.league_id,
                background=True,
            )
        self.assertTrue(background.wait_for_background())
        loaded = background.get(
            self.data, self.state, self.store, self.league_id,
            background=True,
        )
        self.assertEqual(loaded.generated_at, self.market.generated_at)
        self.assertEqual(loaded.directory(limit=4), self.market.directory(limit=4))
        self.assertEqual(loaded.detail("player:10213", 1), self.market.detail("player:10213", 1))

    def test_directory_pages_before_detail_hydration(self) -> None:
        with patch.object(
            self.market._read_model, "canonical",
            side_effect=AssertionError("directory must not hydrate canonical detail"),
        ):
            result = self.market.directory(limit=2)
        self.assertEqual(len(result["assets"]), 2)
        self.assertEqual(result["total"], 4)

    def test_search_reads_compact_rows_without_full_universe_iteration(self) -> None:
        with patch(
            "src.core.asset_market.read_model.AssetSequence.__iter__",
            side_effect=AssertionError("search must use the durable index"),
        ):
            result = self.market.search("Josh Allen", 10)
        self.assertEqual(result["results"][0]["asset_id"], "player:10213")

    def test_memory_guard_refuses_unsafe_stage_before_allocation(self) -> None:
        with patch(
            "src.core.asset_market.read_model.memory_snapshot",
            return_value={
                "rss_bytes": 1, "vms_bytes": 1, "system_available_bytes": 1,
                "cgroup_current_bytes": 1500 * 1024 * 1024,
                "cgroup_limit_bytes": 2048 * 1024 * 1024,
            },
        ):
            with self.assertRaises(MarketMemoryBudgetError):
                enforce_memory_budget("fixture", 64 * 1024 * 1024)

    @staticmethod
    def _cgroup_snapshot(*, current: int, inactive: int | None) -> dict:
        return {
            "rss_bytes": 400 * 1024 * 1024,
            "vms_bytes": 1,
            "system_available_bytes": 1,
            "cgroup_current_bytes": current,
            "cgroup_limit_bytes": 2048 * 1024 * 1024,
            "cgroup_inactive_file_bytes": inactive,
            "cgroup_memory_events": {
                "low": 0, "high": 0, "max": 0,
                "oom": 0, "oom_kill": 0, "oom_group_kill": 0,
            },
        }

    def test_memory_admission_discounts_only_inactive_file(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=1500 * 1024 * 1024,
            inactive=1050 * 1024 * 1024,
        ))
        self.assertTrue(result["admitted"])
        self.assertEqual(result["accounting_mode"], "cgroup_working_set")
        self.assertEqual(
            result["effective_working_set_bytes"], 450 * 1024 * 1024,
        )

    def test_memory_admission_rejects_same_raw_usage_without_reclaimable_cache(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=1500 * 1024 * 1024, inactive=0,
        ))
        self.assertFalse(result["admitted"])
        self.assertEqual(
            result["reason"], "predicted_effective_usage_exceeds_target",
        )

    def test_production_shape_admits_verified_reclaimable_file_cache(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=1_849_692_160, inactive=1_565_327_360,
        ))
        self.assertTrue(result["admitted"])
        self.assertEqual(result["reason"], "admitted")
        self.assertLess(
            result["predicted_hard_pressure_bytes"],
            result["hard_pressure_ceiling_bytes"],
        )
        self.assertEqual(result["hard_pressure_margin_bytes"], 256 * 1024**2)

    def test_high_raw_low_reclaimable_cache_fails_hard_pressure(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=1_849_692_160, inactive=64 * 1024**2,
        ))
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "hard_cgroup_pressure")

    def test_hard_pressure_fails_even_when_inactive_file_is_material(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=2_100_000_000, inactive=400_000_000,
        ))
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "hard_cgroup_pressure")

    def test_memory_admission_fails_conservatively_for_invalid_stat(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=1500 * 1024 * 1024, inactive=None,
        ))
        self.assertFalse(result["admitted"])
        self.assertEqual(result["accounting_mode"], "conservative")

    def test_memory_admission_rejects_oom_event_advance(self) -> None:
        snapshot = self._cgroup_snapshot(
            current=800 * 1024 * 1024, inactive=300 * 1024 * 1024,
        )
        snapshot["cgroup_memory_events"]["oom"] = 2
        result = memory_admission(
            snapshot, baseline_events={"oom": 1, "oom_kill": 0},
        )
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "memory_event_advanced")

    def test_memory_admission_rejects_inconsistent_inactive_file(self) -> None:
        result = memory_admission(self._cgroup_snapshot(
            current=600 * 1024 * 1024, inactive=700 * 1024 * 1024,
        ))
        self.assertEqual(result["accounting_mode"], "conservative")
        self.assertEqual(
            result["effective_working_set_bytes"], 600 * 1024 * 1024,
        )

    def test_memory_admission_uses_safe_ceiling_for_invalid_max(self) -> None:
        snapshot = self._cgroup_snapshot(
            current=1500 * 1024 * 1024, inactive=1000 * 1024 * 1024,
        )
        snapshot["cgroup_limit_bytes"] = None
        result = memory_admission(snapshot)
        self.assertFalse(result["admitted"])
        self.assertEqual(result["accounting_mode"], "conservative")

    def test_memory_admission_rejects_growth_beyond_stage_estimate(self) -> None:
        result = memory_admission(
            self._cgroup_snapshot(
                current=800 * 1024 * 1024, inactive=0,
            ),
            baseline_effective=600 * 1024 * 1024,
        )
        self.assertFalse(result["admitted"])
        self.assertEqual(result["reason"], "observed_growth_exceeded_estimate")

    def test_memory_backoff_expires_or_clears_after_material_improvement(self) -> None:
        now = [100.0]
        snapshots = [self._cgroup_snapshot(
            current=1500 * 1024 * 1024, inactive=0,
        )]
        cache = AssetMarketCache(
            clock=lambda: now[0], memory_observer=lambda: snapshots[-1],
        )
        marker = ("fixture",)
        error = MarketMemoryBudgetError("fixture", memory_admission(snapshots[-1]))
        cache._record_memory_backoff(marker, error)
        self.assertTrue(cache._memory_backoff_active(marker))
        snapshots.append(self._cgroup_snapshot(
            current=1400 * 1024 * 1024, inactive=100 * 1024 * 1024,
        ))
        self.assertFalse(cache._memory_backoff_active(marker))
        cache._record_memory_backoff(marker, error)
        now[0] += 31.0
        self.assertFalse(cache._memory_backoff_active(marker))

    def test_memory_backoff_does_not_cross_request_generation(self) -> None:
        cache = AssetMarketCache(
            clock=lambda: 100.0,
            memory_observer=lambda: self._cgroup_snapshot(
                current=1500 * 1024 * 1024, inactive=0,
            ),
        )
        error = MarketMemoryBudgetError(
            "fixture", memory_admission(cache._memory_observer()),
        )
        cache._record_memory_backoff(("old",), error)
        self.assertFalse(cache._memory_backoff_active(("new",)))

    def test_repeated_requests_start_one_worker_during_memory_backoff(self) -> None:
        snapshot = self._cgroup_snapshot(
            current=1500 * 1024 * 1024, inactive=0,
        )
        cache = AssetMarketCache(
            clock=lambda: 100.0, memory_observer=lambda: snapshot,
        )
        marker = cache.request_marker(
            self.data, self.state, self.store, self.league_id,
        )
        error = MarketMemoryBudgetError("fixture", memory_admission(snapshot))
        with patch.object(cache, "_prepare_generation", side_effect=error):
            cache._start_background(
                self.data, self.state, self.store, self.league_id, marker,
            )
            self.assertTrue(cache.wait_for_background())
            for _ in range(3):
                cache._start_background(
                    self.data, self.state, self.store, self.league_id, marker,
                )
        self.assertEqual(cache.attempted_constructions, 1)
        self.assertEqual(cache.failed_constructions, 1)
        self.assertEqual(cache.metrics()["build_phase"], "memory_backoff")

    def test_concurrent_cold_requests_share_one_background_build(self) -> None:
        cache = AssetMarketCache()
        changed_state = {**self.state, "last_sync": "background-fixture"}
        entered = threading.Event()
        release = threading.Event()

        def prepare(*_args: object) -> None:
            entered.set()
            release.wait(1)

        with patch.object(cache, "_prepare_generation", side_effect=prepare) as build:
            with self.assertRaises(MarketWarmingError):
                cache.get(
                    self.data, changed_state, self.store, self.league_id,
                    background=True,
                )
            self.assertTrue(entered.wait(1))
            first_thread = cache._build_thread
            with self.assertRaises(MarketWarmingError):
                cache.get(
                    self.data, changed_state, self.store, self.league_id,
                    background=True,
                )
            self.assertIs(cache._build_thread, first_thread)
            self.assertEqual(build.call_count, 1)
            release.set()
            if first_thread:
                first_thread.join(timeout=1)

    def test_front_office_detail_changes_do_not_duplicate_market_generation(self) -> None:
        first = self.market.detail("player:10213", 1)
        second = self.market.detail("player:10213", 2)
        self.assertEqual(first["market_generation"], second["market_generation"])
        self.assertEqual(self.cache.build_count, 1)

    def test_failed_atomic_rebuild_preserves_valid_generation_and_removes_partial(self) -> None:
        target = self.market._artifact_path
        before = target.read_bytes()

        def failed_rows():
            yield self.market.by_id["player:10213"], self.market._read_model.canonical("player:10213")
            raise RuntimeError("fixture build failure")

        with self.assertRaisesRegex(RuntimeError, "fixture build failure"):
            build_read_model(target, "replacement", failed_rows(), {})
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(any(target.parent.glob(f".{target.name}.*.partial")))

    def test_stable_ranking_and_explicit_tie_breaker(self) -> None:
        result = self.market.directory(sort="market")
        tied = [row["asset_id"] for row in result["assets"] if row["values"]["market_value"] == 5000]
        self.assertEqual(tied, sorted(tied, reverse=True))
        self.assertEqual(result["tie_breaker"], "canonical_asset_id")
        self.assertEqual(result, self.market.directory(sort="market"))

    def test_search_spans_players_picks_former_players_teams_and_trades(self) -> None:
        self.assertEqual(self.market.search("Josh Allen")["results"][0]["asset_id"], "player:10213")
        self.assertEqual(self.market.search("2028 1st")["results"][0]["asset_type"], "pick")
        self.assertEqual(self.market.search("free-agent tight ends")["results"][0]["asset_id"], "player:2")
        self.assertTrue(any(row["display_name"] == "Former Player" for row in self.market.search("Former Player")["results"]))
        self.assertTrue(any(row["asset_type"] == "team" for row in self.market.search("Puka Cola Quantum")["results"]))
        self.assertTrue(any(row["asset_type"] == "trade" for row in self.market.search("trade-123")["results"]))

    def test_value_layers_remain_separate_and_missing_market_is_not_substituted(self) -> None:
        detail = self.market.detail("player:10213", 1)
        self.assertEqual(detail["value_layers"]["market_value"]["value"], 9200)
        self.assertEqual(detail["value_layers"]["contender_value"]["value"], 9500)
        retired = self.market.detail("player:3")
        self.assertIsNone(retired["value_layers"]["intrinsic_dtos_value"]["value"])
        self.assertEqual(retired["value_layers"]["intrinsic_dtos_value"]["availability"], "unavailable")
        self.assertTrue(retired["value_layers"]["intrinsic_dtos_value"]["limitations"])

    def test_contender_and_rebuilder_views_diverge_from_canonical_layers(self) -> None:
        contender = self.market.directory(sort="contender")["assets"]
        rebuilder = self.market.directory(sort="rebuilder")["assets"]
        self.assertEqual(contender[0]["asset_id"], "player:10213")
        self.assertEqual(rebuilder[0]["asset_id"], "pick:2028:1:1")
        self.assertNotEqual(contender[0]["asset_id"], rebuilder[0]["asset_id"])

    def test_directory_and_detail_use_the_same_canonical_brain_layers(self) -> None:
        directory = {
            row["asset_id"]: row for row in self.market.directory(limit=10)["assets"]
        }
        for asset_id in ("player:10213", "player:2", "pick:2028:1:1"):
            detail = self.market.detail(asset_id)
            for layer in ("contender_value", "rebuilder_value"):
                self.assertEqual(
                    directory[asset_id]["values"][layer],
                    detail["value_layers"][layer]["value"],
                )

    def test_retired_asset_has_no_contextual_ranking_value_without_evidence(self) -> None:
        row = self.market.by_id["player:3"]
        self.assertIsNone(row["values"]["contender_value"])
        self.assertIsNone(row["values"]["rebuilder_value"])

    def test_trending_requires_two_timestamped_observations(self) -> None:
        result = self.market.trending()
        self.assertEqual(result["availability"], "unavailable")
        self.assertEqual(result["most_discussed"]["status"], "unsupported")
        self.data["valuation_intelligence"]["timeline"] = {
            "player:10213": [
                {"timestamp": "2026-01-01", "confidence": 60},
                {"timestamp": "2026-02-01", "confidence": 80},
            ],
        }
        refreshed = AssetMarketCache().get(self.data, self.state, self.store, self.league_id)
        self.assertEqual(refreshed.trending()["biggest_risers"][0]["magnitude"], 20)

    def test_cache_is_single_flight_and_history_reads_track_dataset(self) -> None:
        results = []
        threads = [threading.Thread(target=lambda: results.append(
            self.cache.get(self.data, self.state, self.store, self.league_id)
        )) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(result is self.market for result in results))
        self.assertEqual(self.cache.build_count, 1)
        original_store_identity = self.cache.store_identity(self.store)
        self._append("player_week", "new-evidence", "10213", {"fantasy_points": 20.0})
        self.assertEqual(original_store_identity, self.cache.store_identity(self.store))
        self.assertIs(
            self.cache.get(self.data, self.state, self.store, self.league_id),
            self.market,
        )
        self.assertEqual(self.cache.build_count, 1)
        self.assertEqual(
            self.market.detail("player:10213")["historical_dataset_version"],
            self.store.dataset_version(self.league_id),
        )

    def test_generation_replacement_releases_superseded_market(self) -> None:
        cache = AssetMarketCache()
        previous = cache.get(self.data, self.state, self.store, self.league_id)
        old_confidence = previous.by_id["player:10213"]["confidence"]
        reference = weakref.ref(previous)
        changed_data = copy.deepcopy(self.data)
        changed_data["valuation_intelligence"]["assets"]["player:10213"][
            "scores"
        ]["confidence"] += 1
        changed_data["valuation_intelligence"]["generated_at"] = (
            "2026-08-07T00:00:00+00:00"
        )
        changed_data["asset_market_semantic_revision"] = (
            "material-confidence-change"
        )
        current = cache.get(
            changed_data, self.state, self.store, self.league_id,
        )
        del previous
        gc.collect()
        self.assertIsNone(reference())
        new_confidence = current.by_id["player:10213"]["confidence"]
        self.assertNotEqual(new_confidence, old_confidence)
        self.assertEqual(cache.build_count, 2)

    def test_failed_publication_does_not_expose_marker_or_model(self) -> None:
        cache = AssetMarketCache()
        market = cache.get(self.data, self.state, self.store, self.league_id)
        marker = cache._request_marker
        key = cache._key
        health_pair = (
            cache.health()["historical_dataset_version"],
            cache.health()["historical_dataset_version_scope"],
        )
        compatibility = cache.health()["cache"]["artifact_compatibility"]
        changed = copy.deepcopy(self.data)
        changed["valuation_intelligence"]["generated_at"] = "new-generation"
        replacement = AssetMarketCache().get(
            changed, self.state, self.store, self.league_id,
        )
        cache._epoch = 2
        with self.assertRaisesRegex(RuntimeError, "superseded"):
            cache._publish(
                replacement, "replacement-key", cache.store_identity(self.store),
                cache.request_marker(changed, self.state, self.store, self.league_id),
                epoch=1,
            )
        self.assertIs(cache._market, market)
        self.assertEqual(cache._request_marker, marker)
        self.assertEqual(cache._key, key)
        self.assertEqual(
            (cache.health()["historical_dataset_version"],
             cache.health()["historical_dataset_version_scope"]),
            health_pair,
        )
        self.assertEqual(
            cache.health()["cache"]["artifact_compatibility"], compatibility,
        )

    def test_last_valid_warming_health_retains_dataset_scope_pair(self) -> None:
        with self.cache._lock:
            self.cache._building = True
            self.cache._build_phase = "building"
        try:
            health = self.cache.health()
        finally:
            with self.cache._lock:
                self.cache._building = False
                self.cache._build_phase = "idle"
        expected = (self.market.dataset_version, "artifact_build")
        self.assertEqual(health["availability"], "last_valid_refreshing")
        self.assertEqual(
            (health["historical_dataset_version"],
             health["historical_dataset_version_scope"]), expected,
        )
        self.assertEqual(
            (health["cache"]["historical_dataset_version"],
             health["cache"]["historical_dataset_version_scope"]), expected,
        )

    def test_nonsemantic_markers_start_no_replacement_worker(self) -> None:
        cache = AssetMarketCache()
        market = cache.get(self.data, self.state, self.store, self.league_id)
        original_generated_at = self.data["valuation_intelligence"]["generated_at"]
        self.data["valuation_intelligence"]["generated_at"] = "later-observation"
        try:
            with patch.object(cache, "_start_background") as worker:
                result = cache.get(
                    self.data, {**self.state, "last_sync": "later-sync"},
                    self.store, self.league_id, background=True,
                )
        finally:
            self.data["valuation_intelligence"]["generated_at"] = original_generated_at
        self.assertIs(result, market)
        worker.assert_not_called()
        self.assertEqual(cache.build_count, 1)

    def test_replaced_data_object_with_same_semantic_revision_starts_no_worker(self) -> None:
        cache = AssetMarketCache()
        market = cache.get(self.data, self.state, self.store, self.league_id)
        replacement = copy.deepcopy(self.data)
        replacement["asset_market_semantic_revision"] = cache.request_marker(
            self.data, self.state, self.store, self.league_id,
        )[-1]
        replacement["valuation_intelligence"]["generated_at"] = "later-observation"
        before = cache.metrics()
        with patch.object(cache, "_start_background") as worker:
            result = cache.get(
                replacement, {**self.state, "last_sync": "later-sync"},
                self.store, self.league_id, background=True,
            )
            cache.reconcile(
                replacement, {**self.state, "last_sync": "another-sync"},
                self.store, self.league_id,
            )
        self.assertIs(result, market)
        worker.assert_not_called()
        after = cache.metrics()
        self.assertEqual(after["attempted_constructions"], before["attempted_constructions"])
        self.assertEqual(after["market_actual_constructions"], before["market_actual_constructions"])
        self.assertEqual(after["market_generation"], before["market_generation"])

    def test_final_semantic_admission_guard_skips_stale_request_marker(self) -> None:
        cache = AssetMarketCache()
        market = cache.get(self.data, self.state, self.store, self.league_id)
        before = cache.metrics()
        stale_marker = (*cache._request_marker[:-1], "stale-refresh-marker")
        cache._start_background(
            self.data, self.state, self.store, self.league_id, stale_marker,
        )
        self.assertTrue(cache.wait_for_background())
        metrics = cache.metrics()
        self.assertIs(cache._market, market)
        self.assertEqual(metrics["market_rebuild_requests_noop"], 0)
        self.assertEqual(metrics["market_rebuild_requests_semantic"], 0)
        self.assertEqual(metrics["market_construction_admission_skips"], 0)
        self.assertEqual(metrics["scheduler_skip_reason"], "generation_superseded")
        self.assertEqual(
            metrics["market_actual_constructions"],
            before["market_actual_constructions"],
        )
        self.assertEqual(metrics["build_count"], 1)
        self.assertEqual(
            metrics["durable_publications"], before["durable_publications"],
        )

    def test_semantic_identity_is_deterministic_across_revert(self) -> None:
        baseline = self.cache.artifact_contract(
            self.data, self.state, self.store, self.league_id,
        )
        changed = copy.deepcopy(self.data)
        changed["valuation_intelligence"]["assets"]["player:10213"]["scores"][
            "confidence"
        ] += 1
        material = self.cache.artifact_contract(
            changed, self.state, self.store, self.league_id,
        )
        reverted = self.cache.artifact_contract(
            copy.deepcopy(self.data), self.state, self.store, self.league_id,
        )
        self.assertNotEqual(
            baseline["brain_semantic_output_digest"],
            material["brain_semantic_output_digest"],
        )
        self.assertEqual(baseline, reverted)

    def test_api_ui_agree_and_reads_never_sync(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with patch("routes.market.historical_store", self.store):
            client = TestClient(app)
            with patch("services.sleeper.sync_sleeper", new=AsyncMock()) as sync:
                self.assertIn("Asset Market", self._ready_get(client, "/market").text)
                self.assertEqual(self._ready_get(client, "/api/market").status_code, 200)
                directory = self._ready_get(
                    client, "/api/market/assets?limit=2",
                ).json()
                self.assertEqual(directory["limit"], 2)
                self.assertEqual(
                    directory["historical_dataset_version_scope"],
                    "artifact_build",
                )
                health = self._ready_get(client, "/api/market/health").json()
                self.assertEqual(
                    health["historical_dataset_version_scope"],
                    "artifact_build",
                )
                self.assertEqual(
                    health["cache"]["historical_dataset_version_scope"],
                    "artifact_build",
                )
                self.assertEqual(self._ready_get(client, "/api/market/assets/player:10213").status_code, 200)
                search = self._ready_get(
                    client, "/api/market/search?q=Josh%20Allen",
                ).json()
                self.assertEqual(
                    search["historical_dataset_version_scope"], "live_store",
                )
                self.assertEqual(self._ready_get(client, "/api/market/trending").status_code, 200)
                sync.assert_not_awaited()

    def test_market_summary_is_retained_metadata_only_in_every_lifecycle_state(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        progress = {
            "canonical_history_progress": {
                "status": "completed_with_pending",
                "completed_steps": 5,
                "total_steps": 6,
                "completed_seasons": [2021, 2022, 2023, 2024, 2025],
                "pending_seasons": [2026],
                "consistent": True,
            },
        }
        states = (
            {
                "status": "warming", "availability": "warming",
                "counts": {}, "cache": {"build_active": False},
            },
            {
                "status": "warming", "availability": "warming",
                "counts": {}, "cache": {"build_active": True},
            },
            {
                "status": "ready", "availability": "available",
                "historical_dataset_version": "dataset-one",
                "historical_dataset_version_scope": "artifact_build",
                "market_generation": "market-one", "counts": {"assets": 4},
                "cache": {"build_active": False, "build_count": 1},
            },
            {
                "status": "warming", "availability": "last_valid_refreshing",
                "historical_dataset_version": "dataset-one",
                "historical_dataset_version_scope": "artifact_build",
                "market_generation": "market-one", "counts": {"assets": 4},
                "cache": {"build_active": True, "build_count": 1},
            },
            {
                "status": "ready", "availability": "available",
                "last_error": "replacement failed",
                "historical_dataset_version": "dataset-one",
                "historical_dataset_version_scope": "artifact_build",
                "market_generation": "market-one", "counts": {"assets": 4},
                "cache": {"build_active": False, "build_count": 1},
            },
            {
                "status": "failed", "availability": "warming",
                "last_error": "cold build failed", "counts": {},
                "cache": {"build_active": False, "build_count": 0},
            },
        )
        client = TestClient(app)
        with (
            patch.object(asset_market_cache, "get") as get,
            patch.object(asset_market_cache, "_start_background") as worker,
            patch(
                "routes.market.retained_history_progress_contracts",
                return_value=progress,
            ) as retained,
        ):
            for state in states:
                with self.subTest(state=state["status"], availability=state["availability"]):
                    with patch.object(asset_market_cache, "health", return_value=state):
                        response = client.get("/api/market")
                    self.assertEqual(response.status_code, 200)
                    payload = response.json()
                    self.assertEqual(payload["historical_progress"], progress)
                    self.assertEqual(payload["endpoints"][0], "/api/market/assets")
                    if "historical_dataset_version" in payload:
                        self.assertEqual(
                            payload["historical_dataset_version_scope"],
                            "artifact_build",
                        )
            get.assert_not_called()
            worker.assert_not_called()
            self.assertEqual(retained.call_count, len(states))

    def test_market_summary_repeated_reads_do_not_change_cache_counters(self) -> None:
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        before = asset_market_cache.metrics()
        with patch(
            "routes.market.retained_history_progress_contracts",
            return_value={"canonical_history_progress": {"status": "waiting"}},
        ):
            client = TestClient(app)
            for _ in range(5):
                self.assertEqual(client.get("/api/market").status_code, 200)
        after = asset_market_cache.metrics()
        for field in ("build_count", "cache_hits", "build_active"):
            self.assertEqual(after[field], before[field])

    def test_detail_identity_is_canonical_across_asset_types_and_repeated_reads(self) -> None:
        for asset_id in (
            "player:10213", "player:2", "player:3", "pick:2028:1:1",
        ):
            with self.subTest(asset_id=asset_id):
                first = self.market.detail(asset_id, 1)
                second = self.market.detail(asset_id, 1)
                self.assertEqual(
                    first["brain_snapshot_id"],
                    first["recommendation"]["brain_snapshot_id"],
                )
                self.assertEqual(first["brain_snapshot_id"], second["brain_snapshot_id"])
                self.assertEqual(first["market_generation"], second["market_generation"])
                self.assertEqual(
                    first["historical_dataset_version"], self.market.dataset_version,
                )
                self.assertEqual(
                    first["historical_dataset_version_scope"], "live_store",
                )
                self.assertEqual(
                    first["valuation_generation"],
                    self.data["valuation_intelligence"]["generated_at"],
                )
                self.assertNotEqual(
                    first["brain_snapshot_id"], first["historical_dataset_version"],
                )

    def test_cached_fallback_and_expanded_ui_share_detail_identity(self) -> None:
        self.state["last_sync_error"] = "Sleeper unavailable; using cached data."
        app = FastAPI()
        app.include_router(create_market_router(
            require_data=lambda: self.data, state=self.state,
            league_id=self.league_id,
            page=lambda title, body: HTMLResponse(f"<h1>{title}</h1>{body}"),
        ))
        with patch("routes.market.historical_store", self.store):
            client = TestClient(app)
            payload = self._ready_get(
                client, "/api/market/assets/player:10213",
            ).json()
            html = self._ready_get(
                client,
                "/market?selected=player%3A10213&front_office=1",
            ).text
        snapshot = payload["recommendation"]["brain_snapshot_id"]
        self.assertEqual(payload["brain_snapshot_id"], snapshot)
        self.assertIn(snapshot, html)
        self.assertIn(payload["market_generation"], html)
        self.assertIn(payload["valuation_generation"], html)
        self.assertIn(payload["historical_dataset_version"], html)

    def test_cache_isolates_identical_stores_and_never_discloses_paths(self) -> None:
        other_path = Path(self.temp.name) / "other" / "history.sqlite3"
        other_store = HistoricalStore(other_path)
        self._append(
            "player_week", "former-week", "99", {"fantasy_points": 10.0},
            store=other_store,
        )
        self._append(
            "player_week", "retired-week", "3", {"fantasy_points": 8.0},
            store=other_store,
        )
        other_store.upsert_identity(
            "DTOS-P-99", "Sleeper", "99", "Former Player", 100,
            "2024-01-01T00:00:00+00:00", {"position": "WR"},
        )
        self._append(
            "trade", "trade-123", None,
            {
                "transaction_id": "trade-123", "type": "trade",
                "status": "complete", "roster_ids": [1, 2], "adds": {},
                "drops": {}, "draft_picks": [],
                "source_league_id": self.league_id,
            },
            store=other_store,
        )
        first_assets = self.market.directory(limit=4)["assets"]
        other_market = self.cache.get(
            self.data, self.state, other_store, self.league_id,
        )
        self.assertIsNot(other_market, self.market)
        self.assertNotEqual(other_market.dataset_version, self.market.dataset_version)
        self.assertEqual(
            other_market.directory(limit=4)["assets"],
            first_assets,
        )
        public = str({**other_market.health(), "cache": self.cache.metrics()})
        self.assertNotIn(str(other_path), public)
        self.assertNotIn(str(other_path.parent), public)

    def test_deleted_store_and_recreated_same_path_cannot_reuse_model(self) -> None:
        path = Path(self.temp.name) / "replace" / "history.sqlite3"
        first_store = HistoricalStore(path)
        first_market = self.cache.get(
            self.data, self.state, first_store, self.league_id,
        )
        first_uuid = first_store.database_uuid()
        path.unlink()
        with self.assertRaisesRegex(RuntimeError, "backing database is unavailable"):
            self.cache.get(self.data, self.state, first_store, self.league_id)
        recreated_store = HistoricalStore(path)
        self.assertNotEqual(recreated_store.database_uuid(), first_uuid)
        recreated_market = self.cache.get(
            self.data, self.state, recreated_store, self.league_id,
        )
        self.assertIsNot(recreated_market, first_market)
        self.assertIs(
            self.cache.get(self.data, self.state, recreated_store, self.league_id),
            recreated_market,
        )

    def test_durable_uuid_survives_writes_checkpoints_and_store_restart(self) -> None:
        database_uuid = self.store.database_uuid()
        namespace = self.cache.store_identity(self.store)
        self._append(
            "player_week", "uuid-stability", "10213",
            {"fantasy_points": 21.0},
        )
        with self.store.connection() as connection:
            connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
        restarted = HistoricalStore(self.store.path)
        self.assertEqual(self.store.database_uuid(), database_uuid)
        self.assertEqual(restarted.database_uuid(), database_uuid)
        self.assertEqual(self.cache.store_identity(self.store), namespace)
        self.assertNotEqual(
            self.cache.store_identity(restarted), namespace,
            "Separate store instances must not share a process-global model.",
        )

    def test_repeated_query_surfaces_do_not_rebuild_market(self) -> None:
        for _ in range(5):
            self.market.directory(limit=1)
            self.market.search("QB", limit=1)
            self.market.detail("player:10213", 1)
            self.market.trending(limit=1)
            self.assertIs(
                self.cache.get(self.data, self.state, self.store, self.league_id),
                self.market,
            )
        self.assertEqual(self.cache.build_count, 1)
        self.assertGreaterEqual(self.cache.hits, 5)

    def test_dataset_identity_is_single_flight_and_commit_invalidated(self) -> None:
        initial = self.store.dataset_version(self.league_id)
        computations = self.store.dataset_version_metrics()["computations"]
        versions: list[str] = []
        threads = [threading.Thread(target=lambda: versions.append(
            self.store.dataset_version(self.league_id)
        )) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(versions, [initial] * 8)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self._append(
            "player_week", "identity-invalidation", "10213",
            {"fantasy_points": 22.0},
        )
        changed = self.store.dataset_version(self.league_id)
        self.assertNotEqual(changed, initial)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"],
            computations + 1,
        )
        self.assertFalse(self.store.append(
            record_key="player_week:identity-invalidation",
            entity_type="player_week", league_id=self.league_id,
            source_record_id="identity-invalidation",
            observed_at="2025-09-01T00:00:00+00:00",
            retrieved_at="2025-09-01T00:00:00+00:00", provider="Sleeper",
            availability="available", confidence=100,
            calculation_method="provider_observation", schema_version="2.0",
            payload={"fantasy_points": 22.0}, season=2025, week=1,
            player_id="10213",
        ))
        self.assertEqual(self.store.dataset_version(self.league_id), changed)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"],
            computations + 1,
        )

    def test_semantic_generation_uses_only_bounded_metadata_queries(self) -> None:
        statements: list[str] = []
        original_connection = self.store.connection

        @contextmanager
        def traced_connection():
            with original_connection() as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        self.store._invalidate_dataset_version(self.league_id)
        with patch.object(self.store, "connection", traced_connection):
            version = self.store.dataset_version(self.league_id)
        self.assertTrue(version)
        semantic_queries = "\n".join(statements).casefold()
        self.assertNotIn("from historical_records", semantic_queries)
        self.assertNotIn("from player_identity", semantic_queries)
        self.assertNotIn("from data_quality_issues", semantic_queries)
        self.assertNotIn("count(", semantic_queries)
        self.assertNotIn("max(", semantic_queries)
        self.assertIn("database_metadata", semantic_queries)

    def test_domain_markers_advance_once_per_material_transaction(self) -> None:
        initial = self.store.semantic_generation_markers(self.league_id)
        records = [
            {
                "record_key": f"marker:{index}", "entity_type": "player_week",
                "league_id": self.league_id, "season": 2025, "week": 2,
                "player_id": str(index), "source_record_id": f"marker:{index}",
                "observed_at": "2025-09-08T00:00:00+00:00",
                "retrieved_at": "2025-09-08T00:00:00+00:00",
                "provider": "fixture", "availability": "available",
                "confidence": 100, "calculation_method": "fixture",
                "schema_version": "2.0", "payload": {"fantasy_points": index},
            }
            for index in range(8)
        ]
        self.assertEqual(self.store.append_many(records), (8, 0))
        changed = self.store.semantic_generation_markers(self.league_id)
        self.assertEqual(
            changed["historical_records"], initial["historical_records"] + 1,
        )
        self.assertEqual(self.store.append_many(records), (0, 8))
        self.assertEqual(
            self.store.semantic_generation_markers(self.league_id), changed,
        )

    def test_marker_rollback_and_restart_are_durable(self) -> None:
        initial = self.store.semantic_generation_markers(self.league_id)
        with self.assertRaisesRegex(RuntimeError, "controlled rollback"):
            with self.store.connection() as connection:
                self.store._advance_generation(
                    connection,
                    self.store._record_generation_key(self.league_id),
                )
                raise RuntimeError("controlled rollback")
        self.store._invalidate_dataset_version(self.league_id)
        self.assertEqual(
            self.store.semantic_generation_markers(self.league_id), initial,
        )
        restarted = HistoricalStore(self.store.path)
        self.assertEqual(
            restarted.semantic_generation_markers(self.league_id), initial,
        )

    def test_quality_and_identity_markers_ignore_unchanged_writes(self) -> None:
        initial = self.store.semantic_generation_markers(self.league_id)
        self.store.add_quality_issue(
            "marker-quality", "run", self.league_id, 2025,
            "warning", "fixture", "Fixture issue.",
        )
        quality = self.store.semantic_generation_markers(self.league_id)
        self.assertEqual(
            quality["quality_reconciliation"],
            initial["quality_reconciliation"] + 1,
        )
        self.store.add_quality_issue(
            "marker-quality", "run", self.league_id, 2025,
            "warning", "fixture", "Fixture issue.",
        )
        self.assertEqual(
            self.store.semantic_generation_markers(self.league_id), quality,
        )
        self.assertTrue(self.store.upsert_identity(
            "DTOS-P-marker", "Sleeper", "marker", "Marker", 100,
            "2026-01-01T00:00:00+00:00", {"position": "WR"},
        ))
        identity = self.store.semantic_generation_markers(self.league_id)
        self.assertEqual(
            identity["canonical_identities"],
            quality["canonical_identities"] + 1,
        )
        self.assertFalse(self.store.upsert_identity(
            "DTOS-P-marker", "Sleeper", "marker", "Marker", 100,
            "2026-01-01T00:00:00+00:00", {"position": "WR"},
        ))
        self.assertEqual(
            self.store.semantic_generation_markers(self.league_id), identity,
        )

    def test_search_routes_only_true_historical_queries_to_retained_aliases(self) -> None:
        with patch("src.core.asset_market.engine.historical_graph") as graph:
            self.assertEqual(
                self.market.search("Josh Allen")["results"][0]["asset_id"],
                "player:10213",
            )
            self.assertEqual(self.market.search("no-such-player")["count"], 0)
            self.assertEqual(
                self.market.search("Former Player")["results"][0]["asset_id"],
                "DTOS-P-99",
            )
            graph.assert_not_called()
        with patch.object(self.market._brain, "asset") as asset, patch.object(
            self.market._brain, "decision",
        ) as decision:
            self.market.search("QB")
            asset.assert_not_called()
            decision.assert_not_called()

    def test_request_layers_resolve_dataset_identity_once(self) -> None:
        with patch.object(
            self.store, "dataset_version",
            wraps=self.store.dataset_version,
        ) as version:
            self.market.search("Josh Allen")
            self.assertEqual(version.call_count, 1)
        with patch.object(
            self.store, "dataset_version",
            wraps=self.store.dataset_version,
        ) as version:
            self.market.detail("player:10213", 1)
            self.assertEqual(version.call_count, 1)

    def test_player_dossier_cache_is_single_flight_and_bounded(self) -> None:
        dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(
            self.store, self.league_id, self.data, dataset_version,
        )
        first = graph.player_dossier("10213")
        results: list[dict] = []
        threads = [threading.Thread(target=lambda: results.append(
            graph.player_dossier("10213")
        )) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(result == first for result in results))
        metrics = graph.query_metrics()
        self.assertEqual(metrics["player_summary_build_count"], 1)
        self.assertEqual(metrics["player_summary_cache_hits"], 6)
        self.assertLessEqual(
            metrics["player_summary_cache_entries"],
            metrics["player_summary_cache_limit"],
        )

    def test_player_dossier_cache_eviction_is_bounded_and_failures_are_not_cached(self) -> None:
        dataset_version = self.store.dataset_version(self.league_id)
        graph = historical_graph(
            self.store, self.league_id, self.data, dataset_version,
        )
        graph._player_dossiers.clear()
        with patch.object(
            graph, "_build_player_dossier",
            side_effect=lambda player_id, canonical_id: {
                "identity": canonical_id, "player_id": player_id,
            },
        ) as build:
            for player_id in range(130):
                graph.player_dossier(str(player_id))
            self.assertEqual(len(graph._player_dossiers), 128)
            retained = [key[-1] for key in graph._player_dossiers]
            self.assertNotIn("DTOS-P-0", retained)
            self.assertNotIn("DTOS-P-1", retained)
            self.assertEqual(retained[-1], "DTOS-P-129")
            self.assertEqual(build.call_count, 130)
        graph._player_dossiers.clear()
        with patch.object(
            graph, "_build_player_dossier",
            side_effect=RuntimeError("incomplete summary"),
        ):
            with self.assertRaisesRegex(RuntimeError, "incomplete summary"):
                graph.player_dossier("failed")
        self.assertFalse(any(key[-1] == "DTOS-P-failed" for key in graph._player_dossiers))

    def test_warm_market_reads_do_not_repeat_dataset_aggregate_queries(self) -> None:
        self.store.dataset_version(self.league_id)
        statements: list[str] = []
        original_connection = self.store.connection

        @contextmanager
        def traced_connection():
            with original_connection() as connection:
                connection.set_trace_callback(statements.append)
                yield connection

        with patch.object(self.store, "connection", traced_connection):
            for _ in range(5):
                self.market.search("QB")
                self.market.detail("player:10213", 1)
        aggregates = [
            statement for statement in statements
            if "coalesce(max(id)" in statement
            or "coalesce(max(rowid)" in statement
            or "SELECT issue_key, resolved" in statement
        ]
        self.assertEqual(aggregates, [])

    def test_dataset_identity_cache_is_cross_league_and_rollback_safe(self) -> None:
        first = self.store.dataset_version(self.league_id)
        other = self.store.dataset_version("league-2")
        computations = self.store.dataset_version_metrics()["computations"]
        with self.assertRaises(RuntimeError):
            with self.store.connection() as connection:
                connection.execute(
                    """INSERT INTO historical_records(
                    record_key,entity_type,league_id,source_record_id,
                    observed_at,retrieved_at,provider,availability,confidence,
                    calculation_method,schema_version,payload)
                    VALUES ('rolled-back','player_week',?,'rolled-back',
                    '2025-01-01','2025-01-01','fixture','available',100,
                    'fixture','2.0','{}')""",
                    (self.league_id,),
                )
                raise RuntimeError("rollback")
        self.assertEqual(self.store.dataset_version(self.league_id), first)
        self.assertEqual(self.store.dataset_version("league-2"), other)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self._append(
            "player_week", "cross-league-change", "10213",
            {"fantasy_points": 23.0},
        )
        self.assertEqual(self.store.dataset_version("league-2"), other)
        self.assertEqual(
            self.store.dataset_version_metrics()["computations"], computations,
        )
        self.assertNotEqual(self.store.dataset_version(self.league_id), first)


if __name__ == "__main__":
    unittest.main()
