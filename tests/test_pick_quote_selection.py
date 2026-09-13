import unittest
from datetime import datetime, timezone

from src.core.data_platform.pick_quotes import select_pick_quote


class SelectionTests(unittest.TestCase):
    now = datetime(2026, 9, 13, tzinfo=timezone.utc)

    def quote(self, kind, **changes):
        return dict(provider='FantasyCalc', market_format='fc:12:2qb:ppr',
                    availability='current', value=100, confidence=85,
                    retrieved_at='2026-09-12T00:00:00+00:00', source_updated_at=None,
                    year=2027, round=1, pick_type=kind, value_scale='fc_native', **changes)

    def select(self, pick, quotes):
        return select_pick_quote({'year': 2027, 'round': 1, **pick}, quotes,
                                 market_format='fc:12:2qb:ppr', now=self.now)

    def test_order_and_exact_slot_requires_established_evidence(self):
        quotes = [self.quote('generic_round'), self.quote('projected_range', range='EARLY'),
                  self.quote('exact_slot', exact_slot='1.03')]
        self.assertEqual(self.select({'exact_slot': '1.03'}, quotes)['quote']['pick_type'], 'generic_round')
        self.assertEqual(self.select({'projected_range': 'EARLY', 'range_supported': True}, quotes)['quote']['pick_type'], 'projected_range')
        self.assertEqual(self.select({'exact_slot': '1.03', 'exact_slot_established': True}, quotes)['quote']['pick_type'], 'exact_slot')
        self.assertEqual(self.select({'projected_range': 'LATE', 'range_supported': True}, quotes)['quote']['pick_type'], 'generic_round')

    def test_generic_cannot_be_relabelled_and_missing_is_not_zero(self):
        result = self.select({'projected_range': 'EARLY', 'range_supported': True}, [self.quote('generic_round')])
        self.assertEqual(result['quote']['pick_type'], 'generic_round')
        self.assertIsNone(self.select({}, [self.quote('exact_slot', exact_slot='1.03')])['quote'])

    def test_stale_source_new_retrieval_and_incompatible_format_are_excluded(self):
        for changes in ({'source_updated_at': '2020-01-01T00:00:00+00:00'},
                        {'market_format': 'different'}, {'availability': 'historical'},
                        {'provider': 'DTOS'}, {'confidence': 0}):
            self.assertIsNone(self.select({}, [{**self.quote('generic_round'), **changes}])['quote'])

    def test_conflicts_and_order_independence(self):
        q = self.quote('generic_round')
        self.assertIsNone(self.select({}, [q, {**q, 'value': 200}])['quote'])
        self.assertEqual(self.select({}, [q, q]), self.select({}, [q]))
