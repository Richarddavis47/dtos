import asyncio
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.core.history_context import store as history
from src.core.history_context.season_cache import SleeperSeasonCache
from src.core.history_context.recovery import HistoricalCheckpoints, HistoricalRecoveryUnavailable


class HistoricalReaderRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = SleeperSeasonCache(Path(self.temp.name))
        self.patch = patch.object(history, 'sleeper_season_cache', self.cache)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.reader = history.CanonicalHistoryStore()
        self.facts = {'league': {'league_id': 'source-2021', 'season': '2021', 'status': 'complete'},
                      'rosters': [{'roster_id': 1, 'owner_id': 'old-owner', 'players': ['old-player'],
                                   'settings': {'wins': 9, 'losses': 5}}],
                      'transactions': {'2': [{'transaction_id': 't', 'type': 'trade', 'status': 'complete',
                                              'created': 1631000000000, 'adds': {'old-player': 1}, 'drops': {'old-player': 2}}]}}
        self.cache.write(self.cache.normalize('A', 2021, self.facts))

    def preserve(self):
        return self.reader.preserve_reader_checkpoint('A', 2021, current_season=2026)

    def test_missing_identity_is_unavailable_before_and_after_eviction(self):
        with self.assertRaises(HistoricalRecoveryUnavailable):
            self.reader.records('A', 'franchise_identity', season=2021)
        before = self.reader.records('A', None, season=2021, limit=None)
        self.preserve()
        self.cache.delete('A', 2021)
        with self.assertRaises(HistoricalRecoveryUnavailable):
            self.reader.records('A', 'franchise_identity', season=2021)
        self.assertEqual(before, self.reader.records('A', None, season=2021, limit=None))
        self.cache.write(self.cache.normalize('A', 2021, self.facts))
        self.assertEqual(before, self.reader.records('A', None, season=2021, limit=None))

    def test_front_office_history_preserves_partial_families_across_eviction(self):
        from src.core.historical_memory.graph import HistoricalAssetGraph
        before = HistoricalAssetGraph(self.reader, 'A', {}).franchise_history('1')
        self.assertEqual(len(before['standings']), 1)
        self.assertEqual(before['identities'], [])
        self.assertIn('franchise_identity', before['partial_historical_families'])
        self.preserve()
        self.cache.delete('A', 2021)
        after = HistoricalAssetGraph(history.CanonicalHistoryStore(), 'A', {}).franchise_history('1')
        self.assertEqual(before, after)

    def test_turnover_admission_failure_keeps_every_raw_cache(self):
        from src.platform.cache_budget import CacheAdmissionError
        for year in range(2022, 2027):
            facts = {**self.facts, 'league': {'league_id': f'source-{year}', 'season': str(year)}}
            self.cache.write(self.cache.normalize('A', year, facts))
        before = {year: self.cache.path('A', year).read_bytes() for year in range(2021, 2027)}
        incoming = self.cache.normalize('A', 2027, {'league': {'season': '2027'}})
        async def fetch(*args):
            return self.facts
        with patch('src.platform.cache_budget.require', side_effect=CacheAdmissionError('disk reserve')):
            with self.assertRaises(CacheAdmissionError):
                asyncio.run(self.reader.publish_with_verified_turnover('A', 2027, incoming, fetch))
        self.assertEqual(tuple(before), self.cache.available_seasons('A'))
        for year, body in before.items():
            self.assertEqual(body, self.cache.path('A', year).read_bytes())

    def test_failed_atomic_publication_preserves_verified_turnover_source(self):
        old = self.cache.read('A', 2021)
        before = self.cache.path('A', 2021).read_bytes()
        incoming = self.cache.normalize('A', 2027, {'league': {'season': '2027'}})
        with patch('src.core.history_context.season_cache.os.replace', side_effect=OSError('publication failed')):
            with self.assertRaisesRegex(OSError, 'publication failed'):
                self.cache.write(incoming, verified_evictions={2021: old.checksum})
        self.assertEqual(before, self.cache.path('A', 2021).read_bytes())
        self.assertFalse(self.cache.path('A', 2027).exists())

    def test_changed_turnover_source_is_rejected_under_publication_lock(self):
        from src.platform.cache_budget import CacheAdmissionError
        old = self.cache.read('A', 2021)
        changed = self.cache.normalize('A', 2021, {**self.facts, 'rosters': []})
        self.cache.write(changed)
        incoming = self.cache.normalize('A', 2027, {'league': {'season': '2027'}})
        with self.assertRaisesRegex(CacheAdmissionError, 'source changed'):
            self.cache.write(incoming, verified_evictions={2021: old.checksum})
        self.assertEqual(self.cache.read('A', 2021).checksum, changed.checksum)
        self.assertFalse(self.cache.path('A', 2027).exists())

    def test_three_families_survive_eviction_restart_and_source_outage(self):
        kinds = ('trade', 'season_standing', 'roster_snapshot')
        before = {kind: self.reader.records('A', kind, season=2021) for kind in kinds}
        self.preserve()
        self.cache.delete('A', 2021)
        reader = history.CanonicalHistoryStore()
        reader.update_current('A', {'league': {'league_id': 'A', 'season': '2026'},
                                    'teams': [{'roster_id': 1, 'owner_id': 'new-owner'}]})
        async def offline(*args):
            raise OSError('offline')
        result = asyncio.run(reader.recover_historical_season('A', 2021, offline))
        self.assertEqual(result['state'], 'partial')
        for kind in kinds:
            self.assertEqual(before[kind], reader.records('A', kind, season=2021))
            _, all_rows = reader.records('A', kind, limit=None)
            historical = [row for row in all_rows if row['season'] == 2021]
            self.assertEqual(before[kind], (len(historical), historical))
            self.assertEqual(reader.records('A', kind, season=2020), (0, []))
        current_count, current = reader.records('A', 'roster_snapshot', season=2026)
        self.assertEqual(current_count, 1)
        self.assertEqual(current[0]['payload']['owner_id'], 'new-owner')
        self.assertEqual(before['roster_snapshot'][1][0]['payload']['owner_id'], 'old-owner')
        self.assertEqual(reader.records('A', 'roster_snapshot')[0], 2)
        self.assertIsNone(self.cache.read('A', 2021))

    def test_exact_refetch_uses_original_league_not_alias(self):
        self.preserve()
        self.cache.delete('A', 2021)
        async def fetch(league, season):
            self.assertEqual((league, season), ('source-2021', 2021))
            return self.facts
        result = asyncio.run(self.reader.recover_historical_season('A', 2021, fetch))
        self.assertEqual(result['state'], 'cached')
        self.assertEqual(self.cache.read('A', 2021).facts, self.facts)

    def test_changed_source_cannot_replace_old_truth(self):
        self.preserve()
        before = self.reader.records('A', 'season_standing', season=2021)
        self.cache.delete('A', 2021)
        async def fetch(*args):
            return {**self.facts, 'rosters': []}
        result = asyncio.run(self.reader.recover_historical_season('A', 2021, fetch))
        self.assertEqual(result['recovery_error'], 'HistoricalRecoveryUnavailable')
        self.assertEqual(before, self.reader.records('A', 'season_standing', season=2021))
        self.assertIsNone(self.cache.read('A', 2021))

    def test_checkpoint_replay_is_byte_identical_and_contains_no_broad_season(self):
        self.preserve()
        checkpoints = HistoricalCheckpoints(self.cache.root)
        path = checkpoints.path('A', 2021)
        before = path.read_bytes()
        for _ in range(100):
            self.assertFalse(self.preserve())
        self.assertEqual(before, path.read_bytes())
        value = checkpoints.read('A', 2021)
        self.assertTrue({'trade', 'season_standing', 'roster_snapshot', 'league_season'}
                        <= set(row['entity_type'] for row in value['records']))
        self.assertNotIn('franchise_identity', value['families'])
        self.assertNotIn('facts', value)

    def test_scope_and_protected_seasons(self):
        self.preserve()
        self.assertEqual(self.reader.records('B', 'trade', season=2021)[0], 0)
        self.assertEqual(self.reader.historical_availability('B', 2021)['state'], 'unavailable')
        with self.assertRaises(HistoricalRecoveryUnavailable):
            self.reader.preserve_reader_checkpoint('A', 2021, current_season=2022)

    def test_cache_quota_failure_keeps_compact_truth(self):
        self.preserve()
        self.cache.delete('A', 2021)
        for year in range(2022, 2028):
            self.cache.write(self.cache.normalize('A', year, {'league': {'season': year}}))
        async def fetch(*args):
            return self.facts
        result = asyncio.run(self.reader.recover_historical_season('A', 2021, fetch))
        self.assertEqual(result['state'], 'partial')
        self.assertEqual(self.reader.records('A', 'trade', season=2021)[0], 1)
        self.assertEqual(len(self.cache.available_seasons('A')), 6)

    def test_partial_source_preserves_supported_families_without_inventing_empty_trades(self):
        facts = {key: value for key, value in self.facts.items() if key != 'transactions'}
        self.cache.write(self.cache.normalize('A', 2021, facts))
        before = self.reader.records('A', 'roster_snapshot', season=2021)
        self.preserve()
        self.cache.delete('A', 2021)
        self.assertEqual(before, self.reader.records('A', 'roster_snapshot', season=2021))
        self.assertNotIn('trade', self.reader.historical_availability('A', 2021)['covered_families'])
        with self.assertRaises(HistoricalRecoveryUnavailable):
            self.reader.records('A', 'trade', season=2021)
        with self.assertRaises(HistoricalRecoveryUnavailable):
            self.reader.records('A', 'franchise_identity', season=2021)
        count, rows = self.reader.records('A', None, season=2021, limit=None)
        self.assertEqual(count, len(rows))
        self.assertEqual(
            {row['entity_type'] for row in rows},
            {'league_season', 'roster_snapshot', 'season_standing'},
        )

    def test_complete_family_inventory_survives_whole_season_eviction(self):
        facts = deepcopy(self.facts)
        facts.update({
            'users': [{'user_id': 'old-owner', 'display_name': 'Old GM'}],
            'matchups': {'1': [
                {'roster_id': 1, 'matchup_id': 1, 'points': 10, 'starters': ['p1'],
                 'players_points': {'p1': 10}},
                {'roster_id': 2, 'matchup_id': 1, 'points': 8, 'starters': ['p2'],
                 'players_points': {'p2': 8}},
            ]},
            'drafts': [{'draft_id': 'd1', 'season': '2021'}],
            'draft_picks': [{'draft_id': 'd1', 'pick_no': 1, 'roster_id': 1, 'player_id': 'p1'}],
            'traded_picks': [{'season': 2022, 'round': 1, 'roster_id': 1, 'owner_id': 2}],
            'winners_bracket': [{'m': 1, 'r': 1, 't1': 1, 't2': 2, 'w': 1, 'l': 2}],
            'losers_bracket': [],
        })
        self.cache.write(self.cache.normalize('A', 2021, facts))
        all_families = {
            'league_season', 'franchise_identity', 'roster_snapshot', 'season_standing',
            'player_week', 'matchup', 'trade', 'transaction', 'draft', 'draft_pick',
            'pick_snapshot', 'playoff_bracket', 'playoff_result',
        }
        before = {kind: self.reader.records('A', kind, season=2021, limit=None)
                  for kind in all_families}
        self.preserve()
        checkpoint = HistoricalCheckpoints(self.cache.root).read('A', 2021)
        self.assertEqual(set(checkpoint['families']), all_families)
        self.cache.delete('A', 2021)
        restarted = history.CanonicalHistoryStore()
        for kind, expected in before.items():
            self.assertEqual(expected, restarted.records('A', kind, season=2021, limit=None))
        self.assertEqual(restarted.season_player_leaders('A', 2021)[0], 2)
        self.assertTrue(restarted.ownership_observations('A'))
        recovered = restarted.recovered_season_source('A', 2021)
        self.assertEqual(recovered.facts['matchups']['1'][0]['players_points'], {'p1': 10})
        self.assertEqual(recovered.checksum, checkpoint['source_checksum'])

    def test_historical_identity_coverage_matrix_never_uses_current_users(self):
        cases = (
            ('users-present', [{'user_id': 'old-owner'}], True),
            ('users-absent', None, False),
            ('users-malformed', [{'display_name': 'Missing ID'}], False),
            ('users-incomplete', [{'user_id': 'someone-else'}], False),
        )
        for name, users, identity_available in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as folder:
                    cache = SleeperSeasonCache(Path(folder))
                    facts = deepcopy(self.facts)
                    if users is not None:
                        facts['users'] = users
                    cache.write(cache.normalize('A', 2021, facts))
                    with patch.object(history, 'sleeper_season_cache', cache):
                        reader = history.CanonicalHistoryStore()
                        reader.update_current('A', {'league': {'league_id': 'A', 'season': '2026'},
                                                    'teams': [{'roster_id': 1, 'owner_id': 'current-owner'}]})
                        reader.preserve_reader_checkpoint('A', 2021, current_season=2026)
                        cache.delete('A', 2021)
                        availability = reader.historical_availability('A', 2021)
                        self.assertEqual('franchise_identity' in availability['covered_families'], identity_available)
                        if identity_available:
                            rows = reader.records('A', 'franchise_identity', season=2021)[1]
                            self.assertEqual(rows[0]['payload']['owner_id'], 'old-owner')
                        else:
                            with self.assertRaises(HistoricalRecoveryUnavailable):
                                reader.records('A', 'franchise_identity', season=2021)
                        current = reader.records('A', 'franchise_identity', season=2026)[1]
                        self.assertEqual(current[0]['payload']['owner_id'], 'current-owner')

    def test_users_do_not_create_unsupported_non_identity_families(self):
        facts = {'league': self.facts['league'], 'users': [{'user_id': 'old-owner'}],
                 'rosters': self.facts['rosters']}
        self.cache.write(self.cache.normalize('A', 2021, facts))
        self.preserve()
        self.cache.delete('A', 2021)
        available = self.reader.historical_availability('A', 2021)['covered_families']
        self.assertIn('franchise_identity', available)
        self.assertNotIn('trade', available)
        self.assertNotIn('matchup', available)
        self.assertNotIn('draft', available)

    def test_verified_oldest_first_turnover_bounds_raw_cache_and_survives_restart(self):
        facts_by_season = {}
        for year in range(2021, 2027):
            facts = deepcopy(self.facts)
            facts['league'] = {**facts['league'], 'league_id': f'source-{year}', 'season': str(year)}
            facts['transactions']['2'][0]['transaction_id'] = f't-{year}'
            facts_by_season[year] = facts
            self.cache.write(self.cache.normalize('A', year, facts))
        incoming_facts = deepcopy(self.facts)
        incoming_facts['league'] = {**incoming_facts['league'], 'league_id': 'source-2027', 'season': '2027'}
        incoming = self.cache.normalize('A', 2027, incoming_facts)
        async def fetch(league, season):
            self.assertEqual(league, f'source-{season}')
            return facts_by_season[season]
        before = self.reader.records('A', 'trade', season=2021, limit=None)
        result = asyncio.run(self.reader.publish_with_verified_turnover('A', 2027, incoming, fetch))
        self.assertEqual([row['season'] for row in result['evicted']], [2021])
        self.assertEqual(result['retained_raw_seasons'], [2022, 2023, 2024, 2025, 2026, 2027])
        restarted = history.CanonicalHistoryStore()
        self.assertEqual(before, restarted.records('A', 'trade', season=2021, limit=None))

    def test_turnover_source_failure_or_change_removes_nothing(self):
        facts_by_season = {}
        for year in range(2021, 2027):
            facts = deepcopy(self.facts)
            facts['league'] = {**facts['league'], 'league_id': f'source-{year}', 'season': str(year)}
            facts_by_season[year] = facts
            self.cache.write(self.cache.normalize('A', year, facts))
        incoming = self.cache.normalize('A', 2027, {**deepcopy(self.facts),
            'league': {'league_id': 'source-2027', 'season': '2027'}})
        original = self.cache.available_seasons('A')
        async def changed(*args):
            return {**facts_by_season[2021], 'rosters': []}
        with self.assertRaisesRegex(HistoricalRecoveryUnavailable, 'proof failed'):
            asyncio.run(self.reader.publish_with_verified_turnover('A', 2027, incoming, changed))
        self.assertEqual(self.cache.available_seasons('A'), original)
        self.assertIsNone(self.cache.read('A', 2027))

    def test_turnover_never_evicts_current_or_prior(self):
        self.cache.delete('A', 2021)
        for year in (2027, 2028):
            facts = {**deepcopy(self.facts), 'league': {'league_id': f'source-{year}', 'season': str(year)}}
            self.cache.write(self.cache.normalize('A', year, facts))
        oversized = deepcopy(self.facts)
        oversized['league'] = {'league_id': 'source-2028', 'season': '2028'}
        incoming = self.cache.normalize('A', 2028, oversized)
        async def fetch(*args):
            raise AssertionError('protected seasons must not be fetched for eviction')
        from src.platform.cache_budget import SEASON_LEAGUE_BYTES
        with patch.object(self.cache, 'encoded_size', return_value=SEASON_LEAGUE_BYTES + 1):
            with self.assertRaisesRegex(HistoricalRecoveryUnavailable, 'No verified'):
                asyncio.run(self.reader.publish_with_verified_turnover('A', 2028, incoming, fetch))
        self.assertEqual(self.cache.available_seasons('A'), (2027, 2028))

    def test_reader_order_and_pagination_survive_checkpoint_restart(self):
        facts = deepcopy(self.facts)
        facts['rosters'] = [{**facts['rosters'][0], 'roster_id': roster} for roster in (1, 2, 10)]
        original_trade = facts['transactions']['2'][0]
        facts['transactions']['2'] = [{**original_trade, 'transaction_id': key} for key in ('t9', 't2', 't10')]
        self.cache.write(self.cache.normalize('A', 2021, facts))
        before = {kind: self.reader.records('A', kind, season=2021, limit=None)
                  for kind in ('trade', 'roster_snapshot', 'season_standing')}
        page = self.reader.records('A', 'roster_snapshot', season=2021, limit=1, offset=1)
        self.preserve()
        self.cache.delete('A', 2021)
        restarted = history.CanonicalHistoryStore()
        for kind, expected in before.items():
            self.assertEqual(expected, restarted.records('A', kind, season=2021, limit=None))
        self.assertEqual(page, restarted.records('A', 'roster_snapshot', season=2021, limit=1, offset=1))

    def test_semantic_set_identity_is_order_independent_but_detects_changes(self):
        rows = [self.reader._record('A', 2021, 'trade', key, {'amount': index}, week=2)
                for index, key in enumerate(('t9', 't2', 't10'))]
        digest = HistoricalCheckpoints.semantic_digest(rows)
        self.assertEqual(digest, HistoricalCheckpoints.semantic_digest(list(reversed(rows))))
        self.assertNotEqual(HistoricalCheckpoints.digest(rows), HistoricalCheckpoints.digest(list(reversed(rows))))
        self.assertNotEqual(digest, HistoricalCheckpoints.semantic_digest(rows[:-1]))
        altered = deepcopy(rows)
        altered[0]['payload']['amount'] = 999
        self.assertNotEqual(digest, HistoricalCheckpoints.semantic_digest(altered))
        with self.assertRaisesRegex(HistoricalRecoveryUnavailable, 'Duplicate'):
            HistoricalCheckpoints.semantic_digest([*rows, rows[0]])
        altered = deepcopy(rows)
        altered[0]['season'] = 2022
        self.assertNotEqual(digest, HistoricalCheckpoints.semantic_digest(altered))

    def test_only_explicit_transient_cache_metadata_is_excluded(self):
        rows = self.reader.records('A', 'trade', season=2021)[1]
        digest = HistoricalCheckpoints.semantic_digest(rows)
        changed = deepcopy(rows)
        changed[0]['cache_rebuilt_at'] = '2099-01-01T00:00:00Z'
        self.assertEqual(digest, HistoricalCheckpoints.semantic_digest(changed))
        changed[0]['observed_at'] = '2099-01-01T00:00:00Z'
        self.assertNotEqual(digest, HistoricalCheckpoints.semantic_digest(changed))
