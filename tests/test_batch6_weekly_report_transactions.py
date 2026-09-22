from copy import deepcopy
from types import SimpleNamespace
import unittest

from services.weekly_report_transactions import transaction_facts


class ReportTransactionTests(unittest.TestCase):
    def fixture(self):
        rows = [{'transaction_id': str(i), 'type': 'waiver', 'status': 'complete',
                 'leg': 3, 'roster_ids': [1], 'adds': {str(i): 1},
                 'settings': {} if bid is None else {'waiver_bid': bid}}
                for i, bid in enumerate((None, 0, 12), 1)]
        return SimpleNamespace(season=2025, checksum='verified', facts={
            'league': {'league_id': 'A', 'season': '2025'}, 'transactions': {'3': rows}})

    def read(self, cache):
        return transaction_facts(cache, league_id='A', season=2025, week=3)

    def test_missing_and_genuine_zero_bid(self):
        result = self.read(self.fixture())
        self.assertEqual([r['faab'] for r in result['facts']], [None, 0, 12])

    def test_failed_commissioner_wrong_week_excluded(self):
        cache = self.fixture()
        rows = cache.facts['transactions']['3']
        rows[0]['status'] = 'failed'
        rows[1]['type'] = 'commissioner'
        rows[2]['leg'] = 4
        self.assertEqual(self.read(cache)['facts'], [])

    def test_foreign_league_season_and_missing_week_unavailable(self):
        for field, value in (('league_id', 'B'), ('season', '2024')):
            cache = self.fixture()
            cache.facts['league'][field] = value
            self.assertEqual(self.read(cache)['availability'], 'unavailable')
        cache = self.fixture()
        cache.facts['transactions'] = {}
        self.assertEqual(self.read(cache)['availability'], 'unavailable')

    def test_duplicate_and_conflicting_identity(self):
        cache = self.fixture()
        rows = cache.facts['transactions']['3']
        rows.append(deepcopy(rows[0]))
        self.assertEqual(len(self.read(cache)['facts']), 3)
        rows[-1]['settings'] = {'waiver_bid': 90}
        result = self.read(cache)
        self.assertEqual(result['availability'], 'partial')
        self.assertEqual(len(result['facts']), 2)

    def test_replay_does_not_mutate_retained_source(self):
        cache = self.fixture()
        before = deepcopy(cache.facts)
        first = self.read(cache)
        for _ in range(100):
            self.assertEqual(self.read(cache), first)
        self.assertEqual(cache.facts, before)
