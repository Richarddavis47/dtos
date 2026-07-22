"""HTTP and cached-data contracts for player dossier discovery."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.api import create_api_router
from routes.transactions import create_transactions_router
from services.asset_intelligence import build_player_dossier, player_asset_index
from services.sleeper import STATE, sync_sleeper


async def _noop() -> None:
    return None


async def _sync_noop(**_: object) -> dict[str, object]:
    return {}


async def _refresh() -> bool:
    return True


def _page(_: str, body: str):
    from fastapi.responses import HTMLResponse
    return HTMLResponse(body)


def fixture_data() -> dict[str, object]:
    teams = []
    for roster_id in range(1, 11):
        teams.append({
            "roster_id": roster_id,
            "owner": f"Owner {roster_id}",
            "team_name": f"Team {roster_id}",
            "wins": 5,
            "losses": 5,
            "ties": 0,
            "points_for": 1000 + roster_id,
            "max_points": 1100 + roster_id,
            "players": [{"id": "player one", "name": "Player One", "position": "QB", "team": "BUF", "roster_slot": "Starter"}] if roster_id == 1 else [],
            "picks_owned": [],
        })
    return {
        "league": {"league_id": "league-1", "roster_positions": ["QB", "RB", "WR", "TE", "SUPER_FLEX"]},
        "players": {"player one": {"full_name": "Player One", "position": "QB", "team": "BUF", "age": 24}},
        "teams": teams,
        "transactions": [],
        "traded_picks": [],
    }


class PlayerApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = fixture_data()
        self.state = {"data": self.data, "last_sync": "cached", "last_error": None, "syncing": False}
        app = FastAPI()
        app.include_router(create_api_router(
            ensure_fresh=_noop,
            require_data=lambda: self.data,
            sync_sleeper=_sync_noop,
            state=self.state,
            league_id="league-1",
        ))
        app.include_router(create_transactions_router(
            ensure_fresh=_noop,
            refresh_transactions=_refresh,
            require_data=lambda: self.data,
            state=self.state,
            page=_page,
        ))
        self.client = TestClient(app)

    def test_canonical_player_index_is_enumerable_and_url_safe(self) -> None:
        response = self.client.get("/api/players")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["players"][0]["player_id"], "player one")
        self.assertEqual(payload["players"][0]["dossier_url"], "/players/player%20one")

    def test_league_include_players_uses_same_contract(self) -> None:
        canonical = self.client.get("/api/players").json()["players"]
        included = self.client.get("/api/league?include_players=true").json()["players"]
        self.assertEqual(included, canonical)
        self.assertNotIn("players", self.client.get("/api/league").json())

    def test_valid_dossier_url_and_missing_id_behavior(self) -> None:
        dossier_url = self.client.get("/api/players").json()["players"][0]["dossier_url"]
        valid = self.client.get(f"{dossier_url}?front_office=1")
        self.assertEqual(valid.status_code, 200)
        self.assertIn("Asset Intelligence v1", valid.text)
        self.assertIn("Live Data & Market", valid.text)
        self.assertIn("Availability reason", valid.text)
        self.assertEqual(self.client.get("/players/").status_code, 404)
        self.assertEqual(self.client.get("/players/not-found").status_code, 404)

    def test_all_front_office_contexts_accept_a_discovered_player(self) -> None:
        for roster_id in range(1, 11):
            with self.subTest(roster_id=roster_id):
                report, team, _ = build_player_dossier(self.data, "player one", roster_id)
                self.assertEqual(team["roster_id"], roster_id)
                self.assertIn(f"Front Office {roster_id}", report.core_values.team_fit.summary)

    def test_index_ignores_roster_entries_without_ids(self) -> None:
        self.data["teams"][0]["players"].append({"name": "Invalid"})
        self.assertEqual(len(player_asset_index(self.data)), 1)


class CachedSleeperFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_sync_preserves_cached_player_contract(self) -> None:
        original = dict(STATE)
        cached = fixture_data()
        STATE.clear()
        STATE.update({"data": cached, "last_sync": "cached", "last_error": None, "syncing": False})
        try:
            with patch("services.sleeper.sleeper_get", new=AsyncMock(side_effect=RuntimeError("Sleeper unavailable"))), patch("services.sleeper.save_cache"):
                await sync_sleeper()
            self.assertEqual(player_asset_index(STATE["data"])[0]["player_id"], "player one")
            self.assertIn("Sleeper unavailable", STATE["last_error"])
        finally:
            STATE.clear()
            STATE.update(original)


if __name__ == "__main__":
    unittest.main()
