"""Actual native publications and rendered consumers of scoped source freshness."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from src.core.intelligence import roster_diagnostics as diagnostics
from src.core.intelligence.team_strength import prepare_for_data
from tests.test_market_roster_relevance import MarketNeedFixture


class RosterSourceScopeTests(unittest.TestCase):
    def fixture(self, **options):
        return MarketNeedFixture(self, **options)

    def publish(self, f, *, stamps=None):
        now = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                **row,
                "season": 2026,
                "week": 2,
                "updated_at": (stamps or {}).get(row["player_id"], now),
            }
            for row in f.need_case.rows
        ]
        f.f.capital.reader.publish_horizon(
            {2: payload},
            data=f.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(f.f.capital.reader, f.data)
        return diagnostics.diagnose_league(
            f.data, f.f.capital.reader.snapshot(), projection_reader=f.f.capital.reader
        )["teams"]["1"]

    def add_unused(self, f, *, slot=None, status="Unknown", projected=None):
        pid = "unused-source-control"
        player = dict(
            id=pid,
            name="Disposable scope control",
            position="RB",
            status=status,
            team="NYJ",
            roster_slot=slot or "Bench",
        )
        f.data["players"][pid] = {**player, "full_name": player["name"]}
        if slot:
            f.data["teams"][0]["players"].append(player)
        if projected is not None:
            f.need_case.rows.append(
                dict(
                    player_id=pid,
                    player={"position": "RB"},
                    stats={"rush_yd": projected},
                )
            )
        return pid

    def state(self, f):
        return diagnostics.prepared_diagnostics(
            f.data, f.f.capital.reader.snapshot(), projection_reader=f.f.capital.reader
        )["teams"]["1"]

    def rendered(self, f):
        team = f.client.get("/teams/1")
        market = f.client.get("/market", params={"q": f.player_id, "front_office": 1})
        self.assertEqual(team.status_code, 200, team.text[:500])
        self.assertEqual(market.status_code, 200, market.text[:500])
        return team.text, market.text

    def test_unrostered_missing_row_cannot_change_supported_roster_finding(self):
        for sf in (False, True):
            with self.subTest(superflex=sf):
                f = self.fixture(superflex=sf)
                before = self.state(f)
                pid = self.add_unused(f)
                after = self.publish(f)
                self.assertEqual(after["optimal_points"], before["optimal_points"])
                self.assertEqual(after["optimal_ids"], before["optimal_ids"])
                self.assertEqual(
                    after["positions"]["RB"]["add_one_gain"],
                    before["positions"]["RB"]["add_one_gain"],
                )
                self.assertEqual(after["evidence"]["conclusion_state"], "current")
                self.assertIsNone(
                    f.f.capital.reader.snapshot()["players"][pid][
                        "canonical_projection"
                    ]
                )
                team, market = self.rendered(f)
                self.assertIn("Explore RB trades", team)
                self.assertIn("Explore in Trade For", market)

    def test_stale_unrostered_projection_remains_stale_without_tainting_rosters(self):
        f = self.fixture()
        pid = self.add_unused(f, projected=500)
        row = self.publish(f, stamps={pid: "2020-01-01T00:00:00+00:00"})
        source = f.f.capital.reader.snapshot()["players"][pid]
        self.assertEqual(source["source_freshness"], "Stale")
        self.assertEqual(source["canonical_projection"], 500)
        self.assertEqual(row["evidence"]["projection_freshness"], ["Fresh"])
        self.assertIn(
            "2020-01-01T00:00:00+00:00", row["evidence"]["source_observations"]
        )
        team, market = self.rendered(f)
        self.assertIn("across the full publication", team)
        self.assertIn("eligible roster references", team)
        self.assertIn("Explore in Trade For", self.rendered(f)[1])

    def test_explicit_reserve_storage_is_not_current_lineup_source_dependency(self):
        for slot in ("IR", "Taxi", "Reserve"):
            with self.subTest(slot=slot):
                f = self.fixture()
                before = self.state(f)
                pid = self.add_unused(f, slot=slot)
                after = self.publish(f)
                self.assertIn(pid, after["excluded_player_ids"])
                self.assertEqual(after["optimal_points"], before["optimal_points"])
                self.assertEqual(after["evidence"]["conclusion_state"], "current")
                self.assertIn("Explore in Trade For", self.rendered(f)[1])

    def test_explicit_not_lineup_eligible_row_does_not_supply_or_block_cover(self):
        f = self.fixture()
        pid = self.add_unused(f, slot="Bench")
        f.data["teams"][0]["players"][-1]["lineup_eligible"] = False
        row = self.publish(f)
        self.assertIn(pid, row["excluded_player_ids"])
        self.assertEqual(row["evidence"]["conclusion_state"], "current")
        self.assertNotIn(pid, row["optimal_ids"])

    def test_reactivation_requires_actual_projection_evidence(self):
        f = self.fixture()
        pid = self.add_unused(f, slot="IR", status="Active")
        self.publish(f)
        self.assertIn("Explore in Trade For", self.rendered(f)[1])
        f.data["teams"][0]["players"][-1]["roster_slot"] = "Bench"
        row = self.publish(f)
        self.assertIn(pid, row["missing_projection_ids"])
        self.assertNotEqual(row["evidence"]["conclusion_state"], "current")
        self.assertNotIn("Explore in Trade For", self.rendered(f)[1])

    def test_missing_eligible_reserve_remains_missing_and_withheld(self):
        f = self.fixture()
        pid = self.add_unused(f, slot="Bench", status="Active")
        row = self.publish(f)
        self.assertIn(pid, row["missing_projection_ids"])
        self.assertIsNone(
            f.f.capital.reader.snapshot()["players"][pid]["canonical_projection"]
        )
        self.assertNotEqual(row["evidence"]["conclusion_state"], "current")
        self.assertNotIn("Explore in Trade For", self.rendered(f)[1])

    def test_unknown_kicker_or_defense_availability_is_not_inferred_from_projection(
        self,
    ):
        for position in ("K", "DEF"):
            with self.subTest(position=position):
                f = self.fixture()
                pid = "1-" + position + "-0"
                p = next(p for p in f.data["teams"][0]["players"] if p["id"] == pid)
                p.update(status="Unknown", team="NYJ", injury_status=None)
                f.data["players"][pid].update(
                    status="Unknown", team="NYJ", injury_status=None
                )
                row = self.publish(f)
                projection = f.f.capital.reader.snapshot()["players"][pid]
                self.assertGreater(projection["canonical_projection"], 0)
                self.assertEqual(projection["availability"], "unknown")
                self.assertEqual(row["evidence"]["conclusion_state"], "provisional")
                team, market = self.rendered(f)
                self.assertIn("Provisional", team)
                self.assertNotIn("Explore in Trade For", market)

    def test_relevant_uncertainty_and_flex_competition_remain_qualified(self):
        for status in ("Unknown", "Questionable", "Doubtful"):
            with self.subTest(status=status):
                f = self.fixture()
                pid = "1-WR-0"
                p = next(p for p in f.data["teams"][0]["players"] if p["id"] == pid)
                p.update(status=status, team="NYJ")
                f.data["players"][pid].update(status=status, team="NYJ")
                row = self.publish(f)
                self.assertNotEqual(row["evidence"]["conclusion_state"], "current")
                self.assertNotIn("Explore in Trade For", self.rendered(f)[1])

    def test_zero_and_negative_sleeper_scores_keep_exact_values(self):
        for value in (0, -2.625):
            with self.subTest(value=value):
                f = self.fixture()
                native = next(r for r in f.need_case.rows if r["player_id"] == "1-RB-3")
                native["stats"]["rush_yd"] = value
                row = self.publish(f)
                self.assertEqual(
                    f.f.capital.reader.snapshot()["players"]["1-RB-3"][
                        "canonical_projection"
                    ],
                    value,
                )
                self.assertNotIn("1-RB-3", row["missing_projection_ids"])
                self.assertEqual(row["evidence"]["conclusion_state"], "current")

    def test_aging_still_withholds_and_does_not_recalculate_on_reads(self):
        f = self.fixture()
        self.add_unused(f)
        self.publish(f)
        self.assertIn("Explore in Trade For", self.rendered(f)[1])
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        with (
            patch.object(diagnostics, "_now", return_value=future),
            patch.object(
                diagnostics.SearchLineupMemo,
                "solve",
                side_effect=AssertionError("read recalculated"),
            ),
        ):
            team, market = self.rendered(f)
        self.assertIn("Provisional", team)
        self.assertIn("Aging", team)
        self.assertNotIn("Explore in Trade For", market)

    def test_failed_refresh_stays_provisional_with_last_valid_numbers(self):
        f = self.fixture()
        self.add_unused(f)
        before = self.publish(f)
        reader = f.f.capital.reader
        reader.begin_external_refresh()
        reader.fail_external_refresh(
            RuntimeError("controlled source failure"), league_id="league-1"
        )
        after = self.state(f)
        self.assertEqual(after["optimal_points"], before["optimal_points"])
        self.assertEqual(after["evidence"]["conclusion_state"], "provisional")
        self.assertTrue(after["evidence"]["refresh"]["retained_publication"])
        team, market = self.rendered(f)
        self.assertIn("latest refresh did not complete", team)
        self.assertNotIn("Explore in Trade For", market)

    def test_unused_foreign_generation_still_invalidates_atomic_publication(self):
        f = self.fixture()
        pid = self.add_unused(f)
        self.publish(f)
        snapshot = deepcopy(f.f.capital.reader.snapshot())
        snapshot["players"][pid]["projection_snapshot_id"] = "foreign"
        row = diagnostics.diagnose_league(
            f.data, snapshot, projection_reader=f.f.capital.reader
        )["teams"]["1"]
        self.assertFalse(row["evidence"]["calculation_supported"])
        self.assertIsNone(row["optimal_points"])
        self.assertIn("Mixed", " ".join(row["evidence"]["limitations"]))

    def test_foreign_league_or_scoring_cannot_use_personalized_evidence(self):
        f = self.fixture()
        self.add_unused(f)
        self.publish(f)
        for field, value in (
            ("league_id", "foreign"),
            ("scoring_settings", {"rush_yd": 9}),
        ):
            with self.subTest(field=field):
                snapshot = deepcopy(f.f.capital.reader.snapshot())
                snapshot[field] = value
                row = diagnostics.diagnose_league(
                    f.data, snapshot, projection_reader=f.f.capital.reader
                )["teams"]["1"]
                self.assertIsNone(row["optimal_points"])
                self.assertNotEqual(row["evidence"]["conclusion_state"], "current")

    def test_scope_does_not_mutate_source_rows_or_submitted_lineups(self):
        f = self.fixture()
        self.add_unused(f)
        self.publish(f)
        source = deepcopy(f.f.capital.reader.snapshot())
        data = deepcopy(f.data)
        self.state(f)
        self.rendered(f)
        self.assertEqual(f.data, data)
        self.assertEqual(f.f.capital.reader.snapshot(), source)

    def test_trade_verdict_and_points_do_not_change_for_an_unused_missing_row(self):
        from tests.test_roster_diagnostic_aging import DiagnosticAgingTests

        helper = DiagnosticAgingTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        before = helper.f.f.evaluate().json()["evaluation"]
        helper.data["players"]["unused"] = dict(
            id="unused", position="RB", status="Unknown"
        )
        helper.service.publish_horizon(
            helper.f.f.source.payloads,
            data=helper.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(helper.service, helper.data)
        after = helper.f.f.evaluate().json()["evaluation"]
        self.assertEqual(after["recommendation"], before["recommendation"])
        for side in ("active", "partner"):
            old = before["dimensions"]["roster_diagnostics"]["sides"][side]
            new = after["dimensions"]["roster_diagnostics"]["sides"][side]
            self.assertEqual(new["pre_optimal_points"], old["pre_optimal_points"])
            self.assertEqual(new["post_optimal_points"], old["post_optimal_points"])

    def test_incoming_stored_player_rechecks_its_post_trade_source_freshness(self):
        from tests.test_roster_diagnostic_aging import DiagnosticAgingTests

        helper = DiagnosticAgingTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        helper.data["teams"][0]["players"][0]["roster_slot"] = "IR"
        payloads = deepcopy(helper.f.f.source.payloads)
        for rows in payloads.values():
            for row in rows:
                if row["player_id"] == "a":
                    row["updated_at"] = "2020-01-01T00:00:00+00:00"
        helper.service.publish_horizon(
            payloads,
            data=helper.data,
            league_id="league-1",
            season=2026,
            current_week=2,
        )
        with patch(
            "services.global_evidence.retained_global_evidence", return_value=None
        ):
            prepare_for_data(helper.service, helper.data)
        package = helper.package("Active")
        self.assertEqual(
            package["sides"]["partner"]["pre_evidence"]["projection_freshness"],
            ["Fresh"],
        )
        post = package["sides"]["partner"]["post_evidence"]
        self.assertIn("Stale", post["projection_freshness"])
        self.assertNotEqual(post["conclusion_state"], "current")

    def restore(self, f, *, default):
        import asyncio
        import json
        from services import league_preparation, sleeper
        from src.core.league_runtime import LeagueRuntime

        path = f.root / "scope-cache.json"
        path.write_text(
            json.dumps(
                dict(data=f.data, last_sync=datetime.now(timezone.utc).isoformat())
            )
        )
        if default:
            state = {}
            with patch.object(sleeper, "league_cache_file", return_value=path):
                sleeper.load_cache(state=state, league_id="league-1")
            restored = state["data"]
        else:
            runtime = LeagueRuntime("league-1")
            published = []
            with patch.object(
                league_preparation, "league_cache_file", return_value=path
            ):
                self.assertTrue(
                    league_preparation.restore_cached_runtime(
                        runtime,
                        lambda r: published.append(r.state["data"]),
                        expected_season=2026,
                    )
                )
            self.assertEqual(len(published), 1)
            restored = deepcopy(published[0])
            asyncio.run(runtime.close())
            self.assertFalse(runtime.state["data"])
        f.data.clear()
        f.data.update(restored)
        self.assertTrue(f.f.capital.reader.restore_into(f.data))
        diagnostics.diagnose_league(
            f.data, f.f.capital.reader.snapshot(), projection_reader=f.f.capital.reader
        )

    def test_default_and_connected_cache_restoration_preserve_independent_source_scope(
        self,
    ):
        for default in (False, True):
            with self.subTest(default=default):
                f = self.fixture()
                self.add_unused(f)
                before = self.publish(f)
                self.restore(f, default=default)
                after = self.state(f)
                self.assertEqual(after["optimal_points"], before["optimal_points"])
                self.assertEqual(after["evidence"]["conclusion_state"], "current")
                self.assertIn("Explore in Trade For", self.rendered(f)[1])

    def test_eviction_reopening_and_missing_eligible_evidence_remain_distinct(self):
        f = self.fixture()
        pid = self.add_unused(f, slot="IR")
        self.publish(f)
        for _ in range(2):
            diagnostics.diagnostic_store.clear()
            self.restore(f, default=False)
            self.assertIn("Explore in Trade For", self.rendered(f)[1])
        p = next(p for p in f.data["teams"][0]["players"] if p["id"] == pid)
        p["roster_slot"] = "Bench"
        self.publish(f)
        self.restore(f, default=False)
        self.assertIn(pid, self.state(f)["missing_projection_ids"])
        self.assertNotIn("Explore in Trade For", self.rendered(f)[1])
