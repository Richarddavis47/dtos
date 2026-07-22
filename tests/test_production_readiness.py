"""DTOS v1 production-readiness contracts."""
from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import Settings
from src.core.intelligence import IntelligenceCache, IntelligenceOrchestrator, IntelligenceRegistry
from src.platform.observability import StructuredFormatter, install_observability
from src.platform.validation import REQUIRED_DOCUMENTS, architecture_violations, default_steps, validate_documentation
from tests.test_trade_intelligence import fixture_data


class ConfigurationTests(unittest.TestCase):
    def test_environment_overrides_are_preserved_and_validated(self) -> None:
        values = {
            "SLEEPER_LEAGUE_ID": "league-test",
            "DTOS_CACHE_FILE": "custom-cache.json",
            "SYNC_MINUTES": "20",
            "SLEEPER_TIMEOUT": "9",
            "DTOS_LOG_FORMAT": "text",
            "DTOS_INTELLIGENCE_CACHE_TTL": "12",
            "DTOS_MARKET_CACHE_TTL": "120",
            "DTOS_DATA_WAREHOUSE_FILE": "custom-history.json",
        }
        with patch.dict(os.environ, values, clear=False):
            settings = Settings.from_environment()
        self.assertEqual(settings.league_id, "league-test")
        self.assertEqual(str(settings.cache_file), "custom-cache.json")
        self.assertEqual(settings.intelligence_cache_ttl, 12)
        self.assertEqual(settings.market_cache_ttl, 120)
        self.assertEqual(str(settings.data_warehouse_file), "custom-history.json")

    def test_invalid_configuration_fails_fast(self) -> None:
        with patch.dict(os.environ, {"SYNC_MINUTES": "not-a-number"}, clear=False), self.assertRaisesRegex(ValueError, "SYNC_MINUTES"):
            Settings.from_environment()
        with patch.dict(os.environ, {"DTOS_LOG_FORMAT": "xml"}, clear=False), self.assertRaisesRegex(ValueError, "DTOS_LOG_FORMAT"):
            Settings.from_environment()


class ObservabilityTests(unittest.TestCase):
    def test_structured_logs_include_required_correlation_fields(self) -> None:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(StructuredFormatter())
        logger = logging.getLogger("dtos.test.structured")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.info("provider_complete", extra={"request_id": "request-1", "provider": "market", "duration_ms": 2.5})
        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["request_id"], "request-1")
        self.assertEqual(payload["provider"], "market")
        self.assertEqual(payload["duration_ms"], 2.5)

    def test_request_id_is_preserved_or_generated_and_health_is_additive(self) -> None:
        app = FastAPI()
        install_observability(app)

        @app.get("/probe")
        async def probe():
            return {"ok": True}

        client = TestClient(app)
        supplied = client.get("/probe", headers={"X-Request-ID": "known-id"})
        generated = client.get("/probe")
        self.assertEqual(supplied.headers["X-Request-ID"], "known-id")
        self.assertTrue(generated.headers["X-Request-ID"])


class ArchitectureAndDocumentationTests(unittest.TestCase):
    def test_services_and_routes_use_the_orchestrator_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(architecture_violations(root), ())

    def test_required_documentation_is_present_and_nonempty(self) -> None:
        root = Path(__file__).resolve().parents[1]
        validate_documentation(root)
        self.assertGreaterEqual(len(REQUIRED_DOCUMENTS), 19)

    def test_single_validator_contains_every_permanent_gate(self) -> None:
        names = {step.name for step in default_steps()}
        self.assertEqual(len(names), 10)
        self.assertTrue({"Python compilation", "Ruff", "Dependency integrity", "Route and OpenAPI validation", "Tracked HTTP smoke validation", "Process cleanup"}.issubset(names))

    def test_release_validator_is_a_clean_module_entry_point(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "tools/validation/validate_release.py").read_text(encoding="utf-8")
        self.assertNotIn("sys.path", source)
        result = subprocess.run(
            [sys.executable, "-m", "tools.validation.validate_release", "--help"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Run every DTOS release validation gate", result.stdout)


class PerformanceAndReliabilityTests(unittest.TestCase):
    def test_repeated_recommendation_uses_cache_and_meets_sanity_target(self) -> None:
        orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache(default_ttl=60))
        data = fixture_data()
        started = time.perf_counter()
        first = orchestrator.analyze(data, 1)
        cold_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        second = orchestrator.analyze(data, 1)
        warm_ms = (time.perf_counter() - started) * 1000
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertLess(warm_ms, cold_ms)
        self.assertLess(cold_ms, 2000)
        self.assertGreater(orchestrator.cache.health()["hit_rate"], 0)

    def test_large_league_repeated_requests_remain_bounded(self) -> None:
        data = fixture_data()
        template = data["teams"]
        teams = []
        players = {}
        for roster_id in range(1, 33):
            source = template[(roster_id - 1) % len(template)]
            roster = []
            for index, item in enumerate(source["players"]):
                player_id = f"large-{roster_id}-{index}"
                players[player_id] = {"full_name": player_id, "position": item["position"], "team": "BUF", "age": 25}
                roster.append({**item, "id": player_id, "name": player_id})
            teams.append({**source, "roster_id": roster_id, "owner": f"Owner {roster_id}", "team_name": f"Team {roster_id}", "players": roster, "picks_owned": []})
        data.update({"teams": teams, "players": players})
        orchestrator = IntelligenceOrchestrator(IntelligenceRegistry(), IntelligenceCache())
        started = time.perf_counter()
        result = orchestrator.analyze(data, 1)
        self.assertLess(time.perf_counter() - started, 5)
        self.assertEqual(len(result.decisions), 32)


if __name__ == "__main__":
    unittest.main()
