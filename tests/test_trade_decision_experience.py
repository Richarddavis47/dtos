"""Actual prepared producers and evaluator; decision display cannot alter judgment."""

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from services.trade_calculator import balance_trade_market
from services.trade_intelligence import evaluate_trade_request
from tests import test_capital_strategy_reconciliation as capital


class TradeDecisionExperienceTests(unittest.TestCase):
    def setUp(self):
        self.f = capital.CapitalStrategyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        self.payload = dict(
            active_roster_id=1,
            partner_roster_id=2,
            assets_sent=["a", "2028-R1-3"],
            assets_received=["c"],
        )

    def evaluate(self, **updates):
        return evaluate_trade_request(
            self.data, {**self.payload, **updates}, projection_reader=self.f.reader
        )

    def test_unresolved_strategy_names_only_actual_blocker_and_keeps_numeric_facts(
        self,
    ):
        for team in self.data["teams"]:
            team.pop("strategy", None)
        row = self.evaluate()
        e = row["evaluation"]
        self.assertIsNone(e["recommendation"])
        self.assertEqual(e["market_evidence"]["availability"], "full")
        decision = e["decision_context"]
        self.assertEqual(decision["strategy"]["state"], "unresolved")
        self.assertTrue(decision["strategy"]["selection_required"])
        self.assertIn("Choose", decision["blocker"])
        self.assertNotIn("Market evidence is unavailable", decision["blocker"])
        self.assertIsNotNone(decision["lineup"]["delta"])

    def test_explicit_strategy_changes_interpretation_never_prices_or_lineup(self):
        win = self.evaluate(strategy="WIN NOW")["evaluation"]
        rebuild = self.evaluate(strategy="REBUILD")["evaluation"]
        self.assertEqual(win["market_evidence"], rebuild["market_evidence"])
        self.assertEqual(win["multi_horizon_impact"], rebuild["multi_horizon_impact"])
        self.assertEqual(win["decision_context"]["strategy"]["resolved"], "WIN NOW")
        self.assertEqual(
            win["decision_context"]["strategy"]["source"], "explicit_manager"
        )

    def test_selected_player_facts_reuse_compatible_published_sleeper_projection(self):
        row = self.evaluate(strategy="RETOOL")
        facts = row["proposal_presentation"]["send"][0]["player_facts"]
        self.assertEqual(facts["player_id"], "a")
        self.assertEqual(facts["projection"]["value"], self.f.points["a"])
        self.assertEqual(facts["projection"]["week"], 2)
        self.assertEqual(facts["market_rank"]["label"], "Market positional rank")
        self.assertIsNone(facts["season_fantasy_points_rank"])
        self.assertIsNone(facts["points_per_game_rank"])
        self.assertIsNone(facts["production"]["points_per_game"])

    def test_balance_primary_options_keep_original_incoming_target(self):
        self.f.prices(a=611, b=300, c=929, d=610, e=300, f=650)
        before = copy.deepcopy(self.data)
        with patch(
            "services.trade_intelligence._trade_projection_service",
            return_value=self.f.reader,
        ):
            result = balance_trade_market(
                self.data,
                {
                    **self.payload,
                    "strategy": "RETOOL",
                    "assets_sent": ["a"],
                    "assets_received": ["c"],
                },
            )
        self.assertTrue(result["results"])
        self.assertTrue(
            all("c" in row["proposal"]["assets_received"] for row in result["results"])
        )
        self.assertEqual(self.data, before)
        self.assertTrue(result["preview_only"])

    def test_prepared_actual_production_keeps_sample_and_scoring_not_full_season_rank(
        self,
    ):
        from services.player_evidence import prepare_player_production
        from src.core.data_platform.global_evidence import (
            GlobalEvidenceStore,
            GlobalFact,
        )

        path = Path(self.f.tmp.name) / "actual.sqlite3"
        store = GlobalEvidenceStore(path, reserve_bytes=0)
        store.publish(
            [
                GlobalFact(
                    "production",
                    "sleeper:a",
                    "nflverse",
                    "game:a",
                    "2026-09-01T00:00:00Z",
                    None,
                    {"pass_yd": 18.26, "season_type": "REG"},
                    season=2026,
                    week=1,
                )
            ],
            retrieved_at="2026-09-02T00:00:00Z",
        )
        self.data["canonical_player_production"] = prepare_player_production(
            self.data,
            expected_league_id="league-1",
            as_of="2026-10-15T00:00:00Z",
            path=path,
        )
        row = self.evaluate(strategy="WIN NOW")
        facts = row["evaluation"]["player_facts"]["a"]
        self.assertEqual(facts["production"]["points_per_game"], 18.26)
        self.assertEqual(facts["production"]["sample_games"], 1)
        self.assertIsNone(facts["season_fantasy_points_rank"])
        self.assertNotEqual(
            facts["production"]["points_per_game"],
            row["evaluation"]["decision_context"]["lineup"]["delta"],
        )
        self.assertIn("Actual production:", row["evaluation"]["explanation_html"])
        from services.trade_decision import selected_player_facts
        from services.trade_intelligence import build_trade_workspace

        workspace = build_trade_workspace(self.data, 1, market_only=True)
        for field, bad in [
            ("league_id", "foreign"),
            ("season", 2025),
            ("scoring_fingerprint", "foreign"),
        ]:
            original = self.data["canonical_player_production"][field]
            self.data["canonical_player_production"][field] = bad
            facts = selected_player_facts(
                self.data, workspace["pools"][1], self.f.reader
            )
            self.assertIsNone(facts["a"]["production"]["points_per_game"])
            self.data["canonical_player_production"][field] = original

    def test_valid_zero_projection_and_missing_scoring_are_distinct(self):
        self.f.points["a"] = 0
        self.f.publish()
        facts = self.evaluate(strategy="RETOOL")["evaluation"]["player_facts"]["a"]
        self.assertEqual(facts["projection"]["value"], 0)
        self.assertEqual(facts["projection"]["availability"], "available")
        self.data["league"].pop("scoring_settings")
        facts = self.evaluate(strategy="RETOOL")["evaluation"]["player_facts"]["a"]
        self.assertIsNone(facts["projection"]["value"])
        self.assertIsNone(facts["production"]["points_per_game"])
        self.assertIsNone(
            self.evaluate(strategy="RETOOL")["evaluation"]["decision_context"][
                "lineup"
            ]["delta"]
        )

    def test_display_is_read_only_and_unfavorable_verdict_stays_unfavorable(self):
        self.f.prices(a=900, c=100)
        before = copy.deepcopy(self.data)
        report = self.evaluate(strategy="WIN NOW")["evaluation"]
        self.assertIn(report["recommendation"], ("REJECT", "NOT WORTH IT"))
        self.assertEqual(
            report["decision_context"]["verdict"], report["recommendation"]
        )
        self.assertIn(report["recommendation"], report["explanation_html"])
        self.assertEqual(self.data, before)
        self.assertNotIn("will accept", report["explanation_html"].lower())

    def test_unresolved_strategy_with_other_missing_evidence_lists_both(self):
        for team in self.data["teams"]:
            team.pop("strategy", None)
        self.data["league"]["settings"].pop("playoff_week_start")
        report = self.evaluate()["evaluation"]
        self.assertIn("Choose", report["decision_context"]["blocker"])
        self.assertIn("coverage", report["decision_context"]["blocker"])
        self.assertEqual(report["market_evidence"]["availability"], "full")

    def test_production_source_identity_uses_facts_not_retrieval_only_clock(self):
        scoring = self.data["league"]["scoring_settings"]
        expected = hashlib.sha256(
            json.dumps(scoring, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        facts = self.evaluate(strategy="RETOOL")["evaluation"]["player_facts"]["a"]
        self.assertEqual(facts["production"]["scoring_fingerprint"], expected)
        self.assertEqual(
            facts["projection"]["generation"],
            self.f.reader.snapshot()["horizon_generation"],
        )

    def test_player_facts_age_and_failed_refresh_retain_original_numbers(self):
        from datetime import datetime, timedelta, timezone

        for rows in self.f.payloads.values():
            for row in rows:
                row["updated_at"] = (
                    datetime.now(timezone.utc) - timedelta(hours=7)
                ).isoformat()
        self.f.reader.publish_horizon(
            self.f.payloads,
            data=self.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        report = self.evaluate(strategy="WIN NOW")["evaluation"]
        facts = report["player_facts"]["a"]["projection"]
        self.assertEqual(facts["freshness"], "Stale")
        self.assertEqual(facts["value"], 10)
        self.f.reader.begin_external_refresh()
        self.f.reader.fail_external_refresh(
            RuntimeError("controlled incomplete refresh")
        )
        report = self.evaluate(strategy="WIN NOW")["evaluation"]
        self.assertTrue(
            report["player_facts"]["a"]["projection"]["refresh_evidence"][
                "retained_publication"
            ]
        )
        self.assertIn("latest refresh did not complete", report["explanation_html"])
        self.assertEqual(report["player_facts"]["a"]["projection"]["value"], 10)

    def test_public_day_arkham_scoring_and_generation_are_distinct(self):
        from services.trade_decision import selected_player_facts
        from services.trade_intelligence import build_trade_workspace

        leagues = json.loads(
            Path("tests/fixtures/dynamic_league_settings.json").read_text()
        )["leagues"]
        outputs = []
        for league in leagues:
            data = copy.deepcopy(self.data)
            data["league"] = copy.deepcopy(league)
            data.pop("scoring_settings", None)
            self.f.reader.publish_horizon(
                self.f.payloads,
                data=data,
                league_id=league["league_id"],
                season=2026,
                current_week=2,
            )
            ws = build_trade_workspace(data, 1, market_only=True)
            value = selected_player_facts(data, ws["pools"][1], self.f.reader)["a"]
            self.assertEqual(value["projection"]["league_id"], league["league_id"])
            self.assertEqual(value["production"]["league_id"], league["league_id"])
            self.assertEqual(
                value["projection"]["value"],
                self.f.reader.week_snapshot(2)["players"]["a"]["canonical_projection"],
            )
            outputs.append(value)
        self.assertNotEqual(
            outputs[0]["projection"]["generation"],
            outputs[1]["projection"]["generation"],
        )
        self.assertNotEqual(
            outputs[0]["production"]["scoring_fingerprint"],
            outputs[1]["production"]["scoring_fingerprint"],
        )

    def test_prepared_home_identity_tracks_production_generation_not_retrieval(self):
        from services.home_trade_opportunities import source_identity

        with patch(
            "services.trade_intelligence._trade_projection_service",
            return_value=self.f.reader,
        ):
            self.data["canonical_player_production"] = {
                "league_id": "league-1",
                "season": 2026,
                "generation": "A",
            }
            first = source_identity(self.data)
            self.data["canonical_player_production"]["retrieved_at"] = (
                "2026-10-16T00:00:00Z"
            )
            self.assertEqual(source_identity(self.data), first)
            self.data["canonical_player_production"]["generation"] = "B"
            self.assertNotEqual(source_identity(self.data), first)

    def test_search_opportunity_filter_is_not_an_analysis_strategy(self):
        from services.trade_intelligence import TradeInputError

        for invalid in ("all", "All supported opportunities", "future"):
            with self.subTest(strategy=invalid), self.assertRaises(TradeInputError):
                self.evaluate(strategy=invalid)

    def test_young_bench_for_older_starter_uses_legal_impact_not_past_ppg_difference(
        self,
    ):
        self.data["players"]["b"]["age"] = 23
        self.data["players"]["c"]["age"] = 30
        self.f.points["c"] = 15
        self.f.publish()
        report = self.evaluate(
            assets_sent=["b"], assets_received=["c"], strategy="WIN NOW"
        )["evaluation"]
        self.assertEqual(report["decision_context"]["lineup"]["delta"], 5)
        self.assertNotAlmostEqual(
            report["decision_context"]["lineup"]["delta"], 18.26 - 9.92
        )
        self.assertIn("age 23", report["decision_context"]["main_cost"])
        self.assertIn("age 30", report["decision_context"]["main_cost"])
        self.assertIn("does not guarantee", report["decision_context"]["main_cost"])

    def test_incoming_questionable_qualification_is_visible_in_primary_summary(self):
        self.data["teams"][1]["players"][0]["status"] = "Questionable"
        report = self.evaluate(strategy="WIN NOW")["evaluation"]
        self.assertIn("Incoming availability", report["decision_context"]["limitation"])
        self.assertIn("Questionable", report["explanation_html"])

    def test_independent_parity_and_severe_loss_do_not_require_a_strategy_to_get_a_verdict(
        self,
    ):
        for team in self.data["teams"]:
            team.pop("strategy", None)
        report = self.evaluate(
            assets_sent=["2028-R1-3"], assets_received=["2028-R1-4"]
        )["evaluation"]
        self.assertEqual(report["recommendation"], "FAIR / OPTIONAL")
        self.assertFalse(report["decision_context"]["strategy"]["selection_required"])
        self.assertIsNone(report["decision_context"]["blocker"])
        self.f.prices(a=900, c=100)
        report = self.evaluate()["evaluation"]
        self.assertEqual(report["recommendation"], "REJECT")
        self.assertFalse(report["decision_context"]["strategy"]["selection_required"])

    def test_unsupported_scoring_does_not_publish_zero_as_a_supported_player_fact(self):
        self.data["league"]["scoring_settings"] = {"unsupported_scoring_key": 1}
        self.f.publish()
        report = self.evaluate(strategy="RETOOL")["evaluation"]
        self.assertEqual(
            report["dimensions"]["roster_diagnostics"]["sides"]["active"]["evidence"][
                "scoring"
            ],
            "unavailable / incomplete",
        )
        self.assertIsNone(report["player_facts"]["a"]["projection"]["value"])
        self.assertEqual(
            report["player_facts"]["a"]["projection"]["availability"], "unavailable"
        )
        self.assertIsNone(report["player_facts"]["a"]["production"]["points_per_game"])
        self.assertEqual(
            self.f.reader.week_snapshot(2)["players"]["a"]["canonical_projection"], 0
        )
        self.data["league"]["scoring_settings"] = {"pass_yd": 0}
        self.f.publish()
        report = self.evaluate(strategy="RETOOL")["evaluation"]
        self.assertEqual(report["player_facts"]["a"]["projection"]["value"], 0)
        self.assertEqual(
            report["player_facts"]["a"]["projection"]["availability"], "available"
        )
