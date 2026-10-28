import copy
from datetime import timedelta
import unittest
from unittest.mock import patch

from services.matchup_season import season_week_view
from src.core.intelligence.lineup_review import (
    review_lineup,
    player_identity,
    prepared_games,
)
from tests.lineup_review_fixture import prepared, http


class LineupReviewTests(unittest.TestCase):
    def side(self, data, service, week=8):
        return season_week_view(data, week, service)["groups"]["1"][0]

    def review(self, data, service, now, *, week=8):
        side = self.side(data, service, week)
        snap = service.week_snapshot(week, generation_snapshot=service.snapshot())
        return review_lineup(
            data,
            side,
            snap,
            data["team_strength"],
            week=week,
            observed_at=data["season_matchups"]["observed_at"],
            now=now,
        )

    def test_submitted_stays_actual_while_legal_optimum_includes_bench_qb(self):
        data, service, now = prepared(self, empty=True)
        before = copy.deepcopy(data)
        side = self.side(data, service)
        self.assertEqual(side["lineup"][0]["player_id"], "0")
        self.assertIsNone(side["lineup"][0]["projection"])
        self.assertEqual(side["projection"], 37)
        self.assertEqual(side["empty_slots"], 1)
        self.assertEqual(side["optimal"]["projected_points"], 62)
        self.assertIn("1-bq", [e["asset_id"] for e in side["optimal"]["entries"]])
        review = self.review(data, service, now)
        self.assertTrue(review["actionable"], review)
        self.assertEqual(review["gain"], 25)
        self.assertEqual(data, before)

    def test_positive_and_true_zero_not_missing(self):
        data, service, now = prepared(self)
        review = self.review(data, service, now)
        self.assertTrue(review["actionable"], review)
        self.assertEqual(review["gain"], 15)
        data, service, now = prepared(self, points={"q": 25, "bq": 10})
        self.assertEqual(self.review(data, service, now)["state"], "no_improvement")
        data, service, now = prepared(self, points={"q": 0})
        self.assertTrue(self.review(data, service, now)["actionable"])
        self.assertEqual(self.side(data, service)["lineup"][0]["projection"], 0)
        data, service, now = prepared(self, points={"q": None})
        self.assertFalse(self.review(data, service, now)["actionable"])
        self.assertIsNone(self.side(data, service)["projection"])

    def test_started_and_unknown_games_suppress_without_mutating_optimum(self):
        data, service, now = prepared(self)
        profile = data["team_strength"]
        optimal = copy.deepcopy(self.side(data, service)["optimal"])
        for kickoff in ((now - timedelta(seconds=1)).isoformat(), None):
            profile["lineup_review_schedule"]["games"]["8:BUF"]["kickoff"] = kickoff
            review = self.review(data, service, now)
            self.assertFalse(review["actionable"])
            self.assertEqual(review["state"], "informational")
            self.assertEqual(self.side(data, service)["optimal"], optimal)

    def test_stale_future_and_unsupported_settings_remain_informational(self):
        data, service, now = prepared(self)
        self.assertFalse(
            self.review(data, service, now + timedelta(minutes=16))["actionable"]
        )
        self.assertFalse(self.review(data, service, now, week=9)["actionable"])
        for setting, value in [
            ("best_ball", 1),
            ("best_ball", None),
            ("sub_start_time_eligibility", 1),
        ]:
            data["league"]["settings"][setting] = value
            self.assertFalse(self.review(data, service, now)["actionable"])

    def test_row_conflict_withheld_in_actual_rendered_http(self):
        data, service, _ = prepared(self)
        original = service.week_snapshot

        def conflict(week, **kwargs):
            row = copy.deepcopy(original(week, **kwargs))
            row["players"]["1-q"]["week"] = 9
            return row

        with patch.object(service, "week_snapshot", side_effect=conflict):
            body = http(self, data, service).get("/matchups/1?week=8").text
            self.assertNotIn("Higher-projected lineup available", body)
            self.assertIn("does not match the selected week", body)
            side = self.side(data, service)
            self.assertIsNone(side["lineup"][0]["projection"])

    def test_names_exact_slots_and_no_raw_ids_in_optimal_disclosure(self):
        data, service, _ = prepared(self)
        client = http(self, data, service)
        body = client.get("/matchups/1?week=8").text
        self.assertIn("Higher-projected lineup available", body)
        self.assertIn("Example BQ 1 (QB)", body)
        self.assertNotIn("· 1-bq</li>", body)
        self.assertIn("Submitted starters", body)
        self.assertIn("Review in Sleeper", body)
        self.assertEqual(client.get("/static/lineup-review.js").status_code, 200)
        data["players"]["1-bq"]["player_id"] = "different"
        body = client.get("/matchups/1?week=8").text
        self.assertNotIn("Higher-projected lineup available", body)
        self.assertIn("Player name not verified", body)

    def test_current_membership_only_alert_and_league_isolation(self):
        data, service, _ = prepared(self)
        client = http(self, data, service, membership_league="foreign")
        self.assertNotIn(
            "Higher-projected lineup available", client.get("/matchups?week=8").text
        )
        _, other, _ = prepared(self, league_id="lineup-B")
        self.assertIsNone(self.side(data, other)["optimal"])

    def test_future_uses_future_points_and_does_not_claim_actionability(self):
        data, service, _ = prepared(self)
        current, future = self.side(data, service), self.side(data, service, 9)
        self.assertEqual(
            future["optimal"]["projected_points"]
            - current["optimal"]["projected_points"],
            8,
        )
        self.assertFalse(future["lineup_review"]["actionable"])
        self.assertEqual(future["lineup"][0]["projection"], 12)

    def test_reads_add_no_optimizer_provider_storage_or_discovery(self):
        data, service, _ = prepared(self)
        before = copy.deepcopy(data)
        with (
            patch(
                "src.core.trade_intelligence.lineup.optimal_legal_lineup",
                side_effect=AssertionError("solver read"),
            ),
            patch(
                "src.core.intelligence.team_strength.prepare_for_data",
                side_effect=AssertionError("prepare read"),
            ),
        ):
            for _ in range(8):
                self.assertTrue(self.side(data, service)["lineup_review"]["actionable"])
        self.assertEqual(data, before)

    def test_conflicting_schedule_and_identity_never_substitute(self):
        self.assertFalse(
            player_identity({"x": {"full_name": "Wrong", "player_id": "y"}}, "x")[
                "identity_available"
            ]
        )
        facts = [
            dict(
                family="schedule",
                provider="nflverse",
                season=2026,
                week=8,
                fingerprint=str(i),
                values=dict(
                    game_type="REG",
                    home_team="BUF",
                    away_team="NYJ",
                    kickoff=f"2026-10-29T{hour}:00:00Z",
                ),
            )
            for i, hour in enumerate(("10", "11"))
        ]
        self.assertIsNone(prepared_games(facts, 2026)["games"]["8:BUF"])

    def test_lock_only_affects_changed_players(self):
        data, service, now = prepared(self)
        # An unchanged locked RB stays in the same source slot. Other players
        # may still be changed before their own kickoff.
        for team in data["teams"]:
            for player in team["players"]:
                if player["id"].endswith("-r"):
                    player["team"] = "KC"
                    data["players"][player["id"]]["team"] = "KC"
        # Publication identity still has BUF, so use a separate schedule for
        # the source team only after republishing exact team evidence.
        # The direct pure review checks every moved player independently.
        side = self.side(data, service)
        snap = copy.deepcopy(
            service.week_snapshot(8, generation_snapshot=service.snapshot())
        )
        snap["players"]["1-r"]["team"] = "KC"
        data["team_strength"]["lineup_review_schedule"]["games"]["8:KC"] = {
            "kickoff": (now - timedelta(hours=1)).isoformat(),
            "reference": "played-game",
        }
        result = review_lineup(
            data,
            side,
            snap,
            data["team_strength"],
            week=8,
            observed_at=data["season_matchups"]["observed_at"],
            now=now,
        )
        self.assertTrue(result["actionable"], result)

    def test_unknown_name_starter_transition_and_ir_suppress(self):
        for change in ("name", "starter", "ir"):
            data, service, now = prepared(self)
            if change == "name":
                data["players"].pop("1-bq")
            if change == "starter":
                next(p for p in data["teams"][0]["players"] if p["id"] == "1-q")[
                    "starter_index"
                ] = 3
            if change == "ir":
                next(p for p in data["teams"][0]["players"] if p["id"] == "1-bq")[
                    "roster_slot"
                ] = "IR"
            self.assertFalse(self.review(data, service, now)["actionable"])

    def test_bad_leaf_generation_and_future_row_provenance_cannot_display(self):
        for field, value in [
            ("horizon_generation", "foreign"),
            ("season", 2025),
            ("week", 10),
            ("scoring_settings", {"rush_yd": 99}),
            ("projection_snapshot_id", "foreign"),
        ]:
            data, service, _ = prepared(self)
            original = service.week_snapshot
            with patch.object(
                service,
                "week_snapshot",
                side_effect=lambda week, **kw: {**original(week, **kw), field: value},
            ):
                self.assertIsNone(self.side(data, service, 9)["projection"])
        data, service, _ = prepared(self)
        original = service.week_snapshot

        def conflict(week, **kw):
            snap = copy.deepcopy(original(week, **kw))
            snap["players"]["1-bq"]["season"] = 2025
            return snap

        with patch.object(service, "week_snapshot", side_effect=conflict):
            side = self.side(data, service, 9)
            self.assertEqual(side["projection"], 55)
            self.assertIsNone(side["optimal"])

    def test_flex_superflex_and_repeated_slots_remain_legal(self):
        data, service, now = prepared(self)
        side = self.side(data, service)
        self.assertTrue(self.review(data, service, now)["actionable"])
        self.assertEqual(
            {e["slot"] for e in side["optimal"]["entries"]},
            {"QB", "RB", "FLEX", "SUPER_FLEX"},
        )
        self.assertEqual(len({e["asset_id"] for e in side["optimal"]["entries"]}), 4)

    def test_schedule_scope_and_manual_rules_fail_closed(self):
        for mutation in ("missing", "season", "method", "bestball", "autosub"):
            data, service, now = prepared(self)
            if mutation == "missing":
                data["team_strength"]["lineup_review_schedule"] = None
            if mutation == "season":
                data["team_strength"]["lineup_review_schedule"]["season"] = 2025
            if mutation == "method":
                data["team_strength"]["lineup_review_schedule"]["method"] = "unknown"
            if mutation == "bestball":
                data["league"]["settings"]["best_ball"] = 1
            if mutation == "autosub":
                data["league"]["settings"]["sub_start_time_eligibility"] = 1
            self.assertFalse(self.review(data, service, now)["actionable"])

    def test_failed_refresh_keeps_last_valid_numbers_but_no_actionable_alert(self):
        data, service, _ = prepared(self)
        previous = self.side(data, service)
        with patch.object(
            service, "refresh_evidence", return_value={"retained_publication": True}
        ):
            result = self.side(data, service)
        self.assertEqual(result["projection"], previous["projection"])
        self.assertEqual(result["optimal"], previous["optimal"])
        self.assertFalse(result["lineup_review"]["actionable"])
        self.assertIn("refresh did not complete", result["lineup_review"]["reason"])

    def test_real_account_http_my_team_positive_and_other_franchise_suppression(self):
        from tests.lineup_review_fixture import authenticated_prepared

        f, data, service, _ = authenticated_prepared(self)
        response = f.f.f.client.get("/teams/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Higher-projected lineup available", response.text)
        self.assertIn("+25.00 projected points", response.text)
        self.assertLess(
            response.text.index("Higher-projected lineup available"),
            response.text.index('id="full-roster"'),
        )
        other = f.f.f.client.get("/teams/2")
        self.assertEqual(other.status_code, 200)
        self.assertNotIn("Higher-projected lineup available", other.text)
        for path in ("/matchups?week=8", "/matchups/1?week=8"):
            response = f.f.f.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.text.count("Higher-projected lineup available"), 1
            )

    def test_current_nfl_team_and_eligibility_transitions_suppress_alert(self):
        for mutation in ("team", "fantasy_positions", "status"):
            data, service, now = prepared(self)
            if mutation == "team":
                for player in data["teams"][0]["players"]:
                    if player["id"] == "1-bq":
                        player["team"] = "KC"
                data["players"]["1-bq"]["team"] = "KC"
                data["team_strength"]["lineup_review_schedule"]["games"]["8:KC"] = {
                    "kickoff": (now - timedelta(hours=1)).isoformat(),
                    "reference": "started-game",
                }
            elif mutation == "fantasy_positions":
                data["players"]["1-bq"]["fantasy_positions"] = ["TE"]
            else:
                data["players"]["1-bq"]["injury_status"] = "Out"
            review = self.review(data, service, now)
            self.assertFalse(review["actionable"], review)
            self.assertEqual(review["state"], "informational")

    def test_non_regular_schedule_cannot_verify_regular_week_locks(self):
        fact = dict(
            family="schedule",
            provider="nflverse",
            season=2026,
            week=8,
            fingerprint="wrong-phase",
            values=dict(
                game_type="PRE",
                home_team="BUF",
                away_team="NYJ",
                kickoff="2026-10-29T20:00:00Z",
            ),
        )
        self.assertEqual(prepared_games([fact], 2026)["games"], {})
