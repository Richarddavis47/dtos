"""Prepared season paths preserve scope, availability and no hindsight."""
import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from services.matchup_season import compact_week, prepare_season_matchups, season_week_view, _postseason
from routes.matchups import create_matchups_router
from src.ui.matchup_season import render_season_week


def fixture(league_id="A", *, missing=False):
    league = {"league_id": league_id, "season": "2026", "sport": "nfl", "status": "in_season",
              "settings": {"leg": 2, "last_scored_leg": 1, "start_week": 1, "playoff_week_start": 14,
                           "playoff_teams": 6, "playoff_round_type": 1, "playoff_type": 0}}
    rows = [{"roster_id": rid, "matchup_id": 1, "starters": [str(rid)], "points": 0,
             "starters_points": [0], "players": [str(rid)], "players_points": {str(rid): 0}} for rid in (1, 2)]
    async def fetch(path):
        return copy.deepcopy(rows)
    prepared = asyncio.run(prepare_season_matchups(league, 2, rows, fetch, observed_at="2026-09-20T00:00:00Z"))
    data = {"league": league, "week": 2, "season_matchups": prepared, "roster_positions": ["QB", "BN"],
            "teams": [{"roster_id": rid, "team_name": f"{league_id} team {rid}"} for rid in (1, 2)],
            "players": {str(rid): {"full_name": f"Player {rid}"} for rid in (1, 2)}}
    pinned = {"league_id": league_id, "season": 2026, "horizon_generation": "g1"}
    calls = []
    def snapshot(week, *, generation_snapshot):
        calls.append((week, generation_snapshot))
        return {**pinned, "week": week, "projection_snapshot_id": f'p{week}', "players": {"1": {"canonical_projection": 0, "sleeper_web_display_projection": "0.00"},
                                                   "2": {"canonical_projection": None if missing else 27.335, "sleeper_web_display_projection": "27.33"}}}
    return data, SimpleNamespace(snapshot=lambda: pinned, week_snapshot=snapshot), calls


class SeasonMatchupTests(unittest.TestCase):
    def test_preparation_bounded_and_unchanged_semantics_deduplicate(self):
        data, _, _ = fixture()
        seen = []
        async def fetch(path):
            seen.append(path)
            return data["season_matchups"]["weeks"]["2"]["rows"]
        again = asyncio.run(prepare_season_matchups(data["league"], 2, data["season_matchups"]["weeks"]["2"]["rows"], fetch, observed_at="later"))
        self.assertEqual(again["semantic_generation"], data["season_matchups"]["semantic_generation"])
        self.assertEqual(len(seen), 16)
        self.assertNotIn("/league/A/matchups/2", seen)

    def test_future_week_uses_pinned_exact_values_and_true_zero(self):
        data, service, calls = fixture()
        before = copy.deepcopy(data)
        view = season_week_view(data, 3, service)
        self.assertEqual([s["projection"] for s in view["groups"]["1"]], [0, 27.335])
        body = render_season_week(view, matchup_id="1")
        self.assertIn("27.33", body)
        self.assertIn("0.00", body)
        self.assertIn('/players/2', body)
        self.assertNotIn("Actual score", body)
        self.assertEqual(calls[0][0], 3)
        self.assertEqual(data, before)

    def test_history_never_reads_current_projections_or_current_roster(self):
        data, service, calls = fixture()
        data["teams"][0]["players"] = [{"id": "999"}]
        view = season_week_view(data, 1, service)
        self.assertEqual(calls, [])
        self.assertEqual(view["groups"]["1"][0]["actual"], 0)
        self.assertIsNone(view["groups"]["1"][0]["projection"])
        self.assertEqual(view["groups"]["1"][0]["lineup"][0]["player_id"], "1")

    def test_missing_remains_unavailable_partial_not_complete(self):
        data, service, _ = fixture(missing=True)
        data["roster_positions"] = ["QB", "SUPER_FLEX"]
        side = season_week_view(data, 3, service)["groups"]["1"][0]
        self.assertIsNone(side["projection"])
        self.assertEqual(side["known_subtotal"], 0)
        self.assertEqual(side["coverage"], "partial")

    def test_wrong_league_calendar_and_generation_fail_closed(self):
        data, service, _ = fixture()
        other, wrong, _ = fixture("B")
        self.assertIsNone(season_week_view(data, 3, wrong)["projection_generation"])
        data["season_matchups"] = other["season_matchups"]
        self.assertEqual(season_week_view(data, 3, service)["availability"], "unavailable")
        data, service, _ = fixture()
        data["league"]["settings"]["playoff_teams"] = 4
        self.assertEqual(season_week_view(data, 3, service)["groups"], {})

    def test_playoff_source_placeholders_do_not_lock_opponent(self):
        data, service, _ = fixture()
        view = season_week_view(data, 16, service)
        self.assertEqual(view["round_weeks"], [16, 17])
        self.assertEqual(view["groups"], {})
        self.assertFalse(view["round_complete"])
        self.assertIn("opponents not established", render_season_week(view))

    def test_failed_source_does_not_retain_stale_current_availability(self):
        data, _, _ = fixture()
        async def fetch(path):
            raise TimeoutError()
        changed = asyncio.run(prepare_season_matchups(data["league"], 2, [], fetch, observed_at="later"))
        self.assertEqual(changed["weeks"]["3"]["availability"], "unavailable")
        self.assertEqual(changed["weeks"]["2"]["rows"], [])

    def test_duplicate_roster_source_is_not_accepted(self):
        self.assertIsNone(compact_week([{"roster_id": 1}, {"roster_id": 1}]))

    def test_invalid_source_collections_fail_closed(self):
        for invalid in ({"starters": "123"}, {"players_points": [0]}, {"matchup_id": -1}):
            self.assertIsNone(compact_week([{"roster_id": 1, **invalid}]))

    def test_mid_read_projection_publication_cannot_mix_generations(self):
        data, service, _ = fixture()
        initial = service.snapshot()
        def week_snapshot(week, *, generation_snapshot):
            service.snapshot = lambda: {**initial, "horizon_generation": "new"}
            return {**generation_snapshot, "week": week, "players": {"1": {"canonical_projection": 11}, "2": {"canonical_projection": 22}}}
        service.week_snapshot = week_snapshot
        view = season_week_view(data, 3, service)
        self.assertEqual(view['projection_generation'], 'g1')
        self.assertEqual([s['projection'] for s in view['groups']['1']], [11, 22])

    def test_read_rejects_week_snapshot_from_different_generation(self):
        data, service, _ = fixture()
        service.week_snapshot = lambda week, **kw: {**service.snapshot(), 'horizon_generation': 'new', 'week': week,
                                                   'players': {'1': {'canonical_projection': 99}}}
        view = season_week_view(data, 3, service)
        self.assertIsNone(view['projection_generation'])
        self.assertIsNone(view['groups']['1'][0]['projection'])

    def test_scoring_change_never_reuses_old_projection(self):
        data, service, calls = fixture()
        data['league']['scoring_settings'] = {'pass_td': 6}
        view = season_week_view(data, 3, service)
        self.assertEqual(calls, [])
        self.assertIsNone(view['groups']['1'][0]['projection'])

    def test_prepared_optimal_is_separate_and_never_calculated_on_read(self):
        data, service, _ = fixture()
        profile = {'teams': {'1': {'weekly': {3: {'projection_snapshot_id': 'p3',
                    'optimal': {'available': True, 'projected_points': 40, 'entries': []}}}}}}
        with patch('services.matchup_season.compatible_profile', return_value=profile), \
                patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('request optimization')):
            view = season_week_view(data, 3, service)
        side = view['groups']['1'][0]
        self.assertEqual(side['projection'], 0)
        self.assertEqual(side['optimal']['projected_points'], 40)
        self.assertIn('Optimal legal lineup projection: <b>40.00', render_season_week(view))
        profile['teams']['1']['weekly'][3]['projection_snapshot_id'] = 'stale'
        with patch('services.matchup_season.compatible_profile', return_value=profile):
            self.assertIsNone(season_week_view(data, 3, service)['groups']['1'][0]['optimal'])

    def test_pregame_live_and_final_comparisons_do_not_conflate_scores(self):
        data, service, _ = fixture()
        self.assertIn('A team 2 has the projected edge', render_season_week(season_week_view(data, 2, service)))
        for row, score in zip(data['season_matchups']['weeks']['2']['rows'], (20, 1)):
            row['points'] = score
        self.assertIn('A team 1 leads', render_season_week(season_week_view(data, 2, service)))
        data['season_matchups']['weeks']['1']['rows'][0]['points'] = 5
        self.assertIn('A team 1 wins', render_season_week(season_week_view(data, 1, service)))

    def test_historical_bench_is_source_week_not_current_roster(self):
        data, service, _ = fixture()
        data['season_matchups']['weeks']['1']['rows'][0]['players'].append('88')
        data['season_matchups']['weeks']['1']['rows'][0]['players_points']['88'] = 4.25
        data['teams'][0]['players'] = ['999']
        side = season_week_view(data, 1, service)['groups']['1'][0]
        self.assertEqual([(p['player_id'], p['actual'], p['projection']) for p in side['bench']], [('88', 4.25, None)])

    def test_bracket_evidence_required_for_locks_and_bye_is_qualified(self):
        data, _, _ = fixture()
        calendar = season_week_view(data, 14, None)['calendar']
        bracket = [
            {'m': 1, 'r': 1, 't1': 3, 't2': 6, 'w': 3},
            {'m': 2, 'r': 1, 't1': 4, 't2': 5, 'w': 4},
            {'m': 3, 'r': 2, 't1': 1, 't2': {'w': 1}},
            {'m': 4, 'r': 2, 't1': 2, 't2': {'w': 2}},
            {'m': 5, 'r': 3, 'p': 1, 't1': {'w': 3}, 't2': {'w': 4}}]
        prepared = {'brackets': {'winners_bracket': bracket}}
        self.assertEqual(_postseason(prepared, calendar, 14, 12)['pairs'], {})
        opening = _postseason(prepared, calendar, 14, 13)
        self.assertEqual(opening['byes'], [1, 2])
        self.assertIn(frozenset({3, 6}), opening['pairs'])
        self.assertEqual(_postseason(prepared, calendar, 15, 13)['pairs'], {})
        self.assertIn(frozenset({1, 3}), _postseason(prepared, calendar, 15, 14)['pairs'])
        self.assertEqual(_postseason(prepared, calendar, 16, 15)['pairs'], {})

    def test_multweek_parent_cannot_lock_from_one_component_result(self):
        data, _, _ = fixture()
        calendar = season_week_view(data, 14, None)['calendar']
        calendar['playoff_rounds'] = [[13, 14], [15, 16], [17, 18]]
        prepared = {'brackets': {'winners_bracket': [
            {'m': 1, 'r': 1, 't1': 3, 't2': 6, 'w': 3},
            {'m': 2, 'r': 2, 't1': 1, 't2': {'w': 1}}]}}
        self.assertEqual(_postseason(prepared, calendar, 15, 13)['pairs'], {})
        self.assertIn(frozenset({1, 3}), _postseason(prepared, calendar, 15, 14)['pairs'])

    def test_active_routes_do_not_run_intelligence_or_mutate_active_week(self):
        data, service, _ = fixture()
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: data,
                                                  page=lambda title, body: HTMLResponse(body)))
        with patch("routes.matchups.current_league_context", return_value=SimpleNamespace(projection=service)), \
                patch("services.matchup_intelligence.matchup_player_values", side_effect=AssertionError("expensive construction")), \
                patch("services.matchup_intelligence.matchup_projection", side_effect=AssertionError("wrong week projection")):
            client = TestClient(app)
            for path in ("/matchups", "/matchups?week=3", "/matchups/1?week=3"):
                result = client.get(path)
                self.assertEqual(result.status_code, 200)
                self.assertIn("Matchup week navigation", result.text)
            self.assertEqual(client.get("/matchups?week=99").status_code, 422)
        self.assertEqual(data["week"], 2)

    def test_confirmed_bye_survives_missing_weekly_scores(self):
        data, service, _ = fixture()
        view = season_week_view(data, 2, service)
        view.update(availability='unavailable', byes=[{'roster_id': 1, 'team': 'Qualified'}])
        rendered = render_season_week(view)
        self.assertIn('First-round bye · qualified for the playoffs', rendered)
        self.assertIn('Week evidence unavailable', rendered)

    def test_multiweek_final_preserves_components_until_complete(self):
        from src.core.intelligence.season_calendar import season_calendar
        data, service, _ = fixture()
        data['season_matchups']['brackets'] = {'winners_bracket': [
            {'m': 5, 'r': 3, 't1': 1, 't2': 2, 'p': 1}]}
        data['week'] = 17
        data['league']['settings'].update(leg=17, last_scored_leg=16)
        data['season_matchups']['calendar_reference'] = season_calendar(data['league'])['reference']
        for week, scores in ((16, (150, 100)), (17, (70, 90))):
            for row, score in zip(data['season_matchups']['weeks'][str(week)]['rows'], scores):
                row['points'] = score
        partial = season_week_view(data, 17, service)
        self.assertEqual(partial['round_weeks'], [16, 17])
        self.assertFalse(partial['round_complete'])
        self.assertIsNone(partial['groups']['1'][0]['round_actual'])
        self.assertIn('Round unresolved', render_season_week(partial))
        data['week'] = 18
        data['league']['settings'].update(leg=18, last_scored_leg=17)
        data['season_matchups']['calendar_reference'] = season_calendar(data['league'])['reference']
        final = season_week_view(data, 17, service)
        self.assertTrue(final['round_complete'])
        self.assertEqual([s['round_actual'] for s in final['groups']['1']], [220, 190])
        body = render_season_week(final)
        self.assertIn('Week 16: 150.00', body)
        self.assertIn('Week 17: 70.00', body)
        self.assertIn('Complete round score: <b>220.00', body)
        self.assertIn('A team 1 wins the round', body)

    def test_active_route_round_trip_restores_exact_league_view(self):
        first, first_service, _ = fixture()
        second, _, _ = fixture('B')
        for team in second['teams']:
            team['team_name'] = 'Second league ' + str(team['roster_id'])
        state = {'data': first, 'service': first_service}
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: state['data'],
            page=lambda title, body: HTMLResponse(body)))
        with patch('routes.matchups.current_league_context', side_effect=lambda: SimpleNamespace(projection=state['service'])):
            with TestClient(app) as client:
                initial = client.get('/matchups/1?week=2').text
                state.update(data=second, service=first_service)
                foreign = client.get('/matchups/1?week=2').text
                self.assertIn('Second league 1', foreign)
                self.assertNotIn('A team 1', foreign)
                self.assertIn('Projection unavailable', foreign)
                state.update(data=first, service=first_service)
                self.assertEqual(client.get('/matchups/1?week=2').text, initial)

    def test_final_week_navigation_is_local_and_canonical_projection_is_unchanged(self):
        data, service, _ = fixture('1313066632158924800')
        before = copy.deepcopy(data)
        pinned = service.snapshot()
        canonical = service.week_snapshot(3, generation_snapshot=pinned)
        view = season_week_view(data, 3, service)
        for side in view['groups']['1']:
            for player in side['lineup']:
                row = canonical['players'][player['player_id']]
                self.assertEqual(player['projection'], row['canonical_projection'])
                self.assertEqual(player['projection_display'], row['sleeper_web_display_projection'])
        body = render_season_week(view)
        for label in ('Previous week', 'Next week', 'Current week', 'Go to week'):
            self.assertIn(label, body)
        self.assertEqual(data, before)

    def test_unprepared_cache_cannot_enter_legacy_analysis(self):
        data, service, _ = fixture()
        data.pop('season_matchups')
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: data,
            page=lambda title, body: HTMLResponse(body)))
        with patch('routes.matchups.current_league_context', return_value=SimpleNamespace(projection=service)), \
                patch('services.matchup_intelligence.matchup_projection', side_effect=AssertionError('legacy fallback')):
            response = TestClient(app).get('/matchups')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Week evidence unavailable', response.text)


if __name__ == "__main__":
    unittest.main()
