"""Source-backed record/PF, qualification and real presentation publication."""

import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.matchup_season import prepare_season_matchups
from services.standings import (
    record_fields,
    standings_order,
    playoff_position,
    reconstructed_movement,
)
from src.core.history_context.results import standing_points
from src.core.league_runtime.context import source_generations
from src.core.league_runtime.manager import LeagueRuntime
from src.core.projection_intelligence.service import ProjectionService
from src.ui.badges import official_ranks
from src.ui.standings import render_standings, completed_streak

SOURCES = json.loads(Path("tests/fixtures/standings_source_2132.json").read_text())[
    "leagues"
]


def source_fixture(index=0):
    source = copy.deepcopy(SOURCES[index])
    data = {"league": source["league"], "week": 5, "players": {}, "teams": []}
    data["league"]["sport"] = "nfl"
    for team in source["rosters"]:
        settings = team.pop("settings")
        data["teams"].append(
            dict(
                team,
                **record_fields(settings),
                division=settings.get("division"),
                points_for=standing_points(settings, "fpts"),
                points_against=standing_points(settings, "fpts_against"),
                players=[],
            )
        )
    prepare(data, source["weeks"])
    return data


def prepare(data, weeks, observed="source fixture"):
    async def fetch(path):
        value = weeks.get(path.rsplit("/", 1)[-1])
        if isinstance(value, Exception):
            raise value
        return value

    data["season_matchups"] = asyncio.run(
        prepare_season_matchups(
            data["league"],
            data["week"],
            weeks.get(str(data["week"])) or [],
            fetch,
            observed_at=observed,
        )
    )
    data["matchups"] = weeks.get(str(data["week"])) or []


def controlled(rows=None, **settings):
    data = source_fixture()
    data["teams"] = [
        dict(
            roster_id=i + 1,
            team_name=f"Franchise {i + 1}",
            players=[],
            wins=w,
            losses=losses,
            ties=t,
            points_for=pf,
            points_against=999 - i,
        )
        for i, (w, losses, t, pf) in enumerate(
            rows or [(3, 1, 0, 100), (2, 2, 0, 110), (1, 3, 0, 90), (0, 4, 0, 80)]
        )
    ]
    data["league"]["settings"].update(
        num_teams=len(data["teams"]), playoff_teams=2, **settings
    )
    return data


class StandingsPositioningTests(unittest.TestCase):
    def test_two_audited_orders_and_exact_source_totals(self):
        for index, expected in enumerate(SOURCES):
            with self.subTest(league=index):
                data = source_fixture(index)
                original = copy.deepcopy(data)
                order = standings_order(data)
                self.assertEqual(
                    [t["roster_id"] for t in order["teams"]], expected["expected_order"]
                )
                self.assertEqual(len(order["ranks"]), 10)
                self.assertEqual(data, original)
                self.assertEqual(official_ranks(data), {})
                self.assertIn(
                    "Sleeper record, then Points For",
                    render_standings(data, champion=(2025, 1) if index == 0 else None),
                )
        arkham = source_fixture(1)
        self.assertEqual(
            next(t["points_for"] for t in arkham["teams"] if t["roster_id"] == 4),
            297.43,
        )
        self.assertIsNone(playoff_position(arkham, standings_order(arkham))["boundary"])

    def test_records_then_pf_and_no_pa_tiebreak(self):
        data = controlled(
            [(3, 1, 0, 1), (2, 2, 0, 200), (2, 2, 0, 100), (0, 4, 0, 1000)]
        )
        self.assertEqual(list(standings_order(data)["ranks"]), [1, 2, 3, 4])
        data["teams"][2]["points_for"] = 200
        order = standings_order(data)
        self.assertEqual(order["placements"][2], (2, 3))
        self.assertNotIn(2, order["ranks"])
        self.assertEqual(order["ranks"][4], 4)
        self.assertIn("Tied 2–3", render_standings(data))
        self.assertNotIn("standing-2", render_standings(data))
        data["teams"].reverse()
        self.assertEqual(standings_order(data)["placements"], order["placements"])

    def test_missing_and_invalid_records_pf_not_zero(self):
        for key, value in [
            ("wins", None),
            ("losses", None),
            ("ties", None),
            ("wins", -1),
            ("ties", True),
            ("points_for", None),
            ("points_for", float("nan")),
        ]:
            with self.subTest(key=key, value=value):
                data = controlled()
                data["teams"][0][key] = value
                self.assertEqual(standings_order(data)["ranks"], {})
                self.assertIn("required", standings_order(data)["reason"])
        self.assertEqual(record_fields({}), dict(wins=None, losses=None, ties=None))
        self.assertEqual(
            record_fields(dict(wins=0, losses=0, ties=0)),
            dict(wins=0, losses=0, ties=0),
        )
        data = controlled()
        data["teams"][0].update(
            wins=None, losses=None, ties=None, points_for=None, points_against=None
        )
        text = render_standings(data)
        self.assertIn("Record unavailable", text)
        self.assertNotIn("0-0-0", text)

    def test_incomplete_or_duplicate_franchise_inventory_has_no_rank(self):
        data = source_fixture()
        data["teams"].pop()
        self.assertEqual(standings_order(data)["ranks"], {})
        data = source_fixture()
        data["teams"][1]["roster_id"] = data["teams"][0]["roster_id"]
        self.assertEqual(standings_order(data)["ranks"], {})

    def test_unequal_games_differing_ties_and_equal_tied_opportunities(self):
        for rows, reason in [
            ([(3, 0, 0, 50), (3, 1, 0, 60)], "unequal"),
            ([(3, 0, 1, 50), (2, 2, 0, 60)], "tied-game"),
        ]:
            self.assertIn(reason, standings_order(controlled(rows))["reason"])
        data = controlled([(3, 0, 1, 50), (2, 1, 1, 60), (2, 1, 1, 40), (0, 3, 1, 100)])
        self.assertEqual(list(standings_order(data)["ranks"]), [1, 2, 3, 4])

    def test_median_source_records_not_head_to_head_replacement(self):
        data = controlled(
            [(6, 2, 0, 100), (5, 3, 0, 150), (3, 5, 0, 90), (2, 6, 0, 80)],
            league_average_match=1,
        )
        self.assertEqual(list(standings_order(data)["ranks"]), [1, 2, 3, 4])
        self.assertIn("6-2-0", render_standings(data))
        self.assertEqual(
            reconstructed_movement(data, standings_order(data))["ranks"], {}
        )

    def test_median_completed_week_movement_uses_both_results(self):
        data = controlled(
            [(2, 2, 0, 190), (3, 1, 0, 200), (1, 3, 0, 150), (2, 2, 0, 170)],
            league_average_match=1,
        )
        data["week"] = 3
        data["league"]["settings"].update(leg=3, last_scored_leg=2, playoff_teams=4)

        def rows(scores):
            return [
                dict(roster_id=i + 1, matchup_id=i // 2 + 1, points=score)
                for i, score in enumerate(scores)
            ]

        prepare(
            data,
            {
                "1": rows([100, 90, 80, 70]),
                "2": rows([90, 110, 70, 100]),
                "3": rows([0, 0, 0, 0]),
            },
        )
        order = standings_order(data)
        self.assertEqual(list(order["ranks"]), [2, 1, 4, 3])
        self.assertEqual(
            reconstructed_movement(data, order)["ranks"], {1: 1, 2: 2, 3: 3, 4: 4}
        )

    def test_source_rank_separate_and_not_default_formula(self):
        data = controlled()
        for t in data["teams"]:
            t["official_standing_rank"] = 5 - t["roster_id"]
        self.assertEqual(official_ranks(data)[1], 4)
        self.assertEqual(standings_order(data)["ranks"][1], 1)
        self.assertIn("Sleeper-supplied rank #4", render_standings(data))

    def test_source_changes_reuse_and_league_isolation(self):
        a, b = source_fixture(), source_fixture(1)
        self.assertEqual(standings_order(a), standings_order(copy.deepcopy(a)))
        original = standings_order(a)
        b["teams"][0]["points_for"] = 100000
        self.assertEqual(standings_order(a), original)
        a["teams"][0].update(wins=4, losses=0, points_for=900)
        self.assertNotEqual(standings_order(a)["ranks"], original["ranks"])

    def test_standard_cutoff_counts_and_residual_division_labels(self):
        data = source_fixture()
        for count in (4, 6, 8):
            data["league"]["settings"]["playoff_teams"] = count
            for t in data["teams"]:
                t["division"] = 1
            result = playoff_position(data, standings_order(data))
            self.assertEqual(result["boundary"], count)
            self.assertEqual(len(result["qualifiers"]), count)
            self.assertIn("Not a clinch", result["reason"])
        for count in (None, 0, 10, 11):
            data["league"]["settings"]["playoff_teams"] = count
            self.assertIsNone(playoff_position(data, standings_order(data))["boundary"])

    def test_missing_divisions_and_custom_rules_do_not_hide_ranking(self):
        for key, value in [
            ("divisions", None),
            ("playoff_type", 1),
            ("playoff_seed_type", 1),
        ]:
            data = controlled()
            data["league"]["settings"][key] = value
            self.assertEqual(len(standings_order(data)["ranks"]), 4)
            self.assertIsNone(playoff_position(data, standings_order(data))["boundary"])
        data = controlled()
        del data["league"]["settings"]["divisions"]
        self.assertIn("absent", playoff_position(data, standings_order(data))["reason"])

    def test_division_winners_wildcards_noncontiguous(self):
        data = controlled(
            [(4, 0, 0, 100), (3, 1, 0, 120), (2, 2, 0, 90), (1, 3, 0, 80)], divisions=2
        )
        for t in data["teams"]:
            t["division"] = 2 if t["roster_id"] == 4 else 1
        result = playoff_position(data, standings_order(data))
        self.assertEqual(result["qualifiers"], {1, 4})
        self.assertIsNone(result["boundary"])
        data["league"]["settings"]["playoff_teams"] = 3
        self.assertEqual(
            playoff_position(data, standings_order(data))["qualifiers"], {1, 2, 4}
        )
        data["teams"][3]["division"] = None
        self.assertEqual(
            playoff_position(data, standings_order(data))["qualifiers"], set()
        )

    def test_tie_at_cutoff_withheld_but_tie_inside_allowed(self):
        data = controlled(
            [(3, 1, 0, 100), (2, 2, 0, 100), (2, 2, 0, 100), (0, 4, 0, 80)]
        )
        self.assertIsNone(playoff_position(data, standings_order(data))["boundary"])
        data["league"]["settings"]["playoff_teams"] = 3
        self.assertEqual(playoff_position(data, standings_order(data))["boundary"], 3)

    def test_postseason_statistics_not_final_seeds_missing_bracket(self):
        data = controlled()
        data["league"]["settings"]["last_scored_leg"] = 14
        self.assertIn(
            "postseason", playoff_position(data, standings_order(data))["reason"]
        )

    def test_published_bracket_participants_separate(self):
        data = source_fixture()
        data["week"] = 14
        data["league"]["settings"].update(leg=14, last_scored_leg=13)
        prepare(data, {}, "postseason")
        data["season_matchups"]["brackets"]["winners_bracket"] = [
            {"m": 1, "r": 1, "t1": 3, "t2": 6, "w": None, "l": None},
            {"m": 2, "r": 1, "t1": 4, "t2": 5, "w": None, "l": None},
            {"m": 3, "r": 2, "t1": 1, "t2": {"w": 1}, "w": None, "l": None},
            {"m": 4, "r": 2, "t1": 2, "t2": {"w": 2}, "w": None, "l": None},
        ]
        result = playoff_position(data, standings_order(data))
        self.assertEqual(result["qualifiers"], {1, 2, 3, 4, 5, 6})
        self.assertEqual(result["kind"], "bracket")
        self.assertIsNone(result["boundary"])

    def test_historical_movement_complete_reconciled_and_period(self):
        for index in (0, 1):
            data = source_fixture(index)
            result = reconstructed_movement(data, standings_order(data))
            self.assertEqual(len(result["ranks"]), 10)
            self.assertEqual(result["period"], "completed Week 3 to Week 4")
            self.assertIn("not an observed Sleeper", result["reason"])
            data["season_matchups"]["weeks"]["5"]["rows"][0]["points"] = 100000
            self.assertEqual(
                reconstructed_movement(data, standings_order(data)), result
            )
            data["season_matchups"]["weeks"]["3"]["availability"] = "unavailable"
            self.assertEqual(
                reconstructed_movement(data, standings_order(data))["ranks"], {}
            )

    def test_movement_incompatible_league_missing_prior_and_disagreement(self):
        for change in ("league", "record", "ordering", "missing"):
            data = source_fixture()
            if change == "league":
                data["season_matchups"]["league_id"] = "another"
            elif change == "record":
                data["teams"][0]["wins"] += 1
            elif change == "ordering":
                data["teams"][0]["points_for"] = 100000
            else:
                data["season_matchups"]["weeks"]["2"]["rows"] = []
            self.assertEqual(
                reconstructed_movement(data, standings_order(data))["ranks"], {}
            )

    def test_streak_singular_and_non_scoring_current_week(self):
        text = completed_streak(source_fixture(), 1)
        self.assertIn("1 consecutive loss", text)
        self.assertNotIn("1 consecutive losses", text)


class StandingsPublicationTests(unittest.TestCase):
    def test_real_context_publication_and_warm_routes_default_secondary_and_fallback(
        self,
    ):
        import dtos_app
        from routes.home import create_home_router

        for mode in ("default", "secondary", "fallback"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                data = source_fixture()
                lid = str(data["league"]["league_id"])
                runtime = LeagueRuntime(
                    lid, state={"data": data}, owns_state=mode == "secondary"
                )
                projection = ProjectionService(
                    Path(folder) / "projection.sqlite3", league_id=lid
                )
                active = {"data": data, "context": None}
                fois = SimpleNamespace(
                    repository=SimpleNamespace(league=lambda *args: None)
                )

                async def fresh():
                    pass

                app = FastAPI()
                app.include_router(
                    create_home_router(
                        ensure_fresh=fresh,
                        require_data=lambda: active["data"],
                        page=dtos_app.page,
                        generation_provider=dtos_app.home_presentation_generation,
                    )
                )
                with (
                    patch.object(dtos_app, "fois_service", fois),
                    patch.object(
                        dtos_app,
                        "current_league_context",
                        side_effect=lambda: active["context"],
                    ),
                    patch.dict(dtos_app.STATE, {"data": data}),
                    patch("routes.home.build_team_directory", return_value={}),
                    patch("routes.home.defending_champion", return_value=None),
                    patch("services.attention_changes.pick_changes", return_value=([], {})),
                    patch("services.home_attention.attention_state", return_value={"items": []}),
                    patch("src.ui.front_office_brief.cards", return_value=""),
                    patch("routes.home.current_league_context", return_value=None),
                ):

                    def publish():
                        if mode != "fallback":
                            runtime.apply_data(data)
                            active["context"] = dtos_app._publish_runtime_context(
                                runtime, projection
                            )

                    publish()
                    first_generation = dtos_app.home_presentation_generation()
                    client = TestClient(app)
                    first = client.get("/").text
                    self.assertIn("L1", first)
                    raw = copy.deepcopy(SOURCES[0]["weeks"])
                    # Withdraw predecessor evidence while all current inputs stay fixed.
                    raw["4"] = None
                    prepare(data, raw, "withdrawal")
                    publish()
                    self.assertNotEqual(
                        first_generation, dtos_app.home_presentation_generation()
                    )
                    warm = client.get("/").text
                    league = client.get("/league").text
                    self.assertNotIn('data-badge="streak"', warm)
                    self.assertNotIn('data-badge="streak"', league)
                    prepare(data, SOURCES[0]["weeks"], "recovered")
                    publish()
                    self.assertIn("L1", client.get("/").text)
                    stable = dtos_app.home_presentation_generation()
                    data["season_matchups"]["observed_at"] = "retrieval only"
                    publish()
                    self.assertEqual(stable, dtos_app.home_presentation_generation())
                    self.assertIn("L1", client.get("/league").text)

    def test_warm_home_corrected_scores_with_identical_current_facts(self):
        import dtos_app
        from routes.home import create_home_router

        data = controlled([(1, 1, 0, 30), (1, 1, 0, 30)])
        data["week"] = 3
        data["league"]["settings"].update(leg=3, last_scored_leg=2, playoff_teams=4)

        def week(a, b):
            return [
                dict(roster_id=1, matchup_id=1, points=a),
                dict(roster_id=2, matchup_id=1, points=b),
            ]

        weeks = {"1": week(10, 15), "2": week(20, 15), "3": week(0, 0)}
        prepare(data, weeks)
        retained = source_generations(data, "profile")
        context = SimpleNamespace(
            league_id=data["league"]["league_id"],
            data=data,
            state={"data": data},
            runtime=SimpleNamespace(source_generations=retained),
        )

        async def fresh():
            pass

        app = FastAPI()
        app.include_router(
            create_home_router(
                ensure_fresh=fresh,
                require_data=lambda: data,
                page=dtos_app.page,
                generation_provider=dtos_app.home_presentation_generation,
            )
        )
        with (
            patch.object(dtos_app, "current_league_context", return_value=context),
            patch("routes.home.build_team_directory", return_value={}),
            patch("routes.home.defending_champion", return_value=None),
            patch("services.attention_changes.pick_changes", return_value=([], {})),
            patch("services.home_attention.attention_state", return_value={"items": []}),
            patch("src.ui.front_office_brief.cards", return_value=""),
            patch("routes.home.current_league_context", return_value=None),
        ):
            client = TestClient(app)
            first = client.get("/").text
            self.assertIn("W1", first)
            generation = dtos_app.home_presentation_generation()
            weeks.update({"1": week(20, 15), "2": week(10, 15)})
            prepare(data, weeks, "corrected")
            # Deliberately retained runtime identities reproduce the default
            # publication gap; direct prepared identity still changes Home.
            self.assertEqual(context.runtime.source_generations, retained)
            self.assertNotEqual(generation, dtos_app.home_presentation_generation())
            warm = client.get("/").text
            self.assertIn("L1", warm)
            self.assertIn("L1", client.get("/league").text)
            self.assertNotEqual(first, warm)
            self.assertEqual(data["teams"][0]["points_for"], 30)

    def test_timeout_recovery_and_absent_generation_sentinel(self):
        data = source_fixture()
        weeks = copy.deepcopy(SOURCES[0]["weeks"])
        weeks["4"] = TimeoutError("controlled timeout")
        prepare(data, weeks)
        missing = source_generations(data, "profile")
        self.assertEqual(
            data["season_matchups"]["weeks"]["4"]["reason"], "SOURCE_WEEK_UNAVAILABLE"
        )
        prepare(data, SOURCES[0]["weeks"])
        self.assertNotEqual(
            missing["season_matchups"],
            source_generations(data, "profile")["season_matchups"],
        )
        data.pop("season_matchups")
        self.assertEqual(
            source_generations(data, "profile")["season_matchups"],
            "season-matchups:unavailable",
        )

    def test_correction_changes_only_historical_dependency_and_no_cross_league(self):
        data = source_fixture()
        before = source_generations(data, "profile")
        weeks = copy.deepcopy(SOURCES[0]["weeks"])
        weeks["1"][0]["points"] = 999
        prepare(data, weeks)
        after = source_generations(data, "profile")
        self.assertNotEqual(before["season_matchups"], after["season_matchups"])
        for key in before:
            if key != "season_matchups":
                self.assertEqual(before[key], after[key])
        other = source_generations(source_fixture(1), "profile")
        self.assertNotEqual(after["season_matchups"], other["season_matchups"])
        self.assertEqual(before, source_generations(source_fixture(), "profile"))
