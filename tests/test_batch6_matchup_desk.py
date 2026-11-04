import unittest
import copy
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from routes.matchups import create_matchups_router
from services.matchup_desk import pregame_desk, postgame_desk, matchup_desk, live_desk, _lineup_opportunity, _slot_edges
from services.matchup_season import season_week_view
from src.ui.matchup_season import render_desk
from tests.test_batch6_matchup_season import fixture


class PregameDeskTests(unittest.TestCase):
    def test_active_route_modes_roundtrip_and_unchanged_replay(self):
        first, first_service, _ = fixture()
        second, second_service, _ = fixture('B')
        first['season_matchups']['weeks']['2']['rows'][0]['points'] = 12
        before = copy.deepcopy(first)
        state = {'data': first, 'service': first_service}
        app = FastAPI()
        async def fresh():
            pass
        app.include_router(create_matchups_router(ensure_fresh=fresh, require_data=lambda: state['data'],
            page=lambda title, body: HTMLResponse(body)))
        with patch('routes.matchups.current_league_context', side_effect=lambda: SimpleNamespace(projection=state['service'])):
            with TestClient(app) as client:
                styles = client.get('/static/css/matchups.css')
                self.assertEqual(styles.status_code, 200)
                self.assertIn('text/css', styles.headers['content-type'])
                self.assertIn('.season-sides', styles.text)
                initial = client.get('/matchups/1?week=3').text
                self.assertIn('data-desk-mode="pregame"', initial)
                self.assertLess(initial.index('Source-listed lineup projection'), initial.index('Matchup Desk'))
                self.assertIn('data-desk-mode="live"', client.get('/matchups/1?week=2').text)
                self.assertIn('data-desk-mode="postgame"', client.get('/matchups/1?week=1').text)
                state.update(data=second, service=second_service)
                other = client.get('/matchups/1?week=3').text
                self.assertIn('B team 2', other)
                self.assertNotIn('A team', other)
                state.update(data=first, service=first_service)
                for _ in range(100):
                    self.assertEqual(client.get('/matchups/1?week=3').text, initial)
        self.assertEqual(first, before)

    def test_live_snapshot_leader_is_not_winner_or_movement(self):
        data, service, _ = fixture()
        data['season_matchups']['weeks']['2']['rows'][0]['points'] = 12
        view = season_week_view(data, 2, service)
        result = matchup_desk(data, view, '1')
        self.assertEqual(result['mode'], 'live')
        self.assertEqual(result['leader'], 1)
        for field in ('winner', 'movement', 'win_probability', 'players_remaining', 'provider_updated_at'):
            self.assertIsNone(result[field])
        self.assertEqual(result['observed_at'], view['observed_at'])
        self.assertEqual(result, matchup_desk(data, view, '1'))
        body = render_desk(result)
        self.assertIn('retrieval time', body)
        self.assertIn('not a final result', body)

    def test_live_missing_and_true_zero_remain_distinct(self):
        data, service, _ = fixture()
        view = season_week_view(data, 2, service)
        view['states']['1'] = 'in-game'
        result = live_desk(view, '1')
        self.assertEqual(result['margin'], 0)
        self.assertIsNone(result['leader'])
        view['groups']['1'][0]['actual'] = None
        result = live_desk(view, '1')
        self.assertEqual(result['availability'], 'partial')
        self.assertIsNone(result['margin'])

    def test_dispatch_reuses_pinned_projection_and_future_label(self):
        data, service, calls = fixture()
        view = season_week_view(data, 3, service)
        count = len(calls)
        result = matchup_desk(data, view, '1')
        self.assertEqual(len(calls), count)
        self.assertEqual(result['mode'], 'pregame')
        self.assertNotIn('submitted', render_desk(result))
        self.assertEqual(matchup_desk(data, season_week_view(data, 1, service), '1')['mode'], 'postgame')
        self.assertIsNone(matchup_desk(data, view, 'missing'))

    def test_postgame_uses_actuals_and_does_not_invent_projected_upset(self):
        data, _, _ = fixture()
        rows = data['season_matchups']['weeks']['1']['rows']
        rows[0]['points'], rows[1]['points'] = 10, 20
        rows[0]['starters_points'] = [10]
        rows[1]['starters_points'] = [20]
        result = postgame_desk(data, 1, 1)
        self.assertEqual(result['weekly_winner'], 2)
        self.assertEqual(result['contributors'][0]['actual'], 10)
        self.assertIsNone(result['projected_upset'])
        self.assertEqual(result['lineup_decision']['availability'], 'unavailable')

    def test_postgame_never_declares_unfinished_matchup(self):
        data, _, _ = fixture()
        self.assertEqual(postgame_desk(data, 3, 1)['availability'], 'unavailable')

    def test_equal_optimal_has_no_false_opportunity(self):
        side = {'projection': 10, 'optimal': {'available': True, 'projected_points': 10}}
        self.assertFalse(_lineup_opportunity(side)['opportunity'])
        side['optimal']['projected_points'] = 12
        self.assertEqual(_lineup_opportunity(side)['gain'], 2)
        side['projection'] = None
        self.assertEqual(_lineup_opportunity(side)['availability'], 'unavailable')

    def test_slot_edges_keep_flex_distinct_and_missing_unavailable(self):
        sides = [{'roster_id': rid, 'lineup': [
            {'slot': 'QB', 'projection': score}, {'slot': 'FLEX', 'projection': None}]}
            for rid, score in ((1, 0), (2, 10))]
        rows = {row['slot']: row for row in _slot_edges(sides)}
        self.assertEqual(rows['QB']['edge_roster_id'], 2)
        self.assertEqual(rows['FLEX']['availability'], 'unavailable')

    def test_partial_has_no_forced_smack_talk(self):
        data, service, _ = fixture(missing=True)
        self.assertIsNone(pregame_desk(data, 3, 1, service)['smack_talk'])

    def test_supported_zero_does_not_hide_favorite(self):
        data, service, _ = fixture()
        result = pregame_desk(data, 3, 1, service)
        self.assertEqual(result['favorite'], 2)
        self.assertEqual(result['projected_margin'], 27.335)
        self.assertEqual(result['teams'][0]['submitted_projection'], 0)
        self.assertEqual(result, pregame_desk(data, 3, 1, service))

    def test_missing_does_not_become_zero_or_underdog(self):
        data, service, _ = fixture(missing=True)
        result = pregame_desk(data, 3, 1, service)
        self.assertEqual(result['availability'], 'partial')
        self.assertIsNone(result['favorite'])
        self.assertIsNone(result['projected_margin'])

    def test_final_does_not_become_pregame(self):
        data, service, _ = fixture()
        self.assertEqual(pregame_desk(data, 1, 1, service)['availability'], 'unavailable')

    def test_foreign_projections_do_not_enter_preview(self):
        data, _, _ = fixture()
        _, other, _ = fixture('B')
        self.assertIsNone(pregame_desk(data, 3, 1, other)['favorite'])

    def test_unlocked_future_playoff_has_no_fabricated_opponent(self):
        data, service, _ = fixture()
        result = pregame_desk(data, 16, 1, service)
        self.assertFalse(result['playoff']['opponents_locked'])
        self.assertEqual(result['teams'], [])
