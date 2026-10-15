"""Actual canonical roster diagnostics; no count-only quality or projections."""

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.core.decision_engine.models.decision import DecisionContext
from src.core.decision_engine.team.team_evaluator import evaluate_team
from tests.test_trade_intelligence import fixture_data
from src.core.projection_intelligence.service import ProjectionService
from src.core.intelligence.roster_diagnostics import (
    diagnose_league,
    team_diagnostics,
    diagnostic_identity,
    diagnostic_store,
)


class CanonicalDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.service = ProjectionService(Path(self.folder.name) / "p.sqlite3")

    def publish(
        self, teams, slots, *, statuses=None, league="1313066632158924800", scoring=None
    ):
        self.data = {
            "league": {
                "league_id": league,
                "season": 2026,
                "roster_positions": slots,
                "scoring_settings": scoring
                or {"pass_yd": 1, "rush_yd": 1, "rec_yd": 1},
            },
            "week": 1,
            "teams": [],
            "players": {},
        }
        feed = []
        for rid, room in enumerate(teams, 1):
            players = []
            for pid, pos, value in room:
                details = {
                    "id": pid,
                    "name": pid,
                    "position": pos,
                    "roster_slot": "Bench",
                    **((statuses or {}).get(pid) or {}),
                }
                players.append(details)
                self.data["players"][pid] = {**details, "full_name": pid, "age": 24}
                if value is not None:
                    stat = {
                        "QB": "pass_yd",
                        "RB": "rush_yd",
                        "WR": "rec_yd",
                        "TE": "rec_yd",
                    }[pos]
                    feed.append(
                        {
                            "player_id": pid,
                            "season": 2026,
                            "week": 1,
                            "player": {"position": pos},
                            "stats": {stat: value},
                        }
                    )
            self.data["teams"].append(
                {
                    "roster_id": rid,
                    "owner": str(rid),
                    "team_name": "Team " + str(rid),
                    "players": players,
                    "picks_owned": [],
                }
            )
        self.snapshot = self.service.publish_horizon(
            {1: feed}, data=self.data, league_id=league, season=2026, current_week=1
        )
        return diagnose_league(self.data, self.snapshot)

    def facts(self, rid=1, pos="QB", strategy=None):
        return team_diagnostics(self.data, rid, self.snapshot, strategy=strategy)[
            "positions"
        ][pos]

    def test_superflex_three_elite_qbs_are_strength_not_forced_sales(self):
        self.publish(
            [
                [("a", "QB", 30), ("b", "QB", 29), ("c", "QB", 28)],
                [("x", "QB", 20), ("y", "QB", 19), ("z", "QB", 18)],
            ],
            ["QB", "SUPER_FLEX", "BN"],
        )
        row = self.facts()
        self.assertTrue(row["strength"])
        self.assertEqual(row["surplus_assets"], [])
        self.assertFalse(row["remove_one"]["c"]["preserves_disjoint_reserve"])
        self.assertGreater(row["remove_one"]["a"]["lineup_loss"], 0)

    def test_only_two_usable_superflex_qbs_discloses_resilience(self):
        self.publish(
            [[("a", "QB", 25), ("b", "QB", 20)], [("x", "QB", 24), ("y", "QB", 19)]],
            ["QB", "SUPER_FLEX", "BN"],
        )
        self.assertTrue(self.facts()["resilience_need"])
        self.assertFalse(self.facts()["surplus_assets"])

    def test_rb_heavy_league_not_universal_surplus(self):
        teams = [
            [(f"{rid}-{i}", "RB", 20 if i < 2 else 1) for i in range(8)]
            for rid in range(10)
        ]
        result = self.publish(teams, ["RB", "RB"] + ["BN"] * 12)
        self.assertTrue(
            all(
                not row["positions"]["RB"]["surplus_assets"]
                for row in result["teams"].values()
            )
        )
        self.assertTrue(
            all(
                not row["positions"]["RB"]["starter_need"]
                for row in result["teams"].values()
            )
        )

    def test_wr_concentration_is_context_not_count_penalty(self):
        self.publish(
            [
                [(f"a{i}", "WR", 10) for i in range(8)],
                [(f"b{i}", "WR", 10) for i in range(8)],
            ],
            ["WR", "WR", "FLEX"] + ["BN"] * 12,
        )
        self.assertEqual(self.facts(pos="WR")["league_starter_observations"], 6)
        self.assertFalse(self.facts(pos="WR")["surplus_assets"])

    def test_shallow_and_deep_bench_do_not_change_fixed_player_targets(self):
        teams = [
            [("a", "RB", 20), ("b", "RB", 19), ("c", "RB", 18)],
            [("x", "RB", 15), ("y", "RB", 10), ("z", "RB", 5)],
        ]
        self.publish(teams, ["RB", "BN"])
        short = self.facts(pos="RB")
        self.publish(teams, ["RB"] + ["BN"] * 15)
        deep = self.facts(pos="RB")
        self.assertEqual(short, deep)

    def test_top_heavy_roster_does_not_mistake_marginal_reserves_for_quality(self):
        self.publish(
            [
                [("a", "WR", 30), ("b", "WR", 1), ("c", "WR", 1)],
                [("x", "WR", 20), ("y", "WR", 15), ("z", "WR", 10)],
            ],
            ["WR", "WR", "BN"],
        )
        row = self.facts(pos="WR")
        self.assertTrue(row["starter_need"])
        self.assertGreater(row["add_one_gain"], 0)
        self.assertFalse(row["surplus_assets"])

    def test_interchangeable_useful_depth_can_be_conditionally_expendable(self):
        self.publish(
            [[(f"a{i}", "TE", 20) for i in range(4)], [("x", "TE", 5), ("y", "TE", 4)]],
            ["TE", "BN", "BN", "BN"],
        )
        row = self.facts(pos="TE")
        self.assertTrue(row["surplus_assets"])
        for asset in row["surplus_assets"]:
            loss = row["remove_one"][asset["player_id"]]
            self.assertTrue(loss["preserves_lineup"])
            self.assertTrue(loss["preserves_disjoint_reserve"])

    def test_elite_te_and_weak_backup_preserves_top_starter(self):
        self.publish(
            [[("a", "TE", 30), ("b", "TE", 1)], [("x", "TE", 20), ("y", "TE", 10)]],
            ["TE", "BN"],
        )
        self.assertEqual(self.facts(pos="TE")["remove_one"]["a"]["lineup_loss"], 29)
        self.assertFalse(self.facts(pos="TE")["surplus_assets"])
        self.assertTrue(self.facts(pos="TE")["quality_depth_need"])

    def test_equal_starter_and_only_backup_are_not_double_counted(self):
        self.publish(
            [[("a", "QB", 20), ("b", "QB", 20)], [("x", "QB", 5), ("y", "QB", 4)]],
            ["QB", "BN"],
        )
        self.assertFalse(self.facts()["surplus_assets"])
        self.assertFalse(self.facts()["remove_one"]["a"]["preserves_disjoint_reserve"])

    def test_ir_taxi_out_and_bye_not_counted_as_usable_reserves(self):
        statuses = {
            "b": {"roster_slot": "IR"},
            "c": {"roster_slot": "Taxi"},
            "d": {"injury_status": "Out"},
            "e": {"bye_week": 1},
        }
        result = self.publish(
            [
                [
                    ("a", "QB", 20),
                    ("b", "QB", 30),
                    ("c", "QB", 30),
                    ("d", "QB", 30),
                    ("e", "QB", 30),
                ],
                [("x", "QB", 15)],
            ],
            ["QB", "BN"],
            statuses=statuses,
        )
        self.assertEqual(
            result["teams"]["1"]["excluded_player_ids"], ["b", "c", "d", "e"]
        )
        self.assertTrue(self.facts()["resilience_need"])

    def test_unknown_projection_and_questionable_status_are_not_zero(self):
        for status in ({}, {"b": {"injury_status": "Q"}}):
            self.publish(
                [
                    [("a", "QB", 20), ("b", "QB", None if not status else 15)],
                    [("x", "QB", 15)],
                ],
                ["QB", "BN"],
                statuses=status,
            )
            self.assertEqual(self.facts()["classification"], "Uncertain")
            self.assertFalse(self.facts()["surplus_assets"])

    def test_known_zero_is_supported_but_market_missing_does_not_reprice_diagnostics(
        self,
    ):
        self.publish([[("a", "QB", 0)], [("x", "QB", 0)]], ["QB"])
        first = diagnose_league(self.data, self.snapshot)
        self.assertEqual(first["teams"]["1"]["optimal_points"], 0)
        self.data["market_data"] = {
            "providers": {"FantasyCalc": {"a": {"value": 0}, "x": {"value": None}}}
        }
        self.assertEqual(first, diagnose_league(self.data, self.snapshot))

    def test_rebuild_and_retool_interpret_without_aging_starter_prescription(self):
        self.publish([[("a", "QB", 5)], [("x", "QB", 20)]], ["QB", "BN"])
        rebuild = self.facts(strategy="REBUILD")
        win = self.facts(strategy="WIN NOW")
        retool = self.facts(strategy="RETOOL")
        self.assertIn(
            "not advice to acquire an aging starter", rebuild["interpretation"]
        )
        self.assertIn("WIN NOW", win["interpretation"])
        self.assertIn("RETOOL", retool["interpretation"])
        self.assertEqual(rebuild["add_one_gain"], win["add_one_gain"])

    def test_flex_replacements_are_disjoint_and_unique(self):
        result = self.publish(
            [
                [
                    ("a", "RB", 20),
                    ("b", "WR", 19),
                    ("c", "TE", 18),
                    ("d", "RB", 17),
                    ("e", "WR", 16),
                ],
                [("x", "RB", 15), ("y", "WR", 14), ("z", "TE", 13)],
            ],
            ["RB", "WR", "FLEX", "BN", "BN"],
        )
        row = result["teams"]["1"]
        self.assertFalse(set(row["optimal_ids"]) & set(row["reserve_ids"]))
        self.assertEqual(len(row["optimal_ids"]), len(set(row["optimal_ids"])))

    def test_superflex_can_replace_qb_with_other_eligible_position(self):
        self.publish(
            [
                [("a", "QB", 20), ("b", "RB", 19), ("c", "WR", 18), ("d", "TE", 17)],
                [("x", "QB", 20), ("y", "WR", 15)],
            ],
            ["QB", "SUPER_FLEX", "BN"],
        )
        self.assertEqual(self.facts()["remove_one"]["a"]["supported_slots_after"], 1)
        self.assertEqual(self.facts(pos="RB")["remove_one"]["b"]["lineup_loss"], 1)

    def test_superflex_cross_position_replacement_is_not_missing_qb_depth(self):
        self.publish(
            [
                [("a", "QB", 20), ("b", "QB", 19), ("c", "RB", 18)],
                [("x", "QB", 15), ("y", "QB", 14), ("z", "QB", 10)],
            ],
            ["QB", "SUPER_FLEX", "BN"],
        )
        self.assertFalse(self.facts()["resilience_need"])
        self.assertFalse(self.facts()["quality_depth_need"])

    def test_intelligence_view_invalidates_on_roster_not_retrieval_clock(self):
        from src.core.intelligence.context import build_context

        self.publish(
            [[("a", "QB", 20), ("b", "QB", 19)], [("x", "QB", 15)]], ["QB", "BN"]
        )
        with patch("src.core.projection_intelligence.projection_service", self.service):
            before = build_context(self.data, 1).snapshot_key
            self.data["last_sync"] = "2099-01-01"
            self.assertEqual(before, build_context(self.data, 1).snapshot_key)
            self.data["teams"][1]["players"].append(
                self.data["teams"][0]["players"].pop()
            )
            self.assertNotEqual(before, build_context(self.data, 1).snapshot_key)

    def test_lineup_settings_and_scoring_change_identity(self):
        teams = [[("a", "QB", 20), ("b", "QB", 19)], [("x", "QB", 15), ("y", "QB", 14)]]
        self.publish(teams, ["QB", "BN"])
        first = diagnostic_identity(self.data, self.snapshot)
        self.publish(teams, ["QB", "SUPER_FLEX", "BN"])
        self.assertNotEqual(first, diagnostic_identity(self.data, self.snapshot))
        second = diagnostic_identity(self.data, self.snapshot)
        self.publish(teams, ["QB", "SUPER_FLEX", "BN"], scoring={"pass_yd": 0.5})
        self.assertNotEqual(second, diagnostic_identity(self.data, self.snapshot))

    def test_ownership_league_availability_and_peer_distribution_invalidate(self):
        self.publish(
            [[("a", "QB", 20), ("b", "QB", 15)], [("x", "QB", 10), ("y", "QB", 5)]],
            ["QB", "BN"],
        )
        key = diagnostic_identity(self.data, self.snapshot)
        self.data["last_sync"] = "2099-01-01"
        self.assertEqual(key, diagnostic_identity(self.data, self.snapshot))
        self.data["teams"][1]["players"].append(self.data["teams"][0]["players"].pop())
        self.assertNotEqual(key, diagnostic_identity(self.data, self.snapshot))
        changed = diagnostic_identity(self.data, self.snapshot)
        self.data["players"]["a"]["injury_status"] = "Out"
        self.assertNotEqual(changed, diagnostic_identity(self.data, self.snapshot))
        self.data["league"]["league_id"] = "1319750579458686976"
        self.assertEqual(self.facts()["classification"], "Uncertain")

    def test_returned_cache_cannot_be_mutated_and_is_bounded(self):
        self.publish([[("a", "QB", 20)], [("x", "QB", 10)]], ["QB"])
        one = diagnose_league(self.data, self.snapshot)
        one["teams"]["1"]["positions"]["QB"]["classification"] = "FAKE"
        self.assertNotEqual(self.facts()["classification"], "FAKE")
        status = diagnostic_store.status()
        self.assertLessEqual(status["retained_bytes"], 2_097_152)
        self.assertLessEqual(status["entries"], 12)

    def test_shared_my_team_and_decision_positions_agree(self):
        self.publish(
            [[("a", "QB", 20), ("b", "QB", 15)], [("x", "QB", 10), ("y", "QB", 5)]],
            ["QB", "BN"],
        )
        with patch("src.core.projection_intelligence.projection_service", self.service):
            decision = evaluate_team(
                self.data,
                1,
                DecisionContext(
                    1,
                    self.data["league"]["league_id"],
                    {"roster_positions": ["QB", "BN"]},
                    "WIN NOW",
                ),
            )
        expected = self.facts(strategy="WIN NOW")
        self.assertEqual(decision.diagnostics["positions"]["QB"], expected)
        self.assertIsNone(decision.position_evaluations["QB"].score)

    def test_wrong_scoring_or_foreign_publication_is_not_admitted(self):
        self.publish([[("a", "QB", 20)], [("x", "QB", 10)]], ["QB"])
        self.data["scoring_settings"] = {"pass_yd": 99}
        self.assertEqual(self.facts()["classification"], "Uncertain")
        del self.data["scoring_settings"]
        self.snapshot = {**self.snapshot, "league_id": "foreign"}
        self.assertEqual(self.facts()["classification"], "Uncertain")

    def test_day_arkham_supported_publications_and_roster_ids_are_separate(self):
        self.publish(
            [[("a", "QB", 20), ("b", "QB", 19)], [("x", "QB", 15), ("y", "QB", 14)]],
            ["QB", "SUPER_FLEX", "BN"],
        )
        day_data = json.loads(json.dumps(self.data))
        day_snapshot = self.snapshot
        day = diagnose_league(day_data, day_snapshot)
        self.publish(
            [[("a", "QB", 20), ("b", "QB", 19)], [("x", "QB", 15), ("y", "QB", 14)]],
            ["QB", "BN"],
            league="1319750579458686976",
            scoring={"pass_yd": 0.5},
        )
        arkham = diagnose_league(self.data, self.snapshot)
        self.assertNotEqual(day["generation"], arkham["generation"])
        self.assertEqual(day["teams"]["1"]["optimal_points"], 39)
        self.assertEqual(arkham["teams"]["1"]["optimal_points"], 10)
        self.assertEqual(day, diagnose_league(day_data, day_snapshot))

    def test_actual_captured_league_rules_drive_supported_diagnostics(self):
        capture = json.loads(
            (
                Path(__file__).parent / "fixtures/dynamic_league_settings.json"
            ).read_text()
        )
        generations = []
        for league in capture["leagues"]:
            teams = [
                [
                    (f"{owner}-{pos}-{i}", pos, 100 - i * 10)
                    for pos, n in [("QB", 3), ("RB", 5), ("WR", 7), ("TE", 3)]
                    for i in range(n)
                ]
                for owner in (1, 2)
            ]
            result = self.publish(
                teams,
                league["roster_positions"],
                league=league["league_id"],
                scoring=league["scoring_settings"],
            )
            self.assertEqual(result["teams"]["1"]["coverage"], "supported current week")
            self.assertEqual(
                len(result["teams"]["1"]["optimal_ids"]),
                sum(slot != "BN" for slot in league["roster_positions"]),
            )
            generations.append(result["generation"])
        self.assertNotEqual(*generations)

    def test_peer_concentration_changes_observed_reference_without_pricing(self):
        self.publish(
            [[("a", "WR", 10), ("b", "WR", 9)], [("x", "WR", 20), ("y", "WR", 19)]],
            ["WR", "BN"],
        )
        before = self.facts(pos="WR")
        self.assertTrue(before["starter_need"])
        self.publish(
            [[("a", "WR", 10), ("b", "WR", 9)], [("x", "WR", 5), ("y", "WR", 4)]],
            ["WR", "BN"],
        )
        self.assertFalse(self.facts(pos="WR")["starter_need"])
        self.assertNotEqual(
            before["league_reference_points"],
            self.facts(pos="WR")["league_reference_points"],
        )

    def test_bounded_configuration_withholds_instead_of_expanding_forever(self):
        result = self.publish([[("a", "QB", 20)], [("x", "QB", 10)]], ["QB"] * 15)
        self.assertEqual(
            result["teams"]["1"]["positions"]["QB"]["classification"], "Uncertain"
        )
        self.assertIn("bounded", result["teams"]["1"]["limitations"][0])

    def test_front_office_compatibility_uses_published_need_and_expendability(self):
        from dataclasses import replace
        from src.core.front_office_intelligence import build_league_model
        from src.core.front_office_intelligence.engine import _compatibility

        self.publish(
            [
                [("a", "WR", 5), ("b", "WR", 4)],
                [("x", "WR", 10), ("y", "WR", 9), ("z", "WR", 8), ("w", "WR", 7)],
                [("u", "WR", 9), ("v", "WR", 8)],
            ],
            ["WR", "BN", "BN", "BN"],
        )
        with patch("src.core.projection_intelligence.projection_service", self.service):
            model = build_league_model(self.data)
        reports = []
        for rid in (1, 2):
            report = model.reports[rid]
            facts = team_diagnostics(self.data, rid, self.snapshot, strategy="WIN NOW")
            reports.append(
                replace(report, decision=replace(report.decision, diagnostics=facts))
            )
        self.assertTrue(
            reports[0].decision.diagnostics["positions"]["WR"]["objective_need"]
        )
        self.assertTrue(
            reports[1].decision.diagnostics["positions"]["WR"]["surplus_assets"]
        )
        result = _compatibility(self.data, *reports)
        self.assertIn("WR", result.shared_interests)
        self.assertIn(
            "Team 1's supported WR need", result.forecast.opening_recommendation
        )
        self.assertIn("Team 2", result.forecast.opening_recommendation)
        self.assertIsNone(result.forecast.acceptance_probability)


class DynamicNeedsIntegrationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_home_opportunity_integrity import OpportunityIntegrityTests

        self.f = OpportunityIntegrityTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.enterContext(
            patch(
                "src.core.projection_intelligence.projection_service",
                self.f.source.reader,
            )
        )

    def test_actual_evaluation_recomputes_whole_package_not_sum_of_assets(self):
        f = self.f
        f.payload.update(assets_sent=["a", "b"], assets_received=["c", "d"])
        response = f.evaluate()
        self.assertEqual(response.status_code, 200, response.text)
        e = response.json()["evaluation"]
        row = e["dimensions"]["roster_diagnostics"]["sides"]["active"]
        self.assertEqual(row["pre_optimal_points"], 10)
        self.assertEqual(row["post_optimal_points"], 8)
        ids = [p for facts in row["positions"].values() for p in facts["post_starters"]]
        self.assertEqual(ids, ["c"])
        self.assertNotIn("a", ids)
        self.assertNotIn("b", ids)
        self.assertEqual(e["lineup_impact"]["active"]["delta"], -2)

    def test_availability_filter_never_relabels_canonical_package_projection(self):
        f = self.f
        f.f.data["players"]["a"]["injury_status"] = "Out"
        response = f.evaluate()
        self.assertEqual(response.status_code, 200, response.text)
        e = response.json()["evaluation"]
        canonical = e["multi_horizon_impact"]["sides"]["active"]["weekly"]["2"]["pre"][
            "optimal"
        ]["projected_points"]
        diagnostic = e["dimensions"]["roster_diagnostics"]["sides"]["active"]
        self.assertEqual(diagnostic["pre_optimal_points"], canonical)
        self.assertEqual(diagnostic["coverage"], "partial / unavailable")

    def test_forced_cut_is_not_a_supported_complete_diagnostic(self):
        f = self.f
        f.data = f.f.data
        f.data["league"]["roster_positions"] = ["QB", "BN", "BN"]
        f.source.publish()
        f.payload.update(assets_sent=["a"], assets_received=["c", "d", "f"])
        response = f.evaluate()
        self.assertEqual(response.status_code, 200, response.text)
        row = response.json()["evaluation"]["dimensions"]["roster_diagnostics"][
            "sides"
        ]["active"]
        self.assertEqual(row["capacity"]["additional_spots_to_resolve"], 2)
        self.assertEqual(row["coverage"], "partial / unavailable")

    def test_market_and_projections_are_strategy_invariant_and_reason_is_shared(self):
        f = self.f
        first = f.evaluate().json()["evaluation"]
        f.payload["strategy"] = "WIN NOW"
        second = f.evaluate().json()["evaluation"]
        self.assertEqual(first["values"], second["values"])
        self.assertEqual(first["lineup_impact"], second["lineup_impact"])
        self.assertIn(
            "Replacement support is recalculated", second["counterparty_summary"]
        )
        summary = second["dimensions"]["roster_diagnostics"]["sides"]["active"][
            "summary"
        ]
        self.assertIn(summary, second["explanation_html"])

    def test_selected_my_team_and_opponent_share_structural_diagnostic(self):
        from services.team_headquarters import build_team_headquarters

        f = self.f
        for rid in (1, 2):
            view = build_team_headquarters(f.f.data, rid, strategy="WIN NOW")
            for pos, facts in view["overview"]["positions"].items():
                expected = team_diagnostics(
                    f.f.data, rid, f.source.reader.snapshot(), strategy="WIN NOW"
                )["positions"][pos]
                self.assertEqual(facts["diagnostic"], expected)


class DynamicNeedsTests(unittest.TestCase):
    def test_missing_projections_never_prove_rb_depth(self):
        data = fixture_data()
        data["teams"][0]["players"] = [
            {
                "id": "rb" + str(i),
                "position": "RB",
                "roster_slot": "Starter" if i < 2 else "Bench",
            }
            for i in range(8)
        ]
        decision = evaluate_team(
            data,
            1,
            DecisionContext(1, "league-1", {"roster_positions": ["RB", "RB", "BN"]}),
        )
        self.assertIsNone(
            decision.position_evaluations["RB"].score,
            "Eight unprojected RBs cannot establish quality or expendable depth.",
        )


if __name__ == "__main__":
    unittest.main()
