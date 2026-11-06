"""Direct retained-Sleeper parity, no fantasy scoring reconstruction in expectations."""

import asyncio
import copy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services.matchup_season import prepare_season_matchups, source_player_actual
from services.player_evidence import attach_sleeper_actuals
from src.core.player_value_projection.canonical_production import (
    prepared_production_context,
)
from src.core.player_value_projection.sleeper_actuals import (
    prepare_actual_results,
    resolve_score,
    scoring_identity,
)

STAMP = "2026-11-01T00:00:00Z"


def actual_data(
    league_id="A",
    *,
    scores=(23.4738, 0, -2.125, 19.31, 28.219, 12.2, 18.111, 21.4),
    player="4984",
    scoring=None,
    season=2026,
):
    """Disposable source rows; expected scores below are copied from these rows.

    Not the owner's roster, historical live scores, or an upstream API capture.
    """
    scoring = scoring or {"pass_yd": 0.04, "st_ff": 1, "sack": 1, "rec": 1}
    league = dict(
        league_id=league_id,
        season=str(season),
        sport="nfl",
        status="in_season",
        scoring_settings=scoring,
        roster_positions=[
            "QB",
            "RB",
            "RB",
            "WR",
            "WR",
            "TE",
            "FLEX",
            "FLEX",
            "K",
            "DEF",
            "BN",
        ],
        settings=dict(
            leg=9,
            last_scored_leg=8,
            start_week=1,
            playoff_week_start=15,
            playoff_teams=6,
            playoff_round_type=0,
            playoff_type=0,
        ),
    )
    buckets = {
        str(w): [
            dict(
                roster_id=1,
                matchup_id=1,
                players=[player, "bench"],
                starters=[player],
                starters_points=[v],
                players_points={player: v, "bench": -1.24},
                points=200,
                custom_points=300,
            )
        ]
        for w, v in enumerate(scores, 1)
    }

    async def fetch(path):
        return copy.deepcopy(buckets.get(path.rsplit("/", 1)[-1], []))

    def acquire():
        return asyncio.run(
            prepare_season_matchups(league, 9, [], fetch, observed_at=STAMP)
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        publication = acquire()
    else:
        # Playwright owns a running loop; exercise the real async preparation
        # in a bounded fixture thread, never nesting event loops.
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            publication = executor.submit(acquire).result(timeout=10)
    return dict(
        league=league,
        scoring_settings=scoring,
        week=9,
        players={player: {}},
        season_matchups=publication,
        nfl_state=dict(season=str(season), week=9),
    )


def publish(data):
    lid = data["league"]["league_id"]
    snapshot = {
        "league_id": lid,
        "season": int(data["league"]["season"]),
        "scoring_fingerprint": scoring_identity(data["scoring_settings"]),
        "reference_generation": "unchanged-analysis",
        "players": {},
    }
    attach_sleeper_actuals(data, snapshot)
    data["canonical_player_production"] = snapshot
    return snapshot


def profile(data, player="4984"):
    return prepared_production_context(
        data.get("canonical_player_production") or publish(data),
        league_id=data["league"]["league_id"],
        player_id=player,
        data=data,
    )


class ActualScoreResolutionTests(unittest.TestCase):
    def test_zero_negative_and_precision_match_source_not_reconstruction(self):
        for score in (0, -2.125, 23.4738, 49.6638):
            row = dict(
                starters=["p"], starters_points=[score], players_points={"p": score}
            )
            self.assertEqual(
                resolve_score(row, "p")["points"], row["players_points"]["p"]
            )
            self.assertEqual(
                source_player_actual(row, "p", 0), row["starters_points"][0]
            )

    def test_web_display_midpoints_do_not_change_source_numbers(self):
        from src.core.player_value_projection.sleeper_actuals import actual_display

        for raw, display in [
            (0, "0.00"),
            (-0.0, "0.00"),
            (-2.125, "-2.13"),
            (2.125, "2.13"),
            (23.4738, "23.47"),
        ]:
            self.assertEqual(actual_display(raw), display)
            self.assertEqual(
                resolve_score({"players_points": {"p": raw}}, "p")["points"], raw
            )

    def test_conflict_has_no_precedence(self):
        row = dict(starters=["p"], starters_points=[0], players_points={"p": 9})
        self.assertIsNone(source_player_actual(row, "p", 0))
        self.assertEqual(
            resolve_score(row, "p")["reason"], "conflicting_sleeper_scores"
        )

    def test_index_cannot_read_another_player_or_negative_offset(self):
        row = dict(
            starters=["q", "p"], starters_points=[99, 8], players_points={"p": 8}
        )
        self.assertIsNone(source_player_actual(row, "p", 0))
        self.assertIsNone(source_player_actual(row, "p", -1))
        self.assertEqual(source_player_actual(row, "p", 1), 8)

    def test_null_invalid_missing_and_strings_are_not_zero(self):
        for value in (None, True, "0", "bad", float("nan"), float("inf")):
            self.assertIsNone(
                resolve_score({"players_points": {"p": value}}, "p")["points"]
            )
        self.assertIsNone(resolve_score({}, "p")["points"])
        self.assertIsNone(resolve_score({"players_points": {"0": 0}}, "0")["points"])

    def test_valid_explicit_score_is_not_blocked_by_null_alternate(self):
        for row in (
            dict(starters=["p"], starters_points=[None], players_points={"p": 0}),
            dict(starters=["p"], starters_points=[-3], players_points={"p": None}),
        ):
            result = resolve_score(row, "p")
            self.assertIsNotNone(result["points"])
            self.assertEqual(result["reason"], "invalid_alternate_score")

    def test_duplicate_starter_is_unresolved(self):
        self.assertIsNone(
            resolve_score(dict(starters=["p", "p"], starters_points=[1, 1]), "p")[
                "points"
            ]
        )


class SleeperPublicationTests(unittest.TestCase):
    def test_direct_weekly_source_parity_and_observation_denominator(self):
        data = actual_data()
        context = profile(data)
        for row in context.observations:
            retained = data["season_matchups"]["weeks"][str(row["week"])]["rows"][0][
                "players_points"
            ]["4984"]
            self.assertEqual(row["points"], retained)
        season = context.windows[3]
        self.assertEqual((season.observation_count, season.scored_count), (8, 8))
        self.assertEqual(season.weeks, tuple(range(1, 9)))
        self.assertAlmostEqual(season.observed_total, 120.5888)
        self.assertIn("not games played", " ".join(context.limitations))
        self.assertTrue(all(w.targets is None for w in context.windows))

    def test_bench_explicit_scores_but_absent_ir_taxi_and_free_agents_unknown(self):
        data = actual_data()
        data["teams"] = [dict(players=[dict(id="taxi"), dict(id="ir")])]
        self.assertEqual(profile(data, "bench").windows[3].fantasy_points, -1.24)
        for pid in ("ir", "taxi", "free-agent"):
            self.assertIsNone(profile(data, pid).windows[3].fantasy_points)
        self.assertNotEqual(profile(data).windows[3].observed_total, 300)

    def test_explicit_ir_or_unrostered_map_entry_is_source_evidence_not_inference(self):
        data = actual_data()
        data["season_matchups"]["weeks"]["1"]["rows"][0]["players_points"]["ir"] = 0
        self.assertEqual(profile(data, "ir").windows[3].fantasy_points, 0)
        self.assertEqual(profile(data, "ir").windows[3].observation_count, 1)

    def test_ownership_duplicates_are_deduplicated_and_conflicts_withheld(self):
        data = actual_data()
        row = data["season_matchups"]["weeks"]["1"]["rows"][0]
        duplicate = {**copy.deepcopy(row), "roster_id": 2}
        data["season_matchups"]["weeks"]["1"]["rows"].append(duplicate)
        self.assertEqual(profile(data).windows[3].observation_count, 8)
        duplicate["players_points"]["4984"] = 999
        publish(data)
        context = profile(data)
        self.assertIsNone(context.windows[3].fantasy_points)
        self.assertEqual(context.windows[3].scored_count, 7)
        self.assertIsNotNone(context.windows[1].fantasy_points)

    def test_completed_live_future_and_league_playoff_scope_are_distinct(self):
        data = actual_data()
        data["league"]["settings"].update(last_scored_leg=2, playoff_week_start=3)
        data["week"] = 4
        publish(data)
        c = profile(data)
        self.assertEqual(c.windows[3].observation_count, 2)
        self.assertEqual(c.observations[-1]["week"], 4)
        self.assertEqual(c.observations[-1]["state"], "provisional")
        self.assertEqual(c.observations[-1]["scope"], "postseason")
        self.assertEqual(c.periods["5"]["state"], "future")
        from src.ui.canonical_production import production_panel

        self.assertIn("(future · league postseason)", production_panel(asdict(c)))

    def test_unknown_completion_does_not_make_live_scores_final(self):
        data = actual_data()
        data["league"]["settings"].pop("last_scored_leg")
        self.assertEqual(profile(data).windows[3].observation_count, 0)
        self.assertTrue(profile(data).observations)

    def test_older_atomic_cache_reuses_native_sleeper_rows_not_calculated_totals(self):
        data = actual_data()
        data["season_matchups"].pop("scoring_fingerprint")
        c = profile(data)
        self.assertEqual(
            c.observations[0]["points"],
            data["season_matchups"]["weeks"]["1"]["rows"][0]["players_points"]["4984"],
        )
        self.assertIn("same retained league cache", " ".join(c.limitations))
        data["season_matchups"]["calendar_reference"] = "incompatible"
        publish(data)
        self.assertIsNone(profile(data).windows[3].fantasy_points)

    def test_publication_identity_scoring_and_season_are_not_interchangeable(self):
        for key, value in (
            ("league_id", "other"),
            ("season", "2025"),
            ("scoring_fingerprint", "wrong"),
        ):
            data = actual_data()
            data["season_matchups"][key] = value
            self.assertIsNone(profile(data).windows[3].fantasy_points)
        data = actual_data()
        publish(data)
        data["scoring_settings"] = {"rec": 0.5}
        self.assertFalse(profile(data).windows)
        with self.assertRaises(ValueError):
            prepare_actual_results(data, expected_league_id="other")

    def test_non_sleeper_analysis_cannot_supply_authoritative_points(self):
        data = actual_data()
        data["canonical_player_production"] = {
            "league_id": "A",
            "season": 2026,
            "players": {
                "4984": {
                    "production": {
                        "windows": [{"label": "Season Average", "fantasy_points": 999}]
                    }
                }
            },
        }
        self.assertFalse(profile(data).windows)

    def test_market_reference_analysis_is_not_repriced_by_actuals(self):
        from tests.test_current_production_coverage import prepared

        with tempfile.TemporaryDirectory() as folder:
            analysis = prepared(Path(folder) / "facts.sqlite3")
            original = copy.deepcopy(analysis)
            data = actual_data()
            attach_sleeper_actuals(data, analysis)
            self.assertEqual(
                analysis["reference_generation"], original["reference_generation"]
            )
            self.assertEqual(analysis["players"], original["players"])
            self.assertNotEqual(analysis["generation"], original["generation"])

    def test_completed_season_does_not_substitute_other_season_or_league(self):
        data = actual_data(season=2025)
        data["league"].update(status="complete")
        data["league"]["settings"].update(leg=8, last_scored_leg=8)
        data["week"] = 8
        c = profile(data)
        self.assertEqual(c.windows[3].season, 2025)
        self.assertEqual(c.windows[3].observation_count, 8)
        self.assertIsNone(c.windows[4].fantasy_points)

    def test_restored_source_reproduces_exact_profile_without_io(self):
        data = actual_data()
        before = asdict(profile(data))
        restored = json.loads(json.dumps(data))
        with patch(
            "httpx.AsyncClient.get", side_effect=AssertionError("no acquisition")
        ):
            publish(restored)
        self.assertEqual(asdict(profile(restored)), before)

    def test_each_league_retains_its_own_source_values_including_k_defense(self):
        for lid, score, position in [
            ("one-qb", 23.4738, "QB"),
            ("superflex", 49.6638, "QB"),
            ("kicker", -1.5, "K"),
            ("defense", 0, "DEF"),
        ]:
            data = actual_data(
                lid, scores=(score,), player="BUF" if position == "DEF" else "4984"
            )
            if lid == "superflex":
                data["league"]["roster_positions"] = ["QB", "SUPER_FLEX", "FLEX"]
            pid = "BUF" if position == "DEF" else "4984"
            self.assertEqual(
                profile(data, pid).observations[0]["points"],
                data["season_matchups"]["weeks"]["1"]["rows"][0]["players_points"][pid],
            )


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data = actual_data()

    async def test_failed_week_retains_explicit_last_valid_score_not_successful_acquisition(
        self,
    ):
        data = copy.deepcopy(self.data)
        old = data["season_matchups"]

        async def fail(_):
            raise RuntimeError("disposable source failure")

        new = await prepare_season_matchups(
            data["league"],
            9,
            [],
            fail,
            observed_at="2026-11-02T00:00:00Z",
            previous=old,
        )
        data["season_matchups"] = new
        self.assertEqual(new["weeks"]["1"]["availability"], "unavailable")
        c = profile(data)
        self.assertEqual(
            c.observations[0]["points"],
            old["weeks"]["1"]["rows"][0]["players_points"]["4984"],
        )
        self.assertEqual(c.observations[0]["retrieved_at"], STAMP)
        self.assertEqual(c.observations[0]["freshness"], "last_valid")
        self.assertIn("not newly revalidated", " ".join(c.limitations))

    async def test_correction_replaces_old_score_and_is_qualified(self):
        data = copy.deepcopy(self.data)
        old = data["season_matchups"]

        async def changed(path):
            rows = copy.deepcopy(
                old["weeks"].get(path.rsplit("/", 1)[-1], {}).get("rows", [])
            )
            for row in rows:
                row["players_points"]["4984"] = 7.1234
                row["starters_points"] = [7.1234]
            return rows

        data["season_matchups"] = await prepare_season_matchups(
            data["league"],
            9,
            [],
            changed,
            observed_at="2026-11-02T00:00:00Z",
            previous=old,
        )
        c = profile(data)
        self.assertEqual(c.observations[0]["points"], 7.1234)
        self.assertTrue(c.observations[0]["corrected"])
        self.assertNotEqual(
            data["season_matchups"]["semantic_generation"], old["semantic_generation"]
        )

    async def test_failed_refresh_cannot_borrow_a_different_scoring_publication(self):
        data = copy.deepcopy(self.data)
        old = data["season_matchups"]
        data["league"]["scoring_settings"] = {"rec": 0.5}
        data["scoring_settings"] = {"rec": 0.5}

        async def fail(_):
            raise RuntimeError("source failure")

        data["season_matchups"] = await prepare_season_matchups(
            data["league"], 9, [], fail, observed_at=STAMP, previous=old
        )
        self.assertFalse(profile(data).observations)


class ActualRenderedContractTests(unittest.TestCase):
    def fixture(self):
        from tests.test_current_production_coverage import ProductionViewFixture

        return ProductionViewFixture(self)

    def test_zero_negative_and_conflicting_source_scores_reach_both_routes_and_api(
        self,
    ):
        for value in (0, -2.125):
            f = self.fixture()
            for week in f.f.data["season_matchups"]["weeks"].values():
                for row in week["rows"]:
                    row["players_points"]["1"] = value
                    row["starters_points"] = [value]
            f.republish_actuals()
            for path in ("/market?selected=player%3A1", "/players/1?front_office=4"):
                text = f.f.client.get(path).text
                self.assertIn(
                    f"{({0: '0.00', -2.125: '-2.13'})[value]} fantasy points per score observation",
                    text,
                )
                self.assertIn("not a games-played average", text)
            actual = f.api()
            self.assertEqual(actual["windows"][3]["fantasy_points"], value)
            self.assertEqual(actual["observations"][0]["points"], value)
            f.f.data["season_matchups"]["weeks"]["1"]["rows"][0]["starters_points"] = [
                999
            ]
            f.republish_actuals()
            for path in ("/market?selected=player%3A1", "/players/1?front_office=4"):
                text = f.f.client.get(path).text
                self.assertIn("7 of 8 completed-week score observations", text)
                self.assertIn("Sleeper score records disagree", text)
                self.assertIn("are withheld", text)
            self.assertIsNone(f.api()["windows"][3]["fantasy_points"])

    def test_missing_nflverse_special_teams_does_not_block_sleeper_actual(self):
        f = self.fixture()
        f.set_scoring({"st_ff": 1, "pass_yd": 0.04})
        self.assertIsNone(
            f.f.data["canonical_player_production"]["players"]["1"][
                "non_sleeper_analysis"
            ]["windows"][3]["fantasy_points"]
        )
        self.assertEqual(f.api()["windows"][3]["fantasy_points"], 18)
        self.assertIn(
            "18.00 fantasy points per score observation",
            f.f.client.get("/players/1?front_office=4").text,
        )

    def test_ordinary_disclosures_and_reads_perform_no_acquisition(self):
        f = self.fixture()
        with (
            patch(
                "services.sleeper.sleeper_get",
                side_effect=AssertionError("no provider work"),
            ),
            patch(
                "services.player_evidence.prepare_player_production",
                side_effect=AssertionError("no preparation"),
            ),
        ):
            for path in (
                "/market?selected=player%3A1",
                "/players/1?front_office=4",
                "/api/market/assets/player:1",
            ):
                self.assertEqual(f.f.client.get(path).status_code, 200)

    def test_current_scoring_change_cannot_reuse_old_prepared_actuals(self):
        f = self.fixture()
        f.f.data["scoring_settings"] = {"rec": 99}
        # Bypass presentation caches only in this disposable fixture, retaining
        # the original preparation, to exercise the consumer's own boundary.
        f.f.cache.clear()
        response = f.f.client.get("/players/1?front_office=4")
        self.assertIn(
            "Compatible Sleeper actual results are not prepared", response.text
        )
        self.assertNotIn("18.00 fantasy points per score observation", response.text)


class RetainedScopeControls(unittest.TestCase):
    def test_cache_restoration_without_prior_analysis_still_admits_supported_scores(
        self,
    ):
        from services import sleeper
        from src.core.sync_status import safe_sync_state

        with tempfile.TemporaryDirectory() as directory:
            data = actual_data()
            cache = Path(directory) / "source.json"
            cache.write_text(json.dumps(safe_sync_state({"data": data})))
            with patch.object(sleeper, "league_cache_file", return_value=cache):
                restored = {}
                sleeper.load_cache(state=restored, league_id="A")
            self.assertEqual(
                profile(restored["data"]).observations[0]["points"], 23.4738
            )

    def test_account_scoped_data_does_not_share_actual_score_maps(self):
        first = actual_data("first", scores=(0,))
        second = actual_data("second", scores=(-5,))
        a, b = publish(first), publish(second)
        self.assertEqual(profile(first).observations[0]["points"], 0)
        self.assertEqual(profile(second).observations[0]["points"], -5)
        with self.assertRaises(ValueError):
            prepared_production_context(a, league_id="second", player_id="4984")
        self.assertNotEqual(
            a["sleeper_actuals"]["generation"], b["sleeper_actuals"]["generation"]
        )

    def test_unknown_week_and_invalid_retained_row_are_not_invented_scores(self):
        data = actual_data()
        data["season_matchups"]["weeks"]["1"]["rows"][0]["players_points"] = []
        c = profile(data)
        self.assertEqual(c.periods["1"]["reason"], "invalid_retained_matchup_row")
        self.assertEqual(c.windows[3].observation_count, 7)

    def test_global_analysis_storage_is_not_required_for_explicit_sleeper_results(self):
        from services.global_evidence import canonical_player_evidence

        data = actual_data()
        publish(data)
        with tempfile.TemporaryDirectory() as directory:
            result = canonical_player_evidence(
                "4984",
                data,
                expected_league_id="A",
                path=Path(directory) / "missing.sqlite",
                as_of="2026-11-02T00:00:00Z",
            )
            self.assertEqual(
                result["production"]["points_per_observation"],
                profile(data).windows[3].fantasy_points,
            )
            self.assertIsNone(result["production"]["ppg"])
            self.assertEqual(result["provider_calls"], 0)


class LegacyConsumerRestorationTests(unittest.TestCase):
    def test_native_scores_replace_only_the_old_cached_result_disclosure(self):
        from services import sleeper
        from tests.test_current_production_coverage import ProductionViewFixture

        f = ProductionViewFixture(self)
        cached = f.f.data["valuation_intelligence"]["assets"]["player:1"]
        prices = copy.deepcopy(cached["valuation_layers"])
        scores = copy.deepcopy(cached["scores"])
        cached["canonical_production"] = {
            "source": "Canonical nflverse production",
            "windows": [{"label": "Season Average", "fantasy_points": 999}],
        }
        f.f.data["canonical_player_production"].pop("sleeper_actuals")
        f.f.data["season_matchups"].pop("scoring_fingerprint")
        with patch.object(
            sleeper, "league_cache_file", return_value=f.f.root / "native-cache.json"
        ):
            sleeper.save_cache(
                state=f.f.state, league_id=f.f.data["league"]["league_id"]
            )
            restored = {}
            sleeper.load_cache(
                state=restored, league_id=f.f.data["league"]["league_id"]
            )
        new = restored["data"]["valuation_intelligence"]["assets"]["player:1"]
        self.assertEqual(
            new["canonical_production"]["windows"][3]["fantasy_points"], 18
        )
        self.assertEqual(
            new["canonical_production"]["source"], "Sleeper league matchup results"
        )
        self.assertEqual(new["valuation_layers"], prices)
        self.assertEqual(new["scores"], scores)
        f.f.data = restored["data"]
        f.f.state.update(restored)
        f.f.cache.clear()
        f.f.market = f.f.cache.get(
            f.f.data, f.f.state, f.f.history, f.f.data["league"]["league_id"]
        )
        self.assertEqual(f.api()["windows"][3]["fantasy_points"], 18)
        self.assertIn(
            "18.00 fantasy points per score observation",
            f.f.client.get("/players/1?front_office=4").text,
        )


class ResultUnitConsistencyTests(unittest.TestCase):
    def test_market_layer_and_profile_explanation_share_observation_units(self):
        from tests.test_current_production_coverage import ProductionViewFixture
        from src.core.asset_intelligence.models import AssetContext
        from src.core.asset_intelligence.players import evaluate_player
        from services.asset_explanations import player_profile_explanation

        f = ProductionViewFixture(self)
        detail = f.f.client.get("/api/market/assets/player:1").json()
        self.assertEqual(
            detail["value_layers"]["current_production_value"]["scale"],
            "Sleeper fantasy points per completed-week score observation",
        )
        context = AssetContext(
            f.f.data["league"]["league_id"],
            4,
            {},
            canonical_production=f.f.data["canonical_player_production"],
        )
        report = evaluate_player(
            {"id": "1", "position": "QB", "name": "Source player"}, context
        )
        explanation = player_profile_explanation(
            report, league_id=f.f.data["league"]["league_id"]
        )
        average = next(
            item for item in explanation.evidence if item.label == "Season Average"
        )
        self.assertEqual(
            average.unit, "Sleeper points per completed-week score observation"
        )
        usage = next(
            item
            for item in explanation.evidence
            if item.label == "NFLverse targets per observed game"
        )
        self.assertEqual(usage.unit, "targets per observed NFLverse game")
