"""Durable admission, component sizing, and artifact hygiene regressions."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.league_runtime import create_league_runtime_router
from src.core.asset_market.engine import AssetMarketCache
from src.core.asset_market.read_model import build_read_model, memory_admission
from src.core.asset_market.resource_diagnostics import (
    GLOBAL_LIMIT, PER_LEAGUE_LIMIT, ResourceDiagnostics, runtime_component_sizes,
)
from src.core.historical_memory.store import HistoricalStore
from src.core.league_runtime.manager import LeagueRuntime
from src.core.league_runtime.manager import LeagueRuntimeManager


def _snapshot(*, current: int = 100, inactive: int = 25, oom: int = 0) -> dict:
    return {
        "cgroup_current_bytes": current,
        "cgroup_limit_bytes": 2 * 1024**3,
        "cgroup_inactive_file_bytes": inactive,
        "cgroup_memory_events": {"oom": oom, "oom_kill": 0, "oom_group_kill": 0},
    }


class ResourceDiagnosticsTests(unittest.TestCase):
    def test_resource_health_is_bounded_and_measurement_is_explicit(self) -> None:
        calls = {"health": 0, "measure": 0}

        def health() -> dict:
            calls["health"] += 1
            return {"status": "healthy", "resident_runtime_count": 1}

        def measure() -> dict:
            calls["measure"] += 1
            return {"status": "complete", "runtimes": []}

        app = FastAPI()
        app.include_router(create_league_runtime_router(
            manager=LeagueRuntimeManager(), resource_health=health,
            resource_measurement=measure,
        ))
        client = TestClient(app)
        self.assertEqual(client.get("/api/leagues/resources").json()["status"], "healthy")
        self.assertEqual(calls, {"health": 1, "measure": 0})
        self.assertEqual(
            client.post("/api/leagues/resources/measure").json()["status"],
            "complete",
        )
        self.assertEqual(calls, {"health": 1, "measure": 1})

    def test_admission_history_is_durable_bounded_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diagnostics = ResourceDiagnostics(root)
            admitted = memory_admission(_snapshot(), estimate=10)
            for index in range(GLOBAL_LIMIT + 25):
                diagnostics.record("0", "semantic_preparation", admitted)
            restarted = ResourceDiagnostics(root).health()
            self.assertEqual(restarted["count"], PER_LEAGUE_LIMIT)
            payload = (root / ".asset-market-admission-history.json").read_text()
            self.assertNotIn('"league":"0"', payload)

    def test_oom_rejection_reason_is_explicit_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            diagnostics = ResourceDiagnostics(Path(directory))
            admission = memory_admission(
                _snapshot(oom=2), baseline_events={"oom": 1},
            )
            diagnostics.record("123", "model_publication", admission)
            rejection = diagnostics.health()["latest_rejection"]
            self.assertEqual(rejection["reason"], "oom_event_advanced")
            self.assertFalse(rejection["admitted"])

    def test_high_file_cache_records_unchanged_admission(self) -> None:
        snapshot = _snapshot(current=1_798_828_032, inactive=1_527_832_576)
        admission = memory_admission(snapshot, estimate=100_663_296)
        with tempfile.TemporaryDirectory() as directory:
            row = ResourceDiagnostics(Path(directory)).record(
                "123", "semantic_preparation", admission,
            )
        self.assertTrue(row["admitted"])
        self.assertEqual(row["memory_current"], 1_798_828_032)
        self.assertEqual(row["inactive_file"], 1_527_832_576)

    def test_component_sizing_is_non_mutating_and_handles_missing_contexts(self) -> None:
        runtime = LeagueRuntime("123")
        runtime.state["data"] = {"players": {"1": {"full_name": "A"}}}
        before = repr(runtime.state)
        measured = runtime_component_sizes(runtime)
        self.assertEqual(repr(runtime.state), before)
        self.assertEqual(measured["league"], "a665a45920422f9d")
        self.assertGreater(measured["components"]["player_catalog"]["bytes"], 0)
        self.assertEqual(
            measured["components"]["player_catalog"]["classification"],
            "candidate-for-sharing",
        )


class ArtifactPruningTests(unittest.TestCase):
    def _artifact(self, store: HistoricalStore, league: str, generation: str) -> Path:
        path = AssetMarketCache.artifact_path(store, generation)
        build_read_model(
            path, generation, iter(()), {"league_id": league, "complete": True},
        )
        return path

    def test_pruning_keeps_one_current_artifact_per_league(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoricalStore(Path(directory) / "history.sqlite3")
            a_old = self._artifact(store, "100", "a" * 64)
            a_current = self._artifact(store, "100", "b" * 64)
            b_old = self._artifact(store, "200", "c" * 64)
            b_current = self._artifact(store, "200", "d" * 64)
            AssetMarketCache._publish_artifact_manifest(store, a_old, "a" * 64)
            AssetMarketCache._publish_artifact_manifest(store, a_current, "b" * 64, "100")
            AssetMarketCache._publish_artifact_manifest(store, b_current, "d" * 64, "200")
            result = AssetMarketCache.prune_stale_artifacts(store)
            self.assertFalse(a_old.exists())
            self.assertFalse(b_old.exists())
            self.assertTrue(a_current.exists())
            self.assertTrue(b_current.exists())
            self.assertEqual(result["active_count"], 2)
            self.assertEqual(result["stale_count"], 0)

    def test_cleanup_failure_is_nonfatal_and_preserves_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoricalStore(Path(directory) / "history.sqlite3")
            current = self._artifact(store, "100", "e" * 64)
            cache = AssetMarketCache()
            with patch.object(
                cache, "prune_stale_artifacts", side_effect=OSError("denied"),
            ):
                result = cache.cleanup_artifacts(store, protected=(current,))
            self.assertTrue(current.exists())
            self.assertEqual(result["failures"], 1)
            self.assertEqual(cache.artifact_cleanup_failures, 1)


if __name__ == "__main__":
    unittest.main()
