from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routes.accounts import create_accounts_router
from src.core.accounts import AccountService, AccountStore, group_league_series
from src.core.league_runtime import LeagueRuntime, LeagueRuntimeManager
from src.platform.account_context import AccountContextMiddleware


def _league(league_id: str, season: int, *, previous: str | None = None, name: str = "Dynasty") -> dict:
    return {
        "league_id": league_id, "season": str(season), "name": name,
        "previous_league_id": previous, "total_rosters": 10,
    }


class MultiLeagueOnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.store = AccountStore(Path(self.folder.name) / "accounts.sqlite3")
        self.service = AccountService(self.store)
        self.runtime = type("Runtime", (), {"get": AsyncMock(return_value=object())})()
        self.account_id, _ = self.service.create_account("manager", "Manager", "a secure password")
        self.store.link_sleeper(self.account_id, sleeper_user_id="user-a", username="manager", display_name="Manager")
        first = _league("100", 2026, name="League One")
        self.store.upsert_membership(self.account_id, first, "user-a", 1, "Franchise One", "active")
        self.store.activate(self.account_id, "100")
        self.token, self.csrf = self.service.new_session(self.account_id)

    def tearDown(self) -> None:
        self.folder.cleanup()

    def client(self) -> TestClient:
        app = FastAPI()
        app.add_middleware(AccountContextMiddleware, service=self.service, required=True)
        app.include_router(create_accounts_router(service=self.service, runtime_manager=self.runtime))

        @app.get("/api/fois/leagues/{league_id}")
        async def league_private(league_id: str, request: Request) -> dict:
            return {"league_id": league_id, "query": request.url.query}

        client = TestClient(app)
        client.cookies.set("dtos_session", self.token)
        return client

    def _member_mocks(self, league: dict, *, roster_id: int = 7, franchise: str = "Franchise Two") -> None:
        series = group_league_series([league])[0]
        self.service.discover_series = AsyncMock(return_value=(series,))  # type: ignore[method-assign]
        self.service.complete_series = AsyncMock(return_value=series)  # type: ignore[method-assign]
        self.service.resolve_membership = AsyncMock(return_value=(roster_id, franchise, "active"))  # type: ignore[method-assign]

    def test_discovered_second_league_reaches_handler_and_becomes_authorized(self) -> None:
        second = _league("200", 2026, name="League Two")
        self._member_mocks(second)
        response = self.client().post("/account/leagues/200", data={"csrf_token": self.csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        context = self.store.context_for_session(self.token)
        self.assertEqual(context.active_league_id, "200")
        self.assertEqual(context.membership.roster_id, 7)
        self.assertEqual(context.membership.franchise_name, "Franchise Two")
        self.assertEqual(len(self.store.memberships(self.account_id)), 2)
        self.assertEqual(self.runtime.get.await_count, 1)

    def test_static_import_is_not_parsed_as_a_league_id(self) -> None:
        second = _league("200", 2026, name="League Two")
        self._member_mocks(second)
        self.service.league = AsyncMock(return_value=second)  # type: ignore[method-assign]
        response = self.client().post("/account/leagues/import", data={"csrf_token": self.csrf, "league_id": "200"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, "200")

    def test_nonmember_candidate_reaches_verifier_but_persists_nothing(self) -> None:
        second = _league("200", 2026, name="League Two")
        self._member_mocks(second)
        self.service.league = AsyncMock(return_value=second)  # type: ignore[method-assign]
        self.service.resolve_membership = AsyncMock(return_value=(None, None, "no_franchise"))  # type: ignore[method-assign]
        response = self.client().post("/account/leagues/import", data={"csrf_token": self.csrf, "league_id": "200"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.league_id for row in self.store.memberships(self.account_id)], ["100"])
        self.assertEqual(self.store.context_for_session(self.token).active_league_id, "100")

    def test_discovered_nonmember_persists_nothing(self) -> None:
        second = _league("200", 2026, name="League Two")
        self._member_mocks(second)
        self.service.resolve_membership = AsyncMock(return_value=(None, None, "no_franchise"))  # type: ignore[method-assign]
        response = self.client().post("/account/leagues/200", data={"csrf_token": self.csrf})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row.league_id for row in self.store.memberships(self.account_id)], ["100"])

    def test_same_canonical_league_supports_independent_account_franchises(self) -> None:
        second_account, _ = self.service.create_account("other", "Other", "a secure password")
        self.store.link_sleeper(second_account, sleeper_user_id="user-b", username="other", display_name="Other")
        shared = _league("300", 2026, name="Shared")
        self.store.upsert_membership(self.account_id, shared, "user-a", 2, "A Team", "active")
        self.store.upsert_membership(second_account, shared, "user-b", 9, "B Team", "active")
        self.assertEqual(self.store.activate(self.account_id, "300").roster_id, 2)
        self.assertEqual(self.store.activate(second_account, "300").roster_id, 9)

    def test_ordinary_unconnected_league_route_remains_denied(self) -> None:
        response = self.client().get("/api/fois/leagues/200")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "unauthorized_league")

    def test_duplicate_import_is_idempotent(self) -> None:
        second = _league("200", 2026, name="League Two")
        self._member_mocks(second)
        client = self.client()
        for _ in range(2):
            self.assertEqual(client.post("/account/leagues/200", data={"csrf_token": self.csrf}, follow_redirects=False).status_code, 303)
        self.assertEqual(len([row for row in self.store.memberships(self.account_id) if row.league_id == "200"]), 1)
        self.assertEqual(sum(row["current_league_id"] == "200" for row in self.store.series(self.account_id)), 1)

    def test_connected_league_switch_uses_local_membership_without_provider_calls(self) -> None:
        second = _league("200", 2026, name="League Two")
        self.store.upsert_membership(self.account_id, second, "user-a", 7, "Franchise Two", "active")
        self.service.discover_series = AsyncMock(side_effect=AssertionError("switch must not discover"))  # type: ignore[method-assign]
        self.service.resolve_membership = AsyncMock(side_effect=AssertionError("switch must not resolve"))  # type: ignore[method-assign]
        response = self.client().post("/account/leagues/200/activate", data={"csrf_token": self.csrf}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.store.context_for_session(self.token).membership.franchise_name, "Franchise Two")
        self.assertEqual(self.runtime.get.await_count, 1)


class LeagueSeriesAndScaleTests(unittest.IsolatedAsyncioTestCase):
    def test_account_migration_records_v1_and_v2_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "accounts.sqlite3"
            AccountStore(path)
            AccountStore(path)
            with closing(AccountStore(path).connect()) as connection:
                versions = [row[0] for row in connection.execute("SELECT version FROM account_schema_migrations ORDER BY version")]
            self.assertEqual(versions, [1, 2])

    def test_continuing_six_seasons_form_one_series_without_name_matching(self) -> None:
        rows = [_league(str(year), year, previous=str(year - 1) if year > 2021 else None, name="Day Traders") for year in range(2021, 2027)]
        series = group_league_series(rows)
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0].current_league_id, "2026")
        self.assertEqual([str(row["league_id"]) for row in series[0].seasons], ["2026", "2025", "2024", "2023", "2022", "2021"])
        unrelated = _league("9999", 2026, name="Day Traders")
        self.assertEqual(len(group_league_series([*rows, unrelated])), 2)

    def test_broken_chain_is_not_guessed(self) -> None:
        rows = [_league("200", 2026, previous="missing", name="Same"), _league("100", 2025, name="Same")]
        self.assertEqual(len(group_league_series(rows)), 2)

    def test_future_rollover_is_indefinite_and_year_agnostic(self) -> None:
        rows = [_league(str(year), year, previous=str(year - 1) if year > 2026 else None) for year in range(2026, 2035)]
        series = group_league_series(rows)[0]
        self.assertEqual(series.current_league_id, "2034")
        self.assertEqual(len(series.seasons), 9)

    def test_rollover_promotes_current_without_exposing_historical_front_offices(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(Path(folder) / "accounts.sqlite3")
            service = AccountService(store)
            account_id, _ = service.create_account("rollover", "Rollover", "a secure password")
            old = _league("2026-id", 2026)
            current = _league("2027-id", 2027, previous="2026-id")
            store.upsert_membership(account_id, old, "owner", 1, "Old franchise", "active")
            store.upsert_membership(account_id, current, "owner", 9, "Current franchise", "active")
            store.upsert_series(
                account_id,
                series_id="2026-id",
                current_league=current,
                seasons=(current, old),
                roster_id=9,
                franchise_name="Current franchise",
            )

            fronts = store.series(account_id)
            self.assertEqual(len(fronts), 1)
            self.assertEqual(fronts[0]["current_league_id"], "2027-id")
            self.assertEqual(fronts[0]["roster_id"], 9)
            self.assertIsNone(store.activate(account_id, "2026-id"))
            self.assertEqual(store.activate(account_id, "2027-id").roster_id, 9)

    def test_500_continuing_series_remain_500_front_offices(self) -> None:
        rows = []
        for series_number in range(500):
            prior = None
            for season in range(2021, 2027):
                league_id = str(1_000_000 + series_number * 10 + season - 2021)
                rows.append(_league(league_id, season, previous=prior, name="Shared name"))
                prior = league_id
        grouped = group_league_series(rows)
        self.assertEqual(len(grouped), 500)
        self.assertTrue(all(len(item.seasons) == 6 for item in grouped))

    def test_500_memberships_are_rows_not_eager_runtimes(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(Path(folder) / "accounts.sqlite3")
            service = AccountService(store)
            account_id, _ = service.create_account("scale", "Scale", "a secure password")
            for number in range(500):
                league = _league(str(10_000 + number), 2026, name=f"League {number:03d}")
                store.upsert_membership(account_id, league, "scale-user", number + 1, f"Franchise {number}", "active")
                store.upsert_series(account_id, series_id=league["league_id"], current_league=league, seasons=(league,), roster_id=number + 1, franchise_name=f"Franchise {number}")
            manager = LeagueRuntimeManager(max_warm=2, hydrator=None)
            self.assertEqual(len(store.memberships(account_id)), 500)
            self.assertEqual(len(store.series(account_id)), 500)
            for target in ("10000", "10249", "10499"):
                membership = store.activate(account_id, target)
                self.assertEqual(membership.league_id, target)
                self.assertEqual(membership.roster_id, int(target) - 9999)
            self.assertEqual(manager.health()["resident_runtime_count"], 0)

    def test_league_configuration_and_pick_state_are_runtime_scoped(self) -> None:
        one = LeagueRuntime("100")
        two = LeagueRuntime("200")
        one.apply_data({"league": {"league_id": "100", "season": 2026}, "scoring_settings": {"pass_td": 4}, "roster_positions": ["QB", "SUPER_FLEX"], "traded_picks": [{"league_id": "100", "pick": "A"}]})
        two.apply_data({"league": {"league_id": "200", "season": 2026}, "scoring_settings": {"pass_td": -6}, "roster_positions": ["QB"], "traded_picks": [{"league_id": "200", "pick": "B"}]})
        self.assertNotEqual(one.scoring_profile, two.scoring_profile)
        self.assertEqual({row["league_id"] for row in one.state["data"]["traded_picks"]}, {"100"})
        self.assertEqual({row["league_id"] for row in two.state["data"]["traded_picks"]}, {"200"})
