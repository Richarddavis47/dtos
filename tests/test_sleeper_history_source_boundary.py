import unittest
from unittest.mock import patch

from src.core.intelligence_memory.sleeper_source import SleeperHistoricalSource
from src.core.history_context.season_cache import SleeperSeasonCache


class SleeperSourceBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_buckets_keep_exact_week_and_draft_identity(self):
        source = SleeperHistoricalSource()

        async def get(client, path):
            if path == '/league/L':
                return {'league_id': 'L', 'season': '2025'}
            if '/matchups/' in path:
                return [{'source_week': int(path.rsplit('/', 1)[1])}]
            if '/transactions/' in path:
                return [{'source_week': int(path.rsplit('/', 1)[1])}]
            if path.endswith('/drafts'):
                return [{'draft_id': 'D', 'status': 'complete',
                         'start_time': 1745715619387, 'last_picked': 1745893358447}]
            if path == '/draft/D/picks':
                return [{'pick_no': 1, 'roster_id': 1}]
            return []

        with patch.object(source, '_get', side_effect=get):
            facts = await source.completed_season_facts('L', 2025)
        self.assertNotIn('0', facts['matchups'])
        self.assertEqual(facts['matchups']['1'][0]['source_week'], 1)
        self.assertEqual(facts['transactions']['0'][0]['source_week'], 0)
        self.assertEqual(facts['transactions']['18'][0]['source_week'], 18)
        self.assertEqual(facts['draft_picks'][0]['draft_id'], 'D')
        self.assertEqual(facts['draft_picks'][0]['draft_status'], 'complete')
        self.assertTrue(facts['draft_picks'][0]['draft_start_at'].startswith('2025-04-27'))
        self.assertNotIn('occurred_at', facts['draft_picks'][0])

    async def test_wrong_league_cannot_enter_cache(self):
        source = SleeperHistoricalSource()
        with patch.object(source, '_get', return_value={'league_id': 'OTHER', 'season': '2025'}):
            with self.assertRaises(ValueError):
                await source.completed_season_facts('L', 2025)

    def test_unavailable_week_is_not_reported_as_full_coverage(self):
        facts = {key: [] for key in ('users', 'rosters', 'drafts', 'draft_picks',
                 'traded_picks', 'winners_bracket', 'losers_bracket')}
        facts.update({'league': {}, 'matchups': {'1': None}, 'transactions': {'1': []}})
        normalized = SleeperSeasonCache.normalize('L', 2025, facts)
        self.assertEqual(normalized.completeness['matchups'], 'partial')
        self.assertEqual(normalized.completeness['transactions'], 'available')
        self.assertEqual(normalized.status, 'partial')
