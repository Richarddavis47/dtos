"""Completed producer -> decision -> HTTP controls; all prices are disposable fixtures."""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from services.trade_decision import decision_context, final_decision
from services.trade_explanation import render_trade_explanation, trade_explanation
from services.trade_intelligence import (
    evaluate_trade_request,
    generate_trade_workflow,
    build_trade_workspace,
)
from tests import test_trade_decision_http_browser as http_fixture
from tests import test_trade_discovery_repair as discovery


class RecommendationClarityTests(unittest.TestCase):
    def setUp(self):
        self.f = http_fixture.DecisionHTTPBrowserTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        self.f.f.points.update(a=20, c=26.31)
        self.f.f.prices(a=608, c=931, b=80, d=150, e=100, f=100)
        q = deepcopy(self.data["market_data"]["pick_quotes"]["FantasyCalc"][0])
        q.update(year=2029, value=334 * 12)
        q["normalization_reference"].update(raw_value=334 * 12, normalized_value=334)
        self.data["market_data"]["pick_quotes"]["FantasyCalc"].append(q)
        self.f.f.publish()
        self.payload = dict(
            active_roster_id=1,
            partner_roster_id=2,
            assets_sent=["a", "2029-R1-1"],
            assets_received=["c"],
            strategy="RETOOL",
        )

    def evaluate(self, **kw):
        return evaluate_trade_request(
            self.data, {**self.payload, **kw}, projection_reader=self.f.f.reader
        )["evaluation"]

    def test_exact_prices_legal_gain_and_distinct_week_contexts(self):
        # Publish a genuinely different week rather than relabeling the same gain.
        self.f.f.payloads[3] = [
            dict(row, stats={"pass_yd": 26.94}) if row["player_id"] == "c" else row
            for row in self.f.f.payloads[3]
        ]
        self.f.f.reader.publish_horizon(
            self.f.f.payloads,
            data=self.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        from src.core.intelligence.team_strength import prepare_for_data
        from unittest.mock import patch

        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(self.f.f.reader, self.data)
        e = self.evaluate()
        self.assertEqual(
            (
                e["market_evidence"]["sent"]["total"],
                e["market_evidence"]["received"]["total"],
            ),
            (942, 931),
        )
        self.assertAlmostEqual(e["decision_context"]["lineup"]["delta"], 6.31)
        self.assertEqual(e["decision_context"]["lineup"]["weeks"], [2])
        self.assertIn(
            "Season 2026, week 2", e["decision_context"]["lineup"]["explanation"]
        )
        self.assertAlmostEqual(
            e["multi_horizon_impact"]["sides"]["active"]["weekly"][3]["delta"], 6.94
        )
        self.assertIn("weeks 2, 3, 4", e["explanation_html"])
        self.assertEqual(e["market_evidence"]["difference"], -11)
        self.assertEqual(self.payload["assets_sent"], ["a", "2029-R1-1"])

    def test_stricter_availability_diagnostic_does_not_erase_prepared_comparison(self):
        e = self.evaluate()
        math = deepcopy(e["multi_horizon_impact"])
        e["dimensions"]["roster_diagnostics"]["sides"]["active"][
            "numeric_impact_state"
        ] = "unsupported"
        d = decision_context(e)
        e["decision_context"] = d
        self.assertAlmostEqual(d["lineup"]["delta"], 6.31)
        self.assertEqual(d["lineup"]["state"], "provisional")
        self.assertIn(
            "does not establish dependable availability", d["lineup"]["explanation"]
        )
        self.assertNotIn(
            "improvement is unavailable",
            render_trade_explanation(e, league_id="league-1"),
        )
        self.assertEqual(e["multi_horizon_impact"], math)

    def test_missing_current_week_does_not_erase_other_supported_weeks(self):
        e = self.evaluate()
        e["dimensions"]["strategic_fit"]["active"]["horizons"]["current_week"].update(
            delta=None, availability="partial_or_unavailable"
        )
        d = decision_context(e)
        self.assertIsNone(d["lineup"]["delta"])
        self.assertIn("Other supported periods", d["lineup"]["explanation"])
        self.assertIsNotNone(d["lineup_comparisons"]["next_n"]["delta"])
        # An incompatible publication cannot supply even that comparison.
        e["multi_horizon_impact"]["projection_generation"] = "foreign-generation"
        self.assertTrue(
            all(
                r["delta"] is None
                for r in decision_context(e)["lineup_comparisons"].values()
            )
        )

    def test_genuine_zero_remains_unchanged_not_missing(self):
        self.f.f.points['c'] = 20
        self.f.f.publish()
        e = self.evaluate()
        d = decision_context(e)
        self.assertEqual(d["lineup"]["delta"], 0)
        self.assertIn("unchanged", d["lineup"]["explanation"])

    def test_real_custom_pick_exchange_keeps_neutral_counterparty_veto(self):
        # Actual personal adapter + neutral bilateral gate, not a patched verdict.
        self.data["teams"][0]["strategy"] = "RETOOL"
        self.data["teams"][1]["strategy"] = "RETOOL"
        workspace = build_trade_workspace(self.data, 1)
        values = {
            a.asset_id: a.trade_value
            for pool in workspace["pools"].values()
            for a in pool
        }
        # Swap existing curve slots. User likes their first, opponent uses neutral prices.
        custom = dict(values)
        custom["c"], custom["2028-R1-4"] = custom["2028-R1-4"], custom["c"]
        context = dict(
            mode="custom",
            revision=9,
            baseline_generation="fixture",
            market_generation="fixture",
            method="market-rank-slot-curve-v1",
            values=custom,
            neutral_values=values,
            preferences={},
        )
        e = self.evaluate(
            assets_sent=["2028-R4-3"],
            assets_received=["2028-R1-4"],
            _personal_context=context,
        )
        self.assertFalse(e["generated_trade_eligible"])
        final = final_decision(e)
        self.assertEqual(final["headline"], "COUNTERPARTY LIMITED")
        self.assertIn(e["recommendation"], ("WORTH PURSUING", "SMASH ACCEPT"))
        self.assertIn("COUNTERPARTY LIMITED", e["explanation_html"].split("</p>")[0])
        self.assertNotIn("WORTH PURSUING", e["explanation_html"].split("</p>")[0])
        self.assertIn("Your-side assessment only", e["explanation_html"])
        self.assertEqual(e["personalization"]["revision"], 9)
        self.assertEqual(sorted(custom.values()), sorted(values.values()))
        view = trade_explanation(e, league_id="league-1")
        self.assertEqual(view.conclusion.evidence_keys, ("bilateral_decision",))
        self.assertEqual(
            next(
                item.display
                for item in view.evidence
                if item.key == "bilateral_decision"
            ),
            "COUNTERPARTY LIMITED",
        )
        self.limited = e
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            Path(target, "limited.json").write_text(json.dumps(e, indent=2))

    def test_actual_authenticated_http_preserves_numeric_policy(self):
        with self.f.auth.client as client:
            context = client.get("/api/trades/workspace").json()["workspace_context"]
            r = client.post(
                "/api/trades/evaluate",
                json={**self.payload, "workspace_context": context},
                headers={"X-CSRF-Token": self.f.auth.csrf},
            )
            self.assertEqual(r.status_code, 200, r.text)
            e = r.json()["evaluation"]
            direct = self.evaluate()
            for field in (
                "recommendation",
                "generated_trade_eligible",
                "market_evidence",
                "multi_horizon_impact",
                "values",
            ):
                self.assertEqual(e[field], json.loads(json.dumps(direct[field])))
            self.assertIn("6.31", r.text)
            self.assertIn("week 2", r.text)

    def test_modes_and_explicit_strategies_preserve_neutral_math_and_packages(self):
        workspace = build_trade_workspace(self.data, 1)
        values = {
            a.asset_id: a.trade_value
            for pool in workspace["pools"].values()
            for a in pool
        }
        context = dict(
            mode="custom",
            revision=9,
            baseline_generation="fixture",
            market_generation="fixture",
            method="market-rank-slot-curve-v1",
            values=values,
            neutral_values=values,
            preferences={},
        )
        for strategy in ("WIN NOW", "REBUILD", "RETOOL"):
            neutral = self.evaluate(strategy=strategy)
            custom = self.evaluate(strategy=strategy, _personal_context=context)
            for field in ("market_evidence", "multi_horizon_impact", "lineup_impact"):
                self.assertEqual(neutral[field], custom[field])
            self.assertEqual(
                neutral["dimensions"]["counterparty_plausibility"],
                custom["dimensions"]["counterparty_plausibility"],
            )
            self.assertEqual(neutral["decision_context"]["lineup"]["delta"], 6.31)
            self.assertEqual(custom["personalization"]["revision"], 9)

    def test_repeated_formatting_adds_no_heavy_work_or_mutation(self):
        from contextlib import ExitStack
        from time import perf_counter
        from unittest.mock import patch

        e = self.evaluate()
        before = deepcopy(e)
        targets = (
            "services.sleeper.sleeper_get",
            "services.trade_intelligence.generate_trade_workflow",
            "src.core.fois.service.FOISService._generate_sync",
            "src.core.historical_franchise_state.service.HistoricalFranchiseStateService.reconstruct",
            "src.core.trade_intelligence.lineup.optimal_legal_lineup",
            "src.core.asset_market.engine.AssetMarketCache.get",
        )
        with ExitStack() as stack:
            guards = [
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
                for target in targets
            ]
            start = perf_counter()
            for _ in range(100):
                decision_context(e)
                render_trade_explanation(e, league_id="league-1")
            elapsed = perf_counter() - start
            self.assertTrue(all(guard.call_count == 0 for guard in guards))
        self.assertEqual(e, before)
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            Path(target, "formatting-cost.json").write_text(
                json.dumps(
                    dict(
                        renders=100,
                        seconds=elapsed,
                        added_heavy_calls=dict.fromkeys(targets, 0),
                        evidence_mutations=0,
                    ),
                    indent=2,
                )
            )


class UnseededStrategyControls(unittest.TestCase):
    def test_same_publication_no_preselected_target_and_strategy_differs(self):
        f = discovery.DiscoveryRepairTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        before = deepcopy(f.data)
        results = {}
        for strategy in ("WIN NOW", "REBUILD", "RETOOL"):
            payload = {
                "workflow": "recommended",
                "active_roster_id": 1,
                "strategy": strategy,
            }
            result = generate_trade_workflow(f.data, payload)
            rows = result["results"]
            results[strategy] = [
                (r["proposal"]["assets_sent"], r["proposal"]["assets_received"])
                for r in rows
            ]
            for row in rows:
                self.assertTrue(row["evaluation"]["generated_trade_eligible"])
                self.assertNotIn(
                    row["evaluation"]["recommendation"], ("REJECT", "NOT WORTH IT")
                )
            self.assertNotIn("asset_id", payload)
        self.assertNotEqual(results["WIN NOW"], results["REBUILD"])
        self.assertEqual(f.data, before)
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            Path(target, "unseeded-strategies.json").write_text(
                json.dumps(results, indent=2)
            )
