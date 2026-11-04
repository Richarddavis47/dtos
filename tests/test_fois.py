"""FOIS foundation contracts, scoring, persistence, and API tests."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from src.core.fois.configuration import (
    DEFAULT_FOIS_CONFIGURATION,
    validate_configuration,
)
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult, TradeFact
from src.core.fois.identity import identity_from_team
from src.core.fois.models import MetricStatus
from src.core.fois.scoring import calibrate_process_score
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService


def facts(
    *,
    seasons: int = 5,
    rebuilds: int = 0,
    trades: int = 3,
) -> FOISFacts:
    season_rows = tuple(
        SeasonResult(
            2020 + index,
            8,
            6,
            1 if index == seasons - 1 else 4,
            "champion" if index == seasons - 1 else "playoffs",
            index == seasons - 1,
            index < rebuilds,
        )
        for index in range(seasons)
    )
    trade_rows = tuple(
        TradeFact(
            f"trade-{index}",
            2024,
            True,
            15 if index == 0 else 0,
            8 if index == 0 else 0,
        )
        for index in range(trades)
    )
    return FOISFacts(
        "league-1",
        "league-1:franchise:1",
        "owner-1",
        season_rows,
        trade_rows,
        roster_metrics={"starting_lineup_strength": 82, "roster_flexibility": 74},
        league_settings={"roster_positions": ["QB", "SUPER_FLEX"]},
    )


class FOISFoundationTests(unittest.TestCase):
    def test_neutral_process_evidence_is_not_graded_as_failure(self) -> None:
        self.assertEqual(calibrate_process_score(50), 70)

    def test_confidence_does_not_reduce_executive_score(self) -> None:
        high = FOISEngine().evaluate(facts(seasons=10))
        low = FOISEngine().evaluate(facts(seasons=1))
        self.assertLess(low.confidence, high.confidence)
        self.assertGreater(low.overall_score, 0)
        self.assertNotEqual(low.overall_score, low.confidence)
    def test_configuration_weights_are_versioned_and_total_one_hundred(self) -> None:
        self.assertEqual(sum(DEFAULT_FOIS_CONFIGURATION.category_weights.values()), 100)
        invalid = replace(
            DEFAULT_FOIS_CONFIGURATION,
            category_weights={"results": 99},
        )
        with self.assertRaisesRegex(ValueError, "100"):
            validate_configuration(invalid)

    def test_missing_metrics_are_explicit_and_never_zero(self) -> None:
        score = FOISEngine().evaluate(facts(), generated_at="2026-01-01T00:00:00+00:00")
        draft = next(
            category
            for category in score.category_scores
            if category.category_key == "drafting_talent_evaluation"
        )
        self.assertIsNone(draft.normalized_score)
        self.assertTrue(all(metric.raw_value is None for metric in draft.metric_scores))
        self.assertTrue(
            all(
                metric.status in {
                    MetricStatus.UNAVAILABLE,
                    MetricStatus.INSUFFICIENT_DATA,
                    MetricStatus.DISABLED,
                }
                for metric in draft.metric_scores
            )
        )

    def test_two_year_rebuild_is_not_penalized_like_extended_rebuild(self) -> None:
        short = FOISEngine().evaluate(facts(rebuilds=2))
        long = FOISEngine().evaluate(facts(rebuilds=4))
        def rebuild(score):
            return next(
                metric
                for category in score.category_scores
                for metric in category.metric_scores
                if metric.metric_key == "rebuild_duration"
            )
        self.assertGreater(rebuild(short).normalized_score, rebuild(long).normalized_score)
        self.assertIn("productive-cycle", rebuild(short).explanation)

    def test_justified_overpay_is_explainable_and_positive(self) -> None:
        score = FOISEngine().evaluate(facts())
        metric = next(
            metric
            for category in score.category_scores
            for metric in category.metric_scores
            if metric.metric_key == "overpay_efficiency"
        )
        self.assertEqual(metric.normalized_score, 85)
        self.assertIn("20%", metric.explanation)
        self.assertIn("championship", metric.explanation)

    def test_short_history_reduces_confidence_and_marks_provisional(self) -> None:
        one = FOISEngine().evaluate(facts(seasons=1))
        ten = FOISEngine().evaluate(facts(seasons=10))
        self.assertTrue(one.provisional)
        self.assertLess(one.confidence, ten.confidence)

    def test_identity_keeps_owner_and_franchise_distinct(self) -> None:
        identity = identity_from_team(
            "league-1",
            {"roster_id": 7, "owner_id": "owner-z", "owner": "Zach", "team_name": "Orbit"},
        )
        self.assertEqual(identity.owner_name, "Zach")
        self.assertEqual(identity.franchise_name, "Orbit")
        self.assertNotEqual(identity.owner_id, identity.franchise_id)

    def test_representative_fixture_set_has_ten_scenarios(self) -> None:
        path = Path(__file__).parent / "fixtures" / "fois_scenarios_v160.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 10)
        self.assertEqual(len({row["name"] for row in rows}), 10)

    def test_repository_is_idempotent_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            score = FOISEngine().evaluate(facts(), generated_at="2026-01-01T00:00:00+00:00")
            self.assertTrue(repository.save(score, "same"))
            self.assertFalse(repository.save(score, "same"))
            self.assertEqual(repository.count(), 1)
            self.assertEqual(
                repository.get(score.league_id, score.franchise_id, score.model_version),
                score,
            )

    def test_disabled_service_does_not_run_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "fois.sqlite3"
            service = FOISService(
                repository_factory=lambda: FOISRepository(database)
            )
            with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "0"}), patch.object(
                service.engine, "evaluate"
            ) as evaluate:
                result = asyncio.run(service.generate({"teams": [{"roster_id": 1}]}))
            self.assertEqual(result, ())
            self.assertFalse(database.exists())
            evaluate.assert_not_called()

    def test_generation_uses_worker_thread(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(FOISRepository(Path(directory) / "fois.sqlite3"))
            payload = {
                "league": {"league_id": "league-1"},
                "teams": [{"roster_id": 1, "owner_id": "owner-1"}],
                "fois_history": {},
            }
            real_to_thread = asyncio.to_thread
            with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}), patch(
                "src.core.fois.service.asyncio.to_thread",
                wraps=real_to_thread,
            ) as to_thread:
                asyncio.run(service.generate(payload))
            self.assertEqual(to_thread.call_count, 2)
            self.assertEqual(to_thread.call_args_list[0].args[0], service._generate_sync)
            self.assertEqual(
                to_thread.call_args_list[1].args[0],
                service.repository.canonical_health,
            )

    def test_api_is_feature_flagged_and_status_is_memory_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(FOISRepository(Path(directory) / "fois.sqlite3"))
            app = FastAPI()
            app.include_router(
                create_fois_router(service=service, require_data=lambda: {})
            )
            with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "0"}):
                client = TestClient(app)
                self.assertEqual(client.get("/api/fois/status").status_code, 200)
                self.assertFalse(client.get("/api/fois/status").json()["enabled"])
                self.assertEqual(client.get("/api/fois/model").status_code, 404)


if __name__ == "__main__":
    unittest.main()
