"""Preserve every top-k package and diagnostic while eliminating repeated work."""
import random
import unittest
from unittest.mock import patch

from src.core.trade_intelligence.engine import trade_generator as generator
from tests import trade_construction_reference as reference
from tests.test_trade_intelligence import asset


class ConstructionPerformanceTests(unittest.TestCase):
    def test_all_phases_preferences_and_price_ties_match_prior_release(self):
        rng = random.Random(2112)
        for case in range(6):
            outgoing = tuple(asset(f'out-{i}', 'pick' if i % 3 == 0 else 'player', rng.choice([25, 100, 100, 250])) for i in range(12))
            incoming = tuple(asset(f'in-{i}', 'pick' if i % 3 == 0 else 'player', rng.choice([25, 100, 100, 250]), 2) for i in range(12))
            for phase in range(3):
                for preference in (None, {'name': 'draft_capital'}, {'name': 'position_need', 'position': 'WR'}):
                    before, after = {}, {}
                    args = (1, 2, outgoing, incoming, incoming[case % 2].asset_id)
                    with self.subTest(case=case, phase=phase, preference=preference):
                        expected = reference._canonical_candidates(*args, before, preference, phase)
                        actual = generator._canonical_candidates(*args, after, preference, phase)
                        self.assertEqual(actual, expected)
                        self.assertEqual(after, before)

    def test_expanded_search_reuses_matching_and_keeps_full_pair_count(self):
        outgoing = tuple(asset(f'out-{i}', 'player', 100 + i) for i in range(24))
        incoming = tuple(asset(f'in-{i}', 'player', 100 + i, 2) for i in range(24))
        diagnostics = {}
        with patch.object(generator, '_matches', wraps=generator._matches) as matches:
            actual = generator._canonical_candidates(1, 2, outgoing, incoming, 'in-0', diagnostics, search_phase=2)
        reference_diagnostics = {}
        expected = reference._canonical_candidates(1, 2, outgoing, incoming, 'in-0', reference_diagnostics, search_phase=2)
        self.assertEqual(actual, expected)
        self.assertEqual(diagnostics, reference_diagnostics)
        self.assertGreater(diagnostics['cheap_package_pairs_inspected'], 50_000)
        self.assertLess(matches.call_count, 10_000)
