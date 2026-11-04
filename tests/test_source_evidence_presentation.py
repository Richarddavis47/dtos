"""High-cardinality canonical publisher and actual authenticated HTML evidence."""

from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tests import test_roster_diagnostic_aging as fixtures
from src.core.intelligence import roster_diagnostics as diagnostics


def high_cardinality(count, capture):
    f = fixtures.DiagnosticAgingTests()
    f.setUp()
    data, service = f.data, f.service
    data["league"].update(
        {
            k: capture[k]
            for k in ("league_id", "name", "roster_positions", "scoring_settings")
        }
    )
    lid = capture["league_id"]
    boundary = f.f.f.f
    boundary.store.upsert_membership(
        boundary.account_id, data["league"], "fixture-user", 1, "Team 1", "active"
    )
    boundary.store.activate(boundary.account_id, lid)
    source = f.f.f.source
    for i in range(count - len(source.points)):
        pid = "source-" + str(i)
        source.points[pid] = 1
        data["players"][pid] = {
            "id": pid,
            "full_name": "Source player " + str(i),
            "position": "QB",
            "team": "NYJ",
            "status": "Active",
        }
    source.payloads = {
        week: [
            {
                "player_id": pid,
                "season": 2026,
                "week": week,
                "stats": {"pass_yd": points},
                "player": {"position": "QB"},
            }
            for pid, points in source.points.items()
        ]
        for week in (2, 3, 4, 5)
    }
    for rows in source.payloads.values():
        for i, row in enumerate(rows):
            row["updated_at"] = (f.observed - timedelta(seconds=i * 90)).isoformat()
    service.publish_horizon(
        source.payloads, data=data, league_id=lid, season=2026, current_week=2
    )
    from src.core.intelligence.team_strength import prepare_for_data

    with patch("services.global_evidence.retained_global_evidence", return_value=None):
        prepare_for_data(service, data)
    return f


class SourceEvidencePresentationTests(unittest.TestCase):
    def test_complete_high_cardinality_provenance_is_secondary(self):
        captures = json.loads(
            Path("tests/fixtures/dynamic_league_settings.json").read_text()
        )["leagues"]
        for count, capture in zip((238, 200), captures):
            f = high_cardinality(count, capture)
            try:
                with patch.object(diagnostics, "_now", return_value=f.observed):
                    row = diagnostics.team_diagnostics(f.data, 1, f.service.snapshot())
                    self.assertEqual(len(row["evidence"]["source_observations"]), count)
                    response = f.f.f.f.client.get("/teams/1")
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(
                        '<details class="diagnostic-source-provenance"><summary>Detailed source provenance</summary>',
                        response.text,
                    )
                    for stamp in row["evidence"]["source_observations"]:
                        self.assertIn(stamp, response.text)
                    self.assertIn(
                        str(count) + " distinct source observations", response.text
                    )
                    self.assertLess(
                        response.text.index("removing this player costs"),
                        response.text.index("Detailed source provenance"),
                    )
            finally:
                f.doCleanups()

    def test_bounded_summary_and_complete_original_clocks(self):
        from copy import deepcopy
        from datetime import datetime, timezone
        from src.ui.source_provenance import source_presentation

        now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        for stamps, state in (
            (["2026-10-15T11:59:59+00:00"], "Fresh"),
            (["2026-10-15T11:00:00+00:00"], "Aging"),
            (["2026-10-15T06:00:00+00:00"], "Stale"),
            (["Unavailable", "bad", "2026-10-16T00:00:00+00:00"], "Unavailable"),
            ([], "Unavailable"),
        ):
            for retained in (False, True):
                evidence = dict(
                    source_observations=stamps,
                    projection_freshness=[state],
                    conclusion_state="current"
                    if state == "Fresh" and not retained
                    else "provisional",
                    refresh={"retained_publication": retained},
                )
                before = deepcopy(evidence)
                summary, details = source_presentation(
                    evidence, {"projection_snapshot_id": "exact-source"}, now=now
                )
                self.assertEqual(evidence, before)
                self.assertLess(len(summary), 600)
                self.assertIn({"Fresh": "observations are recent", "Aging": "at least an hour old",
                               "Stale": "at least six hours old", "Unavailable": "update times are not verified"}[state], summary)
                self.assertIn(state, details)
                for stamp in stamps:
                    self.assertIn(stamp, details)
                self.assertIn("exact-source", details)
                self.assertEqual("latest refresh did not complete" in summary, retained)
                if state == "Unavailable":
                    self.assertIn("provenance is incomplete", summary)

    def test_named_scenarios_and_genuine_negative_zero(self):
        from src.ui.roster_diagnostic_evidence import evidence_html

        html = evidence_html(
            {
                "remove_one": {
                    "a": {
                        "lineup_loss": -0.000001,
                        "replacement_names": ["Quarterback B"],
                    }
                },
                "evidence": {
                    "projection_freshness": ["Fresh"],
                    "conclusion_state": "current",
                },
            },
            [{"id": "a", "name": "Quarterback A"}],
        )
        self.assertIn("Quarterback A", html)
        self.assertIn("Quarterback B", html)
        self.assertIn("0.00 projected points", html)
        self.assertNotIn("-0.00", html)
        self.assertNotIn("remove_one", html)
