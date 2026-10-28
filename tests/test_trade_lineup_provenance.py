"""One pinned publisher/optimizer supplies every admitted comparison surface."""

from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from services.trade_decision import decision_context
from services.trade_explanation import trade_explanation, render_trade_explanation
from services.trade_lineup_evidence import completed_lineup_evidence
from tests import test_trade_recommendation_clarity as fixtures


class LineupProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RecommendationClarityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.e = self.fixture.evaluate()
        self.rows = []

    def save(self, name, result):
        target = os.environ.get("DTOS_TRADE_CLARITY_EVIDENCE")
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            Path(target, name + ".json").write_text(json.dumps(result, indent=2))

    def test_valid_root_and_future_handles_cover_every_scope_without_mutation(self):
        before = deepcopy(self.e)
        a = completed_lineup_evidence(self.e)
        p = self.e["provenance"]["inputs"]["projection_evidence"]
        weeks = self.e["multi_horizon_impact"]["sides"]["active"]["weekly"]
        self.assertEqual(
            weeks[2]["pre"]["projection_snapshot_id"], p["projection_snapshot_id"]
        )
        self.assertEqual(
            weeks[3]["post"]["projection_snapshot_id"], p["horizon_snapshot_ids"]["3"]
        )
        self.assertEqual(a["identity_state"], "compatible")
        self.assertFalse(a["invalid_comparison"])
        for week in (2, 3, 4, 5):
            self.assertAlmostEqual(a["weekly"][week]["delta"], 6.31)
            self.assertEqual(a["weekly"][week]["state"], "provisional")
        self.assertEqual(a["horizons"]["current_week"]["weeks"], [2])
        self.assertAlmostEqual(a["horizons"]["next_n"]["delta"], 18.93)
        self.assertAlmostEqual(a["horizons"]["playoff_window"]["delta"], 12.62)
        html = render_trade_explanation(self.e, league_id="league-1")
        self.assertIn("Season 2026, week 2", html)
        self.assertIn("selected league scoring · Week 3", html)
        self.assertEqual(self.e, before)
        self.save("admitted-lineup-context", a)

    def test_global_conflicts_fence_headline_horizons_and_expanded_weekly_rows(self):
        controls = [
            ("projection_generation", "foreign"),
            ("league_id", "foreign"),
            ("season", 2027),
            ("current_week", 3),
            ("scoring_profile_id", "foreign"),
        ]
        for key, value in controls:
            with self.subTest(key=key):
                e = deepcopy(self.e)
                e["multi_horizon_impact"][key] = value
                a = completed_lineup_evidence(e)
                self.assertEqual(a["identity_state"], "incompatible")
                self.assertTrue(
                    all(row["delta"] is None for row in a["weekly"].values())
                )
                self.assertTrue(
                    all(row["delta"] is None for row in a["horizons"].values())
                )
                self.assertIsNone(a["mean_weekly_delta"])
                d = decision_context(e)
                self.assertIsNone(d["lineup"]["delta"])
                self.assertEqual(
                    d["final_decision"]["headline"], "Recommendation unavailable"
                )
                self.assertEqual(
                    d["final_decision"]["classification"], "MISSING REQUIRED EVIDENCE"
                )
                self.assertFalse(d["final_decision"]["qualified"])
                view = trade_explanation(e, league_id="league-1")
                values = [
                    item.display
                    for item in view.evidence
                    if item.key.startswith("weekly.")
                ]
                self.assertTrue(values)
                self.assertTrue(all(v is None for v in values))
                # Deliberately keep the earlier decision_context: the renderer
                # must reapply pure admission, not trust cached primary prose.
                html = render_trade_explanation(e, league_id="league-1")
                self.assertNotIn(
                    "6.31", html.split('<details class="tw-player-facts">')[0]
                )
                self.assertNotIn("18.93", html)
                self.rows.append(
                    dict(
                        conflict=key,
                        headline=d["final_decision"]["headline"],
                        all_weekly_withheld=True,
                    )
                )
        self.save("provenance-conflicts", self.rows)

    def test_missing_and_conflicting_global_identity_never_defaults_to_current(self):
        for key in (
            "season",
            "scoring_profile_id",
            "generation",
        ):
            e = deepcopy(self.e)
            e["provenance"]["inputs"]["projection_evidence"].pop(key)
            a = completed_lineup_evidence(e)
            self.assertNotEqual(a["identity_state"], "compatible")
            self.assertTrue(all(w["delta"] is None for w in a["weekly"].values()))

    def test_missing_evaluation_league_identity_never_admits_comparisons(self):
        e = deepcopy(self.e)
        e["provenance"]["inputs"].pop("league_id")
        admitted = completed_lineup_evidence(e)
        self.assertEqual(admitted["identity_state"], "unavailable")
        self.assertTrue(
            all(row["delta"] is None for row in admitted["weekly"].values())
        )

    def test_missing_future_manifest_preserves_independent_current_root(self):
        e = deepcopy(self.e)
        e["provenance"]["inputs"]["projection_evidence"].pop("horizon_snapshot_ids")
        admitted = completed_lineup_evidence(e)
        self.assertEqual(admitted["identity_state"], "compatible")
        self.assertAlmostEqual(admitted["weekly"][2]["delta"], 6.31)
        self.assertIsNone(admitted["weekly"][3]["delta"])
        self.assertAlmostEqual(admitted["horizons"]["current_week"]["delta"], 6.31)
        self.assertIsNone(admitted["horizons"]["next_n"]["delta"])

    def test_bad_future_post_snapshot_does_not_erase_current_or_other_window(self):
        e = deepcopy(self.e)
        e["multi_horizon_impact"]["sides"]["active"]["weekly"][3]["post"][
            "projection_snapshot_id"
        ] = "foreign"
        a = completed_lineup_evidence(e)
        self.assertAlmostEqual(a["weekly"][2]["delta"], 6.31)
        self.assertIsNotNone(a["weekly"][3]["pre"])
        self.assertIsNone(a["weekly"][3]["post"])
        self.assertIsNone(a["weekly"][3]["delta"])
        self.assertIsNone(a["horizons"]["next_n"]["delta"])
        self.assertAlmostEqual(a["horizons"]["current_week"]["delta"], 6.31)
        self.assertAlmostEqual(a["horizons"]["playoff_window"]["delta"], 12.62)
        items = {x.key: x for x in trade_explanation(e, league_id="league-1").evidence}
        self.assertIsNone(items["weekly.active.3.delta"].display)
        self.assertEqual(items["weekly.active.2.delta"].display, "6.31")
        self.assertEqual(items["active.playoff_window"].display, "12.62")
        html = render_trade_explanation(e, league_id="league-1")
        active_summary = html.split("<h4>Your team · gains and sacrifices</h4>", 1)[
            1
        ].split("</section>", 1)[0]
        self.assertIn(
            "Package-production trade-offs cannot be verified", active_summary
        )
        self.save("isolated-week-failure", a)

    def test_partner_conflict_withholds_endorsement_without_erasing_valid_user_week(
        self,
    ):
        e = deepcopy(self.e)
        e["multi_horizon_impact"]["sides"]["partner"]["weekly"][2]["post"][
            "projection_snapshot_id"
        ] = "foreign-partner-publication"
        d = decision_context(e)
        self.assertAlmostEqual(d["lineup"]["delta"], 6.31)
        self.assertEqual(d["final_decision"]["headline"], "Recommendation unavailable")
        self.assertFalse(d["final_decision"]["qualified"])
        values = {
            x.key: x.display
            for x in trade_explanation(e, league_id="league-1").evidence
        }
        self.assertEqual(values["weekly.active.2.delta"], "6.31")
        self.assertIsNone(values["weekly.partner.2.delta"])
        self.assertEqual(
            e["generated_trade_eligible"], self.e["generated_trade_eligible"]
        )

    def test_phase_week_season_scoring_and_before_after_mismatch(self):
        for phase in ("pre", "post"):
            for key, value in (
                ("week", 7),
                ("season", 2027),
                ("scoring_profile_id", "foreign"),
                ("available", False),
            ):
                with self.subTest(phase=phase, key=key):
                    e = deepcopy(self.e)
                    e["multi_horizon_impact"]["sides"]["active"]["weekly"][2][phase][
                        key
                    ] = value
                    a = completed_lineup_evidence(e)
                    self.assertIsNone(a["weekly"][2]["delta"])
                    self.assertIsNone(a["horizons"]["current_week"]["delta"])
                    self.assertAlmostEqual(a["weekly"][3]["delta"], 6.31)

    def test_horizon_and_weekly_delta_must_match_accepted_pre_post_totals(self):
        e = deepcopy(self.e)
        e["dimensions"]["strategic_fit"]["active"]["horizons"]["current_week"][
            "delta"
        ] = 5.4318
        self.assertIsNone(
            completed_lineup_evidence(e)["horizons"]["current_week"]["delta"]
        )
        self.assertAlmostEqual(completed_lineup_evidence(e)["weekly"][2]["delta"], 6.31)
        e = deepcopy(self.e)
        e["multi_horizon_impact"]["sides"]["active"]["weekly"][2]["delta"] = 5.4318
        self.assertIsNone(completed_lineup_evidence(e)["weekly"][2]["delta"])
        self.assertAlmostEqual(completed_lineup_evidence(e)["weekly"][3]["delta"], 6.31)

    def test_no_missing_delta_is_reconstructed_and_genuine_zero_stays_zero(self):
        e = deepcopy(self.e)
        row = e["multi_horizon_impact"]["sides"]["active"]["weekly"][2]
        row["delta"] = None
        self.assertIsNone(completed_lineup_evidence(e)["weekly"][2]["delta"])
        # Re-publish genuine zero, not a synthetic flag or price substitution.
        self.fixture.f.f.points["c"] = 20
        self.fixture.f.f.publish()
        e = self.fixture.evaluate()
        self.assertEqual(completed_lineup_evidence(e)["weekly"][2]["delta"], 0)
        self.assertEqual(decision_context(e)["lineup"]["delta"], 0)
