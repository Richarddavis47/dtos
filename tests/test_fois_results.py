"""Production FOIS Results and competitive-cycle regression coverage."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.fois import create_fois_router
from src.core.fois.cycles import CompetitiveCycleAnalyzer
from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult
from src.core.fois.history import load_results_history
from src.core.fois.repository import FOISRepository
from src.core.fois.service import FOISService
from src.core.historical_memory.store import HistoricalStore


def season(
    year: int,
    *,
    wins: int = 8,
    losses: int = 6,
    finish: int = 4,
    playoff: bool = True,
    final_four: bool = False,
    final: bool = False,
    title: bool = False,
    rebuilding: bool = False,
    complete: bool = True,
) -> SeasonResult:
    return SeasonResult(
        year,
        wins,
        losses,
        finish,
        "1" if title else "2" if final else "4" if final_four else "6" if playoff else None,
        title,
        rebuilding,
        10,
        playoff,
        final_four or final or title,
        final or title,
        wins,
        losses,
        complete,
    )


def score(rows: tuple[SeasonResult, ...], **kwargs):
    facts = FOISFacts(
        "league",
        "league:franchise:1",
        "owner",
        rows,
        expected_seasons=kwargs.get("expected_seasons", len(rows)),
        ownership_changes=kwargs.get("ownership_changes", 0),
    )
    result = FOISEngine().evaluate(
        facts,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    return next(
        category
        for category in result.category_scores
        if category.category_key == "results"
    )


class FOISResultsTests(unittest.TestCase):
    def test_representative_results_scenarios_are_explainable(self) -> None:
        scenarios = {
            "multiple_championships": tuple(
                season(2017 + i, title=i in {2, 6}, final_four=True)
                for i in range(9)
            ),
            "sustained_no_titles": tuple(
                season(2018 + i, final_four=i % 2 == 0) for i in range(8)
            ),
            "title_then_collapse": (
                season(2020, title=True),
                season(2021, wins=3, losses=11, finish=10, playoff=False),
                season(2022, wins=2, losses=12, finish=10, playoff=False),
            ),
            "two_year_rebuild": (
                season(2020, wins=3, losses=11, finish=10, playoff=False, rebuilding=True),
                season(2021, wins=4, losses=10, finish=9, playoff=False, rebuilding=True),
                season(2022, final=True),
            ),
            "five_year_rebuild": tuple(
                season(2019 + i, wins=3, losses=11, finish=10, playoff=False, rebuilding=True)
                for i in range(5)
            ),
            "mediocrity": tuple(
                season(2019 + i, wins=7, losses=7, finish=6, playoff=False)
                for i in range(6)
            ),
            "elite_run": tuple(
                season(2019 + i, wins=11, losses=3, finish=1, final_four=True, title=i == 2)
                for i in range(5)
            ),
            "lucky_title": (
                season(2021, wins=6, losses=8, finish=7, title=True),
                season(2022, wins=4, losses=10, finish=9, playoff=False),
                season(2023, wins=5, losses=9, finish=8, playoff=False),
            ),
            "ownership_transfer": tuple(season(2020 + i) for i in range(5)),
            "missing_history": (
                season(2022),
                season(2024, complete=False),
            ),
        }
        for name, rows in scenarios.items():
            with self.subTest(name=name):
                result = score(
                    rows,
                    ownership_changes=1 if name == "ownership_transfer" else 0,
                    expected_seasons=5 if name == "missing_history" else len(rows),
                )
                self.assertIsNotNone(result.normalized_score)
                self.assertTrue(result.explanation)
                self.assertIsNotNone(result.details)
                self.assertIn("timeline", result.details)
                self.assertIn("competitive_cycles", result.details)

    def test_titles_do_not_dominate_results_category(self) -> None:
        result = score((season(2021, title=True), season(2022, playoff=False)))
        title = next(
            metric for metric in result.metric_scores
            if metric.metric_key == "championships"
        )
        self.assertEqual(title.metric_weight, 10)
        self.assertLess(title.weighted_contribution, result.normalized_score)

    def test_all_results_metrics_are_production_weighted(self) -> None:
        rows = tuple(
            season(2015 + index, title=index in {3, 8}, final_four=True)
            for index in range(10)
        )
        result = score(rows)
        self.assertEqual(len(result.metric_scores), 15)
        self.assertEqual(
            sum(metric.metric_weight for metric in result.metric_scores),
            100,
        )
        self.assertTrue(
            all(
                metric.status.value in {"active", "insufficient_data"}
                for metric in result.metric_scores
            )
        )

    def test_actual_matchup_record_drives_win_percentage(self) -> None:
        row = season(2024, wins=10, losses=4)
        row = SeasonResult(
            **{
                **row.__dict__,
                "matchup_wins": 7,
                "matchup_losses": 7,
            }
        )
        result = score((row,))
        metric = next(
            metric for metric in result.metric_scores
            if metric.metric_key == "regular_season_winning_percentage"
        )
        self.assertEqual(metric.raw_value, .5)
        self.assertIn("7-7", metric.explanation)

    def test_two_year_rebuild_and_five_year_rebuild_are_distinct(self) -> None:
        short = score((
            season(2020, rebuilding=True, playoff=False),
            season(2021, rebuilding=True, playoff=False),
            season(2022, final=True),
        ))
        long = score(tuple(
            season(2018 + i, rebuilding=True, playoff=False)
            for i in range(5)
        ))
        def metric(result):
            return next(
                row for row in result.metric_scores
                if row.metric_key == "rebuild_duration"
            )
        self.assertEqual(metric(short).normalized_score, 90)
        self.assertLess(metric(long).normalized_score, metric(short).normalized_score)

    def test_reload_timing_and_contention_window_detection(self) -> None:
        rows = (
            season(2019, final_four=True),
            season(2020, rebuilding=True, playoff=False),
            season(2021, rebuilding=True, playoff=False),
            season(2022, final=True),
            season(2023, title=True),
        )
        analysis = CompetitiveCycleAnalyzer().analyze(rows)
        contention = [
            cycle for cycle in analysis.competitive_cycles
            if cycle.cycle_type == "contention"
        ]
        self.assertEqual(len(contention), 2)
        self.assertEqual(contention[-1].reload_time, 2)
        self.assertEqual(contention[-1].duration, 2)
        self.assertEqual(contention[-1].peak_years, (2023,))

    def test_historical_windows_are_deterministic(self) -> None:
        rows = tuple(season(2013 + i) for i in range(12))
        first = CompetitiveCycleAnalyzer().analyze(rows)
        second = CompetitiveCycleAnalyzer().analyze(rows)
        self.assertEqual(first, second)
        windows = {window.key: window for window in first.historical_windows}
        self.assertEqual(len(windows["full_history"].seasons), 12)
        self.assertEqual(len(windows["trailing_10"].seasons), 10)
        self.assertEqual(len(windows["trailing_5"].seasons), 5)
        self.assertEqual(len(windows["trailing_3"].seasons), 3)
        self.assertIn("current_cycle", windows)

    def test_missing_history_and_ownership_change_reduce_confidence_not_score(self) -> None:
        rows = tuple(season(2020 + i) for i in range(3))
        complete = score(rows, expected_seasons=3)
        incomplete = score(rows, expected_seasons=6, ownership_changes=1)
        self.assertEqual(complete.normalized_score, incomplete.normalized_score)
        self.assertLess(incomplete.confidence, complete.confidence)
        self.assertLess(incomplete.completeness, complete.completeness)

    def test_results_analysis_persists_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = FOISRepository(Path(directory) / "fois.sqlite3")
            evaluated = FOISEngine().evaluate(
                FOISFacts(
                    "league",
                    "league:franchise:1",
                    "owner",
                    tuple(season(2020 + i) for i in range(4)),
                ),
                generated_at="2026-01-01T00:00:00+00:00",
            )
            self.assertTrue(repository.save(evaluated, "history-a"))
            self.assertFalse(repository.save(evaluated, "history-a"))
            restored = repository.get(
                "league",
                "league:franchise:1",
                evaluated.model_version,
            )
            results = next(
                row for row in restored.category_scores
                if row.category_key == "results"
            )
            self.assertTrue(results.details["timeline"])
            self.assertEqual(repository.count(), 1)

    def test_historical_store_adapter_uses_canonical_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoricalStore(Path(directory) / "history.sqlite3")
            common = {
                "league_id": "league",
                "season": 2024,
                "week": None,
                "franchise_id": None,
                "player_id": None,
                "observed_at": "2025-01-01",
                "retrieved_at": "2025-01-01",
                "provider": "Sleeper",
                "availability": "observed",
                "confidence": 100,
                "calculation_method": "test",
                "derived": False,
                "schema_version": "1.0",
            }
            def append(key, entity, source, payload, **dimensions):
                store.append(
                    record_key=key,
                    entity_type=entity,
                    source_record_id=source,
                    payload=payload,
                    **{**common, **dimensions},
                )
            append("season", "league_season", "2024", {"total_rosters": 10})
            append(
                "standing",
                "season_standing",
                "1",
                {"roster_id": 1, "wins": 9, "losses": 5, "rank": 2},
                franchise_id="league:franchise:1",
            )
            append(
                "identity",
                "franchise_identity",
                "1",
                {"sleeper_roster_id": "1", "owner_id": "owner-a"},
                franchise_id="league:franchise:1",
            )
            append(
                "playoff",
                "playoff_result",
                "placements",
                {
                    "placements": {"1": 1},
                    "champion_roster_id": 1,
                    "final_four_roster_ids": [1],
                },
            )
            append(
                "matchup",
                "matchup",
                "1:1",
                {
                    "winner": 1,
                    "loser": 2,
                    "postseason_context": False,
                },
                week=1,
            )
            history = load_results_history(store, "league")
            result = history["1"]["seasons"][0]
            self.assertTrue(result["championship"])
            self.assertEqual(result["matchup_wins"], 1)
            self.assertEqual(result["league_size"], 10)

    def test_results_history_ignores_standing_without_roster_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = HistoricalStore(Path(directory) / "history.sqlite3")
            store.append(
                record_key="invalid-standing",
                entity_type="season_standing",
                league_id="league",
                source_record_id="invalid",
                observed_at="2025-01-01",
                retrieved_at="2025-01-01",
                provider="SanitizedFixture",
                availability="available",
                confidence=100,
                calculation_method="fixture",
                schema_version="1.0",
                payload={"fixture": True, "value": 1},
                season=2024,
            )

            self.assertEqual(load_results_history(store, "league"), {})

    def test_results_api_exposes_timeline_cycles_and_explanations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = FOISService(
                FOISRepository(Path(directory) / "fois.sqlite3")
            )
            data = {
                "league": {"league_id": "league"},
                "teams": [{"roster_id": 1, "owner_id": "owner"}],
                "fois_history": {
                    "1": {
                        "seasons": [
                            row.__dict__
                            for row in (
                                season(2022, rebuilding=True, playoff=False),
                                season(2023, final=True),
                                season(2024, title=True),
                            )
                        ]
                    }
                },
            }
            app = FastAPI()
            app.include_router(
                create_fois_router(service=service, require_data=lambda: data)
            )
            with patch.dict(os.environ, {"DTOS_FOIS_ENABLED": "1"}):
                client = TestClient(app)
                calculated = client.post("/api/fois/leagues/league/calculate")
                self.assertEqual(calculated.status_code, 200)
                detail = client.get(
                    "/api/fois/leagues/league/franchises/"
                    "league:franchise:1/results"
                )
            self.assertEqual(detail.status_code, 200)
            payload = detail.json()
            self.assertTrue(payload["details"]["timeline"])
            self.assertTrue(payload["details"]["competitive_cycles"])
            self.assertTrue(payload["explanation"])
            self.assertIn("strengths", payload)
            self.assertIn("weaknesses", payload)


if __name__ == "__main__":
    unittest.main()
