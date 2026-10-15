"""Real publication/evaluation controls for post-trade and source-clock evidence."""

from datetime import datetime, timedelta, timezone
from copy import deepcopy
import unittest
from unittest.mock import patch

from tests import test_roster_diagnostic_http as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics


class DiagnosticAgingTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DiagnosticHTTPTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.observed = datetime.now(timezone.utc).replace(microsecond=0)
        for team in self.f.f.f.data["teams"]:
            for player in team["players"]:
                player.update(status="Active", team="NYJ")
                self.f.f.f.data["players"][player["id"]].update(
                    status="Active", team="NYJ"
                )
        self.f.publish(self.observed.isoformat())
        self.data = self.f.f.f.data
        self.service = self.f.f.source.reader

    def package(self, status):
        player = self.data["teams"][0]["players"][0]
        player["status"] = status
        player["team"] = "NYJ"
        self.data["players"]["a"]["status"] = status
        response = self.f.f.evaluate()
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["evaluation"]["dimensions"]["roster_diagnostics"]

    def test_incoming_uncertainty_uses_complete_post_roster(self):
        for status in ("Unknown", "Questionable", "Doubtful"):
            with self.subTest(status=status):
                receiver = self.package(status)["sides"]["partner"]
                self.assertNotEqual(receiver["evidence"]["conclusion_state"], "current")
                incoming = next(
                    e for e in receiver["post_eligibility"] if e["player_id"] == "a"
                )
                self.assertEqual(incoming["status"], status.lower())
                self.assertNotIn(
                    "a", [e["player_id"] for e in receiver["pre_eligibility"]]
                )

    def test_clock_crosses_boundaries_without_republication(self):
        snapshot = self.service.snapshot()
        for seconds, expected in (
            (0, "Fresh"),
            (3599, "Fresh"),
            (3600, "Aging"),
            (21599, "Aging"),
            (21600, "Stale"),
            (30000, "Stale"),
        ):
            with (
                self.subTest(seconds=seconds),
                patch.object(
                    diagnostics,
                    "_now",
                    return_value=self.observed + timedelta(seconds=seconds),
                    create=True,
                ),
            ):
                row = diagnostics.team_diagnostics(self.data, 1, snapshot)
                self.assertEqual(row["evidence"]["projection_freshness"], [expected])
                self.assertEqual(row["optimal_points"], 10)
        self.assertIs(snapshot, self.service.snapshot())

    def test_failed_refresh_retained_provenance(self):
        self.service.begin_external_refresh()
        self.service.fail_external_refresh(
            RuntimeError("controlled incomplete refresh")
        )
        row = diagnostics.team_diagnostics(self.data, 1, self.service.snapshot())
        self.assertTrue(row["evidence"]["refresh"]["retained_publication"])
        self.assertIn(
            "latest refresh did not complete", " ".join(row["evidence"]["limitations"])
        )
        self.assertEqual(row["optimal_points"], 10)

    def test_complete_status_matrix_preserves_pre_post_identity_and_numerics(self):
        for status in (
            "Active",
            "Unknown",
            "Questionable",
            "Doubtful",
            "Out",
            "Inactive",
            "Retired",
        ):
            with self.subTest(status=status):
                result = self.package(status)
                sender, receiver = (
                    result["sides"][side] for side in ("active", "partner")
                )
                self.assertIn("a", [e["player_id"] for e in sender["pre_eligibility"]])
                self.assertNotIn(
                    "a", [e["player_id"] for e in sender["post_eligibility"]]
                )
                incoming = next(
                    e for e in receiver["post_eligibility"] if e["player_id"] == "a"
                )
                self.assertEqual(
                    incoming["excluded"], status in {"Out", "Inactive", "Retired"}
                )
                if status in {"Unknown", "Questionable", "Doubtful"}:
                    self.assertEqual(receiver["available_post_optimal_points"], 10)
                    self.assertEqual(receiver["numeric_impact_state"], "provisional")
                if incoming["excluded"]:
                    self.assertEqual(receiver["available_post_optimal_points"], 8)
                    self.assertIn("excluded", receiver["summary"])

    def test_exact_twenty_to_twenty_eight_receiver_control(self):
        self.f.f.source.points.update(a=28, c=20)
        self.f.publish(self.observed.isoformat())
        for status in ("Active", "Unknown", "Questionable", "Doubtful"):
            with self.subTest(status=status):
                receiver = self.package(status)["sides"]["partner"]
                self.assertEqual(receiver["pre_optimal_points"], 20)
                self.assertEqual(receiver["post_optimal_points"], 28)
                self.assertEqual(receiver["available_post_optimal_points"], 28)
                self.assertEqual(
                    receiver["pre_evidence"]["conclusion_state"], "current"
                )
                self.assertEqual(
                    receiver["post_evidence"]["conclusion_state"],
                    "current" if status == "Active" else "provisional",
                )

    def test_multiple_incoming_bench_uncertainty_and_outgoing_removal(self):
        self.f.f.payload["assets_sent"] = ["a", "b"]
        self.data["teams"][0]["players"][1]["status"] = "Doubtful"
        receiver = self.package("Active")["sides"]["partner"]
        self.assertEqual(receiver["available_post_optimal_points"], 10)
        self.assertEqual(receiver["post_evidence"]["conclusion_state"], "provisional")
        self.assertEqual(
            {e["player_id"] for e in receiver["post_eligibility"]},
            {"a", "b", "c", "d", "f"},
        )
        self.assertEqual(len(receiver["positions"]["QB"]["post_starters"]), 1)
        self.assertIn("capacity", receiver)
        sender = self.package("Unknown")["sides"]["active"]
        self.assertEqual(sender["post_evidence"]["conclusion_state"], "current")
        self.assertNotIn("a", [e["player_id"] for e in sender["post_eligibility"]])

    def test_cold_boundaries_timezone_and_new_clock_preserve_numbers(self):
        from src.core.projection_intelligence.sleeper_provider import freshness_state

        stamp = self.observed.astimezone(timezone(timedelta(hours=-4))).isoformat()
        for seconds, expected in (
            (3599.999999, "Fresh"),
            (3600, "Aging"),
            (21600 - 0.000001, "Aging"),
            (21600, "Stale"),
        ):
            diagnostics.diagnostic_store.clear()
            now = self.observed + timedelta(seconds=seconds)
            with (
                self.subTest(seconds=seconds),
                patch.object(diagnostics, "_now", return_value=now),
            ):
                row = diagnostics.team_diagnostics(
                    self.data, 1, self.service.snapshot()
                )
                self.assertEqual(row["evidence"]["projection_freshness"], [expected])
                self.assertEqual(freshness_state(stamp, now=now), expected)
                self.assertEqual(row["optimal_points"], 10)

    def test_failed_publication_preserves_head_and_recovers(self):
        head = self.service.snapshot()
        broken = deepcopy(self.f.f.source.payloads)
        broken[2] = [{"unexpected": "malformed optional source"}]
        with self.assertRaises((ValueError, RuntimeError)):
            self.service.publish_horizon(
                broken,
                data=self.data,
                league_id="league-1",
                season=2026,
                current_week=2,
            )
        self.assertIs(head, self.service.snapshot())
        row = diagnostics.team_diagnostics(self.data, 1, head)
        self.assertTrue(row["evidence"]["refresh"]["retained_publication"])
        self.assertEqual(row["optimal_points"], 10)
        self.f.publish(self.observed.isoformat())
        self.assertFalse(self.service.refresh_evidence(self.service.snapshot()))

    def test_legacy_refresh_failure_is_bound_to_requested_league(self):
        head = self.service.snapshot()
        for league in ("foreign", "league-1"):
            with self.subTest(league=league), self.assertRaises(ValueError):
                self.service.ingest_sleeper(
                    [{"unexpected": "malformed"}],
                    data=self.data,
                    league_id=league,
                    season=2026,
                    week=2,
                )
            self.assertIs(head, self.service.snapshot())
            evidence = self.service.refresh_evidence(head)
            self.assertEqual(bool(evidence), league == "league-1")
            if evidence:
                self.assertTrue(evidence["retained_publication"])

    def test_partial_coverage_preserves_independent_numeric_admission(self):
        snapshot = deepcopy(self.service.snapshot())
        del snapshot["players"]["b"]
        row = diagnostics.team_diagnostics(
            self.data, 1, snapshot, projection_reader=self.service
        )
        self.assertTrue(row["evidence"]["calculation_supported"])
        self.assertEqual(row["evidence"]["conclusion_state"], "unavailable")
        self.assertEqual(row["optimal_points"], 10)
        self.assertEqual(row["missing_projection_ids"], ["b"])
        self.assertFalse(row["positions"]["QB"]["surplus_assets"])

    def test_negative_display_zero_is_not_negative_arithmetic(self):
        from src.ui.roster_diagnostic_evidence import evidence_html

        facts = diagnostics.team_diagnostics(self.data, 1, self.service.snapshot())[
            "positions"
        ]["QB"]
        facts["remove_one"]["a"]["lineup_loss"] = -0.00001
        body = evidence_html(facts, self.data["teams"][0]["players"])
        self.assertIn("0.00 projected points", body)
        self.assertNotIn("-0.00", body)
        self.assertEqual(facts["remove_one"]["a"]["lineup_loss"], -0.00001)

    def test_superflex_full_package_has_unique_slot_assignments(self):
        self.data["league"]["roster_positions"] = [
            "QB",
            "SUPER_FLEX",
            "BN",
            "BN",
            "BN",
            "BN",
        ]
        self.f.publish(self.observed.isoformat())
        self.f.f.payload["assets_sent"] = ["a", "b"]
        result = self.package("Questionable")
        receiver = result["sides"]["partner"]
        assignments = receiver["post_lineup_assignments"]
        self.assertEqual({a["slot"] for a in assignments}, {"QB", "SUPER_FLEX"})
        self.assertEqual(len({a["player_id"] for a in assignments}), len(assignments))
        self.assertEqual(receiver["post_evidence"]["conclusion_state"], "provisional")

    def test_oversized_pool_is_guarded_before_solver(self):
        from src.core.trade_intelligence.models import TradeProposal

        self.data["teams"][0]["players"].extend(
            {"id": f"extra-{i}", "position": "QB", "status": "Active"}
            for i in range(2049)
        )
        with patch.object(
            diagnostics.SearchLineupMemo,
            "solve",
            side_effect=AssertionError("oversized solver entered"),
        ):
            row = diagnostics.package_diagnostics(
                self.data,
                TradeProposal(1, 2, (), (), "test"),
                self.service.snapshot(),
                {},
                {},
                projection_reader=self.service,
            )
        self.assertFalse(row["evidence"]["calculation_supported"])
        self.assertIsNone(row["sides"]["active"]["post_optimal_points"])

    def test_two_real_league_configurations_have_independent_source_ages(self):
        import json
        from pathlib import Path
        from tests import test_dynamic_needs as canonical

        leagues = json.loads(
            Path("tests/fixtures/dynamic_league_settings.json").read_text()
        )["leagues"]
        controls = []
        for i, league in enumerate(leagues):
            f = canonical.CanonicalDiagnosticTests()
            f.setUp()
            self.addCleanup(f.doCleanups)
            f.publish(
                [[("q1", "QB", 20), ("q2", "QB", 19)], [("q3", "QB", 18)]],
                league["roster_positions"],
                league=league["league_id"],
                scoring=league["scoring_settings"],
            )
            stamp = (self.observed - timedelta(hours=7 if i == 0 else 0)).isoformat()
            payload = {
                1: [
                    {
                        "player_id": pid,
                        "season": 2026,
                        "week": 1,
                        "player": {"position": "QB"},
                        "stats": {"pass_yd": 100},
                        "updated_at": stamp,
                    }
                    for pid in ("q1", "q2", "q3")
                ]
            }
            snap = f.service.publish_horizon(
                payload,
                data=f.data,
                league_id=league["league_id"],
                season=2026,
                current_week=1,
            )
            controls.append((f, snap))
        with patch.object(diagnostics, "_now", return_value=self.observed):
            for index in (0, 1, 0):
                f, snap = controls[index]
                row = diagnostics.team_diagnostics(
                    f.data, 1, snap, projection_reader=f.service
                )
                self.assertEqual(row["league_id"], leagues[index]["league_id"])
                self.assertEqual(
                    row["evidence"]["projection_freshness"],
                    ["Stale" if index == 0 else "Fresh"],
                )

    def test_warm_age_transition_does_not_solve_or_change_publication(self):
        snapshot = self.service.snapshot()
        original = deepcopy(snapshot)
        diagnostics.diagnostic_store.clear()
        with patch.object(diagnostics, "_now", return_value=self.observed):
            before = diagnostics.team_diagnostics(self.data, 1, snapshot)
            identity = diagnostics.diagnostic_identity(
                self.data, snapshot, include_qualification=True
            )
        with (
            patch.object(
                diagnostics, "_now", return_value=self.observed + timedelta(hours=6)
            ),
            patch.object(
                diagnostics,
                "_compute",
                side_effect=AssertionError("clock-only numerical recompute"),
            ),
        ):
            after = diagnostics.team_diagnostics(self.data, 1, snapshot)
            self.assertNotEqual(
                identity,
                diagnostics.diagnostic_identity(
                    self.data, snapshot, include_qualification=True
                ),
            )
        self.assertEqual(before["generation"], after["generation"])
        self.assertEqual(before["optimal_points"], after["optimal_points"])
        self.assertEqual(
            before["positions"]["QB"]["remove_one"],
            after["positions"]["QB"]["remove_one"],
        )
        self.assertEqual(snapshot, original)

    def test_clock_unknown_future_invalid_timezone_and_retrieval_only(self):
        snapshot = self.service.snapshot()
        for stamp in (
            None,
            "bad",
            "2026-01-01T00:00:00",
            (self.observed + timedelta(seconds=1)).isoformat(),
        ):
            with (
                self.subTest(stamp=stamp),
                patch.object(diagnostics, "_now", return_value=self.observed),
            ):
                altered = deepcopy(snapshot)
                for row in altered["players"].values():
                    row["source_timestamp"] = stamp
                result = diagnostics.team_diagnostics(self.data, 1, altered)
                self.assertIn("Unavailable", result["evidence"]["projection_freshness"])
                self.assertEqual(result["optimal_points"], 10)
        with patch.object(
            diagnostics, "_now", return_value=self.observed + timedelta(hours=7)
        ):
            before = diagnostics.team_diagnostics(self.data, 1, snapshot)
            copy = deepcopy(snapshot)
            copy["generated_at"] = (self.observed + timedelta(hours=7)).isoformat()
            copy["retrieved_at"] = copy["generated_at"]
            after = diagnostics.team_diagnostics(self.data, 1, copy)
            self.assertEqual(before["generation"], after["generation"])
            self.assertEqual(before["evidence"], after["evidence"])

    def test_http_consumers_age_on_warm_reads_and_recover_after_publication(self):
        for seconds, label in ((0, "Fresh"), (3600, "Aging"), (21600, "Stale")):
            with patch.object(
                diagnostics,
                "_now",
                return_value=self.observed + timedelta(seconds=seconds),
            ):
                for rid in (1, 2):
                    response = self.f.f.f.client.get(f"/teams/{rid}")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(label, response.text)
                response = self.f.f.evaluate()
                self.assertEqual(response.status_code, 200)
                result = response.json()["evaluation"]["dimensions"][
                    "roster_diagnostics"
                ]
                for side in result["sides"].values():
                    self.assertIn(label, side["evidence"]["projection_freshness"])
        self.service.begin_external_refresh()
        self.service.fail_external_refresh(RuntimeError("incomplete"))
        self.assertTrue(
            self.service.refresh_evidence(self.service.snapshot())[
                "retained_publication"
            ]
        )
        self.f.publish((self.observed + timedelta(hours=7)).isoformat())
        with patch.object(
            diagnostics, "_now", return_value=self.observed + timedelta(hours=7)
        ):
            row = diagnostics.team_diagnostics(self.data, 1, self.service.snapshot())
            self.assertEqual(row["evidence"]["projection_freshness"], ["Fresh"])
            self.assertFalse(row["evidence"]["refresh"])

    def test_failed_refresh_scope_age_and_home_cached_explanation(self):
        from services import home_trade_opportunities as ideas

        with patch.object(diagnostics, "_now", return_value=self.observed):
            identity = ideas.source_identity(self.data)
            self.service.begin_external_refresh()
            self.service.fail_external_refresh(RuntimeError("incomplete preparation"))
            self.assertNotEqual(identity, ideas.source_identity(self.data))
            row = diagnostics.team_diagnostics(self.data, 1, self.service.snapshot())
            self.assertEqual(row["evidence"]["projection_freshness"], ["Fresh"])
            self.assertEqual(row["evidence"]["conclusion_state"], "provisional")
        foreign = deepcopy(self.service.snapshot())
        foreign["league_id"] = "foreign"
        self.assertFalse(self.service.refresh_evidence(foreign))
        with patch.object(
            diagnostics, "_now", return_value=self.observed + timedelta(hours=7)
        ):
            row = diagnostics.team_diagnostics(self.data, 1, self.service.snapshot())
            self.assertIn("Stale", row["evidence"]["projection_freshness"])
            self.assertTrue(row["evidence"]["refresh"]["retained_publication"])
        self.service.fail_external_refresh(
            RuntimeError("foreign attempt"), league_id="foreign"
        )
        self.assertFalse(self.service.refresh_evidence(self.service.snapshot()))
