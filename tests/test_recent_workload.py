"""Matched retained-source → shared read model → actual dossier/API controls."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.global_evidence import player_usage_evidence
from src.core.data_platform.global_evidence import GlobalEvidenceStore, GlobalFact
from src.core.data_platform.global_usage import player_usage
from tests import test_player_api as api_fixtures

STAMP = "2026-10-20T00:00:00Z"
NOW = "2026-11-15T12:00:00Z"


def fact(week, targets, carries, **changes):
    date = datetime(2026, 9, 6, 17, tzinfo=timezone.utc) + timedelta(weeks=week - 1)
    row = GlobalFact(
        "production",
        "sleeper:player one",
        "nflverse",
        f"g{week}:id",
        date.isoformat(),
        None,
        dict(
            game_id=f"g{week}",
            season_type="REG",
            team="BUF",
            opponent="NYJ",
            rec_tgt=targets,
            rush_att=carries,
        ),
        season=2026,
        week=week,
    )
    return replace(row, **changes)


def seed(store):
    rows = [fact(w, 2 if w <= 3 else 5, 12 if w <= 3 else 6) for w in range(1, 7)]
    store.publish(rows, retrieved_at=STAMP)
    return rows


def data(league="league-1"):
    value = api_fixtures.fixture_data()
    value["league"].update(league_id=league, season="2026")
    value["nfl_state"] = dict(season="2026", season_type="regular", week=7)
    value["scoring_settings"] = {"rec": 1}
    return value


class RecentWorkloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.store = GlobalEvidenceStore(Path(self.tmp) / "global.sqlite3")
        self.rows = seed(self.store)

    def usage(self, **kwargs):
        return player_usage(
            self.store, "player one", season=2026, as_of=NOW, through_week=6, **kwargs
        )

    def comparison(self):
        return self.usage()["recent_workload"]

    def test_increase_decrease_dates_and_exact_samples(self):
        r = self.comparison()
        self.assertEqual(r["status"], "supported")
        self.assertEqual(
            r["metrics"]["targets"],
            dict(
                status="supported",
                previous_average=2,
                recent_average=5,
                difference=3,
                previous_count=3,
                recent_count=3,
            ),
        )
        self.assertEqual(r["metrics"]["carries"]["difference"], -6)
        self.assertEqual([g["week"] for g in r["previous"]], [1, 2, 3])
        self.assertEqual([g["week"] for g in r["recent"]], [4, 5, 6])
        self.assertTrue(r["recent"][0]["date"].startswith("2026-09-27"))

    def test_explicit_zero_and_unchanged_not_missing(self):
        self.store.publish(
            [
                replace(r, values={**r.values, "rush_att": 0, "rec_tgt": 0})
                for r in self.rows
            ],
            retrieved_at="2026-10-21T00:00:00Z",
        )
        self.assertEqual(self.comparison()["metrics"]["targets"]["difference"], 0)
        self.assertEqual(self.comparison()["metrics"]["carries"]["recent_average"], 0)

    def test_missing_stat_does_not_shift_sample_or_hide_other_metric(self):
        self.store.publish(
            [replace(self.rows[4], values={**self.rows[4].values, "rec_tgt": None})],
            retrieved_at="2026-10-21T00:00:00Z",
        )
        r = self.comparison()
        self.assertEqual(r["metrics"]["targets"]["reasons"], ["stat_fields_missing"])
        self.assertEqual(r["metrics"]["carries"]["difference"], -6)
        self.assertEqual([g["week"] for g in r["recent"]], [4, 5, 6])

    def test_negative_invalid_count_is_not_a_zero(self):
        self.store.publish(
            [replace(self.rows[4], values={**self.rows[4].values, "rec_tgt": -1})],
            retrieved_at="2026-10-21T00:00:00Z",
        )
        self.assertEqual(
            self.comparison()["metrics"]["targets"]["status"], "unavailable"
        )

    def test_missing_game_is_not_omitted_to_manufacture_trend(self):
        self.store.publish([fact(8, 50, 50)], retrieved_at=STAMP)
        r = player_usage(
            self.store, "player one", season=2026, as_of=NOW, through_week=8
        )["recent_workload"]
        self.assertIn("game_observations_missing", r["reasons"])
        self.assertEqual(r["unobserved_weeks"], [7])
        self.assertEqual(r["metrics"], {})

    def test_trailing_missing_game_blocks_stale_six_game_comparison(self):
        r = player_usage(
            self.store, "player one", season=2026, as_of=NOW, through_week=7
        )["recent_workload"]
        self.assertEqual(r["unobserved_weeks"], [7])
        self.assertEqual(r["metrics"], {})

    def test_missing_is_not_invented_bye_in_partial_schedule(self):
        self.store.publish(
            [
                GlobalFact(
                    "schedule",
                    "nfl-game:other",
                    "nflverse",
                    "other",
                    self.rows[0].effective_at,
                    None,
                    dict(
                        game_id="other",
                        home_team="NYJ",
                        away_team="KC",
                        game_type="REG",
                    ),
                    season=2026,
                    week=7,
                )
            ],
            retrieved_at=STAMP,
        )
        self.test_trailing_missing_game_blocks_stale_six_game_comparison()

    def test_only_complete_schedule_shape_can_establish_bye(self):
        # Existing canonical 32-team complete-schedule rule, not absence inference.
        teams = ["BUF"] + [f"T{i}" for i in range(31)]
        scheduled = []
        for week in range(1, 18):
            for i in range(0, 32, 2):
                if week == (7 if i == 0 else 1 + i // 2):
                    continue
                game = f"{week}-{i}"
                scheduled.append(
                    GlobalFact(
                        "schedule",
                        f"nfl-game:{game}",
                        "nflverse",
                        game,
                        self.rows[0].effective_at,
                        None,
                        dict(
                            game_id=game,
                            home_team=teams[i],
                            away_team=teams[i + 1],
                            game_type="REG",
                        ),
                        season=2026,
                        week=week,
                    )
                )
        self.store.publish(scheduled, retrieved_at=STAMP)
        r = player_usage(
            self.store, "player one", season=2026, as_of=NOW, through_week=7
        )["recent_workload"]
        self.assertEqual(r["status"], "supported")
        self.assertNotIn("unobserved_weeks", r)

    def test_revision_replaces_prior_result_and_historical_query_does_not_see_it(self):
        before = self.comparison()["generation"]
        self.store.publish(
            [replace(self.rows[-1], values={**self.rows[-1].values, "rec_tgt": 11})],
            retrieved_at="2026-10-22T00:00:00Z",
        )
        self.assertEqual(self.comparison()["metrics"]["targets"]["recent_average"], 7)
        self.assertNotEqual(self.comparison()["generation"], before)
        old = player_usage(
            self.store,
            "player one",
            season=2026,
            as_of="2026-10-21T00:00:00Z",
            through_week=6,
        )["recent_workload"]
        self.assertEqual(old["metrics"]["targets"]["recent_average"], 5)

    def test_duplicate_same_game_is_one_observation(self):
        self.store.publish(
            [replace(self.rows[-1], source_record_id="alternate-record")],
            retrieved_at=STAMP,
        )
        self.assertEqual(self.comparison()["eligible_observations"], 6)
        self.assertEqual(self.comparison()["metrics"]["targets"]["recent_average"], 5)

    def test_conflicting_duplicate_does_not_select_a_statistic(self):
        self.store.publish(
            [
                replace(
                    self.rows[-1],
                    source_record_id="alternate-record",
                    values={**self.rows[-1].values, "rec_tgt": 99},
                )
            ],
            retrieved_at=STAMP,
        )
        r = self.comparison()
        self.assertEqual(
            r["metrics"]["targets"]["reasons"], ["conflicting_stat_records"]
        )
        self.assertEqual(r["metrics"]["carries"]["recent_average"], 6)

    def test_tied_source_revisions_are_not_resolved_by_fingerprint(self):
        self.store.publish(
            [replace(self.rows[-1], values={**self.rows[-1].values, "rec_tgt": 99})],
            retrieved_at=STAMP,
        )
        self.assertEqual(
            self.comparison()["metrics"]["targets"]["reasons"],
            ["conflicting_stat_records"],
        )

    def test_insufficient_sample_keeps_totals_and_records(self):
        r = player_usage(
            self.store, "player one", season=2026, as_of=NOW, through_week=5
        )
        self.assertEqual(len(r["games"]), 5)
        self.assertEqual(r["targets"], 16)
        self.assertIn("six_observations_not_available", r["recent_workload"]["reasons"])

    def test_live_future_postseason_other_season_and_unconfirmed_excluded(self):
        extra = [
            fact(7, 99, 99),
            fact(6, 99, 99, season=2025, source_record_id="old"),
            fact(
                6,
                99,
                99,
                values={**self.rows[-1].values, "season_type": "POST"},
                source_record_id="post",
            ),
            fact(
                6,
                99,
                99,
                effective_at="2026-12-01T00:00:00Z",
                source_record_id="future",
            ),
        ]
        self.store.publish(extra, retrieved_at=STAMP)
        self.assertEqual(self.comparison()["metrics"]["targets"]["recent_average"], 5)
        unknown = player_usage(self.store, "player one", season=2026, as_of=NOW)[
            "recent_workload"
        ]
        self.assertIn("completed_week_boundary_unknown", unknown["reasons"])

    def test_unknown_game_type_blocks_unproven_comparison(self):
        self.store.publish(
            [
                fact(
                    1,
                    5,
                    5,
                    values={**self.rows[0].values, "season_type": None},
                    source_record_id="unknown",
                )
            ],
            retrieved_at=STAMP,
        )
        self.assertIn("game_type_unknown", self.comparison()["reasons"])

    def test_transfer_uses_historical_team_not_catalog_and_qualifies(self):
        self.store.publish(
            [replace(r, values={**r.values, "team": "KC"}) for r in self.rows[3:]],
            retrieved_at="2026-10-21T00:00:00Z",
        )
        r = self.comparison()
        self.assertEqual(r["qualifications"], ["teams_changed"])
        self.assertEqual(r["recent"][0]["team"], "KC")
        self.assertEqual(r["previous"][0]["team"], "BUF")

    def test_no_hindsight_before_first_retrieval(self):
        r = player_usage(
            self.store,
            "player one",
            season=2026,
            as_of="2026-10-19T00:00:00Z",
            through_week=6,
        )
        self.assertEqual(r["games"], [])
        self.assertEqual(r["recent_workload"]["metrics"], {})

    def test_shared_updates_new_game_and_failure_preservation_across_leagues(self):
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=self.store
        ):
            leagues = [data("a"), data("b")]
            for d in leagues:
                d["nfl_state"]["week"] = 8

            def get(d):
                return player_usage_evidence(
                    "player one", d, expected_league_id=d["league"]["league_id"]
                )

            self.assertIn(
                "game_observations_missing",
                get(leagues[0])["recent_workload"]["reasons"],
            )
            self.store.publish([fact(7, 8, 3)], retrieved_at="2026-10-26T00:00:00Z")
            results = [get(d) for d in leagues]
            self.assertEqual(
                results[0]["recent_workload"]["metrics"],
                results[1]["recent_workload"]["metrics"],
            )
            self.assertEqual(
                results[0]["recent_workload"]["generation"],
                results[1]["recent_workload"]["generation"],
            )
            self.assertEqual(
                results[0]["recent_workload"]["metrics"]["targets"]["recent_average"], 6
            )
            self.store.record_source_check(
                "nflverse/production/2026",
                source_identity=None,
                checked_at="2026-11-01T00:00:00Z",
                status="failed",
                details={"reason": "source_unavailable"},
            )
            self.assertEqual(
                get(leagues[0])["recent_workload"]["metrics"],
                results[0]["recent_workload"]["metrics"],
            )
            self.assertEqual(get(leagues[0])["source_check"]["status"], "failed")
            with self.assertRaises(ValueError):
                player_usage_evidence("player one", leagues[0], expected_league_id="b")
            past = player_usage_evidence(
                "player one",
                leagues[0],
                expected_league_id="a",
                as_of="2026-10-25T00:00:00Z",
            )
            self.assertIsNone(past["source_check"])
            self.assertEqual(past["recent_workload"]["metrics"], {})

    def test_read_only_derivation_does_not_retain_duplicate_payload(self):
        before = self.store.path.read_bytes()
        for _ in range(12):
            self.usage()
        self.assertEqual(before, self.store.path.read_bytes())


class RecentWorkloadRenderedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.store = GlobalEvidenceStore(Path(self.tmp) / "global.sqlite3")
        self.rows = seed(self.store)
        self.enterContext(
            patch(
                "services.global_evidence.retained_global_evidence",
                return_value=self.store,
            )
        )
        self.fixture = api_fixtures.PlayerApiContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.client.close)
        self.fixture.data.update(data())
        self.download = self.enterContext(
            patch(
                "src.core.data_platform.source_snapshot.download_snapshot",
                side_effect=AssertionError("No acquisition on render"),
            )
        )

    def page(self):
        r = self.fixture.client.get("/players/player%20one?front_office=1")
        self.assertEqual(r.status_code, 200)
        return r.text

    def test_actual_dossier_and_api_match_retained_source_values(self):
        html = self.page()
        self.assertIn("Targets increased from 2 to 5 per observed game.", html)
        self.assertIn("Carries decreased from 12 to 6 per observed game.", html)
        self.assertIn("Difference: +3 per observed game.", html)
        self.assertIn("Sep 6 – Sep 20, 2026 UTC", html)
        self.assertIn("Game samples and sources", html)
        api = self.fixture.client.get("/api/players/player%20one/intelligence").json()
        self.assertEqual(
            api["canonical_evidence"]["usage"]["recent_workload"]["metrics"]["targets"][
                "recent_average"
            ],
            5,
        )
        self.download.assert_not_called()

    def test_reload_reflects_correction_and_failed_refresh_without_reevaluation(self):
        self.assertIn("Targets increased from 2 to 5", self.page())
        self.store.publish(
            [replace(self.rows[-1], values={**self.rows[-1].values, "rec_tgt": 11})],
            retrieved_at="2026-10-22T00:00:00Z",
        )
        self.assertIn("Targets increased from 2 to 7", self.page())
        self.store.record_source_check(
            "nflverse/production/2026",
            source_identity=None,
            checked_at="2026-11-01T00:00:00Z",
            status="failed",
            details={},
        )
        html = self.page()
        self.assertIn("Targets increased from 2 to 7", html)
        self.assertIn("latest source update did not complete", html)

    def test_missing_stat_withholds_only_affected_result_and_zero_renders(self):
        self.store.publish(
            [
                replace(
                    self.rows[-1],
                    values={**self.rows[-1].values, "rec_tgt": None, "rush_att": 0},
                )
            ],
            retrieved_at="2026-10-22T00:00:00Z",
        )
        html = self.page()
        self.assertIn("Targets comparison unavailable.", html)
        self.assertNotIn("Targets increased from", html)
        self.assertIn("Carries decreased from 12 to 4", html)
        self.assertIn("Targets: Unknown", html)
        self.assertIn("Carries: 0", html)

    def test_unknown_boundary_keeps_usage_records_without_claiming_completed_samples(
        self,
    ):
        self.fixture.data["nfl_state"]["season_type"] = "post"
        html = self.page()
        self.assertIn("completed NFL week is not confirmed", html)
        self.assertNotIn("Targets increased from", html)
        self.assertIn("Retained usage totals", html)
