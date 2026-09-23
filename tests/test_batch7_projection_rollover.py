"""Season rollover must not revive a compatible-looking wrong projection."""
import asyncio
import copy
import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.core.projection_intelligence.service import ProjectionService


class ProjectionRolloverTests(unittest.TestCase):
    def test_restore_checks_season_week_scoring_and_league_without_writes(self):
        service = object.__new__(ProjectionService)
        service._lock = threading.RLock()
        service._snapshot = {'league_id': 'A', 'season': 2026, 'week': 3,
                             'scoring_settings': {'rec': 1}, 'players': {}}
        data = {'league': {'league_id': 'A', 'season': '2026'},
                'week': 3, 'scoring_settings': {'rec': 1}}
        for change in ({'week': 4}, {'season': 2027},
                       {'scoring_settings': {'rec': .5}},
                       {'league': {'league_id': 'B', 'season': '2026'}}):
            with self.subTest(change=change):
                candidate = {**copy.deepcopy(data), **change}
                before = copy.deepcopy(candidate)
                self.assertFalse(service.restore_into(candidate))
                self.assertEqual(candidate, before)
        self.assertTrue(service.restore_into(data))
        self.assertIs(data['projection_intelligence'], service._snapshot)

    def test_active_sync_requests_selected_league_season_not_global_next_season(self):
        from services import sleeper

        league = {'league_id': 'batch7-test', 'season': '2026', 'settings': {'leg': 1}}
        async def source(_client, path):
            if path == '/league/batch7-test':
                return league
            if path == '/state/nfl':
                return {'season': '2027', 'week': 1, 'season_type': 'pre'}
            if path == '/players/nfl':
                return {}
            return []

        state = {'syncing': False, 'data': {}}
        projections = Mock()
        projections.begin_external_refresh.return_value = True
        # Stop after the bounded source handoff: no downstream canonical writes.
        fetch = AsyncMock(side_effect=RuntimeError('test source unavailable'))
        with patch.object(sleeper, 'sleeper_get', side_effect=source), \
                patch.object(sleeper, 'refresh_public_market', new=AsyncMock(return_value={})), \
                patch('services.matchup_season.prepare_season_matchups', new=AsyncMock(return_value={})), \
                patch.object(sleeper.SLEEPER_PROJECTION_CLIENT, 'fetch', fetch), \
                patch.object(sleeper, 'player_history_evidence_batch', side_effect=RuntimeError('test boundary stop')), \
                patch.object(sleeper, 'save_cache') as save:
            asyncio.run(sleeper._sync_sleeper(league_id='batch7-test', state=state, projections=projections))
        self.assertEqual(fetch.await_args.kwargs['season'], 2026)
        self.assertEqual(fetch.await_args.kwargs['week'], 1)
        save.assert_not_called()
        self.assertFalse(state['syncing'])

    def test_completed_league_keeps_its_week_when_global_clock_rolls_over(self):
        from services.sleeper import selected_league_week

        prior = {'season': '2026', 'status': 'complete', 'settings': {'leg': 17}}
        next_global = {'season': '2027', 'week': 1, 'season_type': 'pre'}
        self.assertEqual(selected_league_week(prior, next_global), 17)
        current = {'season': '2027', 'status': 'in_season', 'settings': {'leg': 3}}
        self.assertEqual(selected_league_week(
            current, {'season': '2027', 'week': 4, 'season_type': 'regular'}), 4)
        with self.assertRaises(ValueError):
            selected_league_week({'season': '2027', 'settings': {}}, next_global)

    def test_failed_candidate_preparation_restores_exact_last_valid_state(self):
        from services import sleeper

        league = {'league_id': 'batch7-test', 'season': '2026', 'sport': 'nfl',
                  'status': 'in_season', 'settings': {'leg': 2},
                  'scoring_settings': {}, 'roster_positions': []}
        previous = {'league': {'league_id': 'batch7-test', 'season': '2026'}, 'marker': 'last-valid'}
        state = {'syncing': False, 'data': previous, 'last_sync': 'old-sync',
                 'transactions_last_sync': 'old-transactions', 'transactions_last_error': None}

        async def source(_client, path):
            values = {
                '/league/batch7-test': league,
                '/state/nfl': {'season': '2026', 'week': 2, 'season_type': 'regular'},
                '/players/nfl': {},
            }
            return values.get(path, [])

        projections = Mock()
        projections.begin_external_refresh.return_value = False
        with patch.object(sleeper, 'sleeper_get', side_effect=source), \
                patch.object(sleeper, 'refresh_public_market', new=AsyncMock(return_value={'provider_status': {}})), \
                patch('services.matchup_season.prepare_season_matchups', new=AsyncMock(return_value={})), \
                patch.object(sleeper, 'player_history_evidence_batch', return_value={}), \
                patch('src.core.intelligence.pick_context.prepare_pick_context', side_effect=RuntimeError('controlled candidate failure')), \
                patch.object(sleeper, 'save_cache') as save:
            asyncio.run(sleeper._sync_sleeper(league_id='batch7-test', state=state, projections=projections))
        self.assertIs(state['data'], previous)
        self.assertEqual(state['last_sync'], 'old-sync')
        self.assertEqual(state['transactions_last_sync'], 'old-transactions')
        self.assertIn('controlled candidate failure', state['last_error'])
        self.assertFalse(state['syncing'])
        save.assert_not_called()
