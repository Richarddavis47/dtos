"""v1.14.1 preserves state-specific evidence and existing dossier navigation."""
import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from routes.matchups import _battle_edge, _player_identity, _projection_range, create_matchups_router
from services.matchup_intelligence import matchup_projection
from src.ui.intelligence_presentation import matchup_game_state


def fixture(league="A", points=(0, 0), projections=(24, 8), bounds=(None, None)):
    sides, values = [], {}
    for index in range(2):
        pid = f"{league}{index}"
        sides.append({"roster_id": index + 1, "team": f"{league} Team {index}", "owner": f"GM {index}", "record": "0-0", "points": points[index], "lineup": [{"id": pid, "name": f"{league} Player {index}", "position": "QB", "nfl_team": "BUF", "slot": "QB", "points": points[index]}], "bench": []})
        values[index + 1] = {pid: NS(name=f"{league} Player {index}", projection=NS(projected_points=projections[index], floor=bounds[0], ceiling=bounds[1], confidence=90, projection_snapshot_id=f"{league}-generation"))}
    data = {"league_id": league, "week": 1, "preseason": True, "matchups": {"1": sides}}
    evidence = {f"{league}{i}": {"canonical_projection": projections[i], "provider": "Sleeper"} for i in range(2)}
    service = NS(player=lambda pid: evidence.get(pid, {}))
    return data, sides, values, service


class MatchupEvidenceTests(unittest.TestCase):
    def summary(self, data, sides, values, service):
        with patch("services.matchup_intelligence.current_league_context", return_value=NS(projection=service)):
            return matchup_projection(data, sides, values)

    def render(self, data, summary):
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: data, page=lambda title, body: HTMLResponse(body)))
        with patch("routes.matchups.matchup_projection", return_value=summary):
            response = TestClient(app).get("/matchups/1")
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_pregame_actual_zeroes_do_not_determine_battle(self):
        args = fixture()
        body = self.render(args[0], self.summary(*args))
        self.assertIn("A Team 0 projected edge", body)
        self.assertNotIn("Even battle", body)
        self.assertNotIn("0.0–0.0", body)
        self.assertIn("Unavailable</b><span>A Team 0 Range", body)

    def test_live_and_final_use_actual_not_projected_winner(self):
        for state, verb in (("live", "leads"), ("final", "wins")):
            args = fixture(points=(2, 9))
            for side in args[1]:
                side["status"] = state
            body = self.render(args[0], self.summary(*args))
            self.assertIn(f"A Team 1 {verb}", body)
            self.assertNotIn("A Team 0 projected edge", body)
            self.assertIn("Pregame projection", body)

    def test_explicit_live_zero_and_final_zero_are_not_pregame(self):
        self.assertEqual(matchup_game_state({"preseason": True}, [{"status": "live", "points": 0}]), "in-game")
        self.assertEqual(matchup_game_state({"preseason": True}, [{"status": "final", "points": 0}]), "final")

    def test_missing_projection_is_not_zero_or_volatility(self):
        args = fixture(projections=(None, 8))
        summary = self.summary(*args)
        self.assertIsNone(summary["sides"][0]["projected"])
        self.assertIsNone(summary["sides"][0]["canonical_projection_total"])
        self.assertIsNone(summary["projected_margin"])
        self.assertEqual(summary["highest_volatility"], "Unavailable")
        self.assertEqual(summary["missing"], 1)
        body = self.render(args[0], summary)
        self.assertIn("Projection unavailable", body)
        self.assertNotIn("0.0–0.0", body)

    def test_partial_team_totals_are_not_compared_as_complete(self):
        args = fixture()
        summary = self.summary(*args)
        summary["sides"][0]["canonical_projection_coverage"] = "1/2"
        self.assertIn("Pregame projections unavailable</b>", self.render(args[0], summary))

    def test_real_zero_bounds_remain_zero(self):
        args = fixture(projections=(0, 0), bounds=(0, 0))
        summary = self.summary(*args)
        self.assertEqual(summary["sides"][0]["floor"], 0)
        self.assertEqual(_projection_range(summary["sides"][0]), "0.0–0.0")
        self.assertIn("Even projected battle", self.render(args[0], summary))

    def test_partial_bounds_do_not_masquerade_as_complete(self):
        args = fixture(bounds=(2, None))
        summary = self.summary(*args)
        self.assertEqual(_projection_range(summary["sides"][0]), "Unavailable")
        self.assertEqual(summary["highest_volatility"], "Unavailable")

    def test_one_missing_contributor_invalidates_aggregate_not_known_player(self):
        args = fixture(bounds=(2, 30))
        args[1][0]["lineup"].append({"id": "missing", "name": "Missing", "position": "QB", "points": 0})
        summary = self.summary(*args)
        self.assertIsNone(summary["sides"][0]["floor"])
        self.assertIsNone(summary["sides"][0]["projected"])
        self.assertEqual(summary["sides"][0]["players"][0]["canonical_projection"], 24)
        self.assertEqual(summary["missing"], 1)

    def test_player_and_team_actions_stay_in_active_league(self):
        rendered = []
        for league in ("A", "B", "A"):
            args = fixture(league=league)
            before = copy.deepcopy(args[0])
            body = self.render(args[0], self.summary(*args))
            for index in range(2):
                self.assertIn(f'href="/players/{league}{index}"', body)
                self.assertIn(f'aria-label="Open {league} Player {index} player dossier"', body)
                self.assertIn(f'href="/teams/{index + 1}"', body)
            self.assertIn('href="/matchups"', body)
            self.assertNotIn(f'href="/players/{"B" if league == "A" else "A"}', body)
            self.assertEqual(args[0], before)
            rendered.append(body)
        self.assertEqual(rendered[0], rendered[2])

    def test_vacant_player_does_not_create_invalid_dossier_link(self):
        for pid in ("", "../account", 'x" onclick="'):
            self.assertNotIn("href=", _player_identity({"id": pid, "name": "Unknown"}))

    def test_missing_and_tied_battles_are_distinct(self):
        kwargs = {"state": "pregame", "left_name": "A", "right_name": "B"}
        self.assertEqual(_battle_edge(left=None, right=0, **kwargs)[0], "Projection unavailable")
        self.assertEqual(_battle_edge(left=0, right=0, **kwargs)[0], "Even projected battle")


if __name__ == "__main__":
    unittest.main()
