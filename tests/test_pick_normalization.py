import unittest
from copy import deepcopy

from src.core.valuation.normalization import prepare_market_normalization


class PickNormalizationTests(unittest.TestCase):
    def test_shared_provider_units_preserve_identity_and_order(self):
        for provider, fmt in [('FantasyCalc', 'fc:12:2qb:ppr'), ('DynastyProcess', 'dp:2qb')]:
            data = {'providers': {provider: {str(i): {'value': i * 500} for i in range(1, 16)}},
                    'pick_quotes': {provider: [
                        {'value': value, 'market_format': fmt, 'year': year, 'round': round_number,
                         'pick_type': kind, 'range': band, 'exact_slot': slot}
                        for value, year, round_number, kind, band, slot in (
                            (5000, 2027, 1, 'projected_range', 'EARLY', None),
                            (3500, 2027, 1, 'generic_round', None, None),
                            (3000, 2027, 1, 'projected_range', 'MID', None),
                            (2500, 2027, 1, 'projected_range', 'LATE', None),
                            (2000, 2028, 1, 'generic_round', None, None),
                            (1500, 2027, 2, 'generic_round', None, None),
                            (1000, 2027, 3, 'exact_slot', None, '3.03'))]}}
            before = deepcopy(data['pick_quotes'][provider])
            prepare_market_normalization(data)
            values = []
            for original, quote in zip(before, data['pick_quotes'][provider]):
                self.assertEqual(original, {k: v for k, v in quote.items() if k != 'normalization_reference'})
                ref = quote['normalization_reference']
                player = data['providers'][provider][str(original['value'] // 500)]['normalization_reference']
                self.assertEqual(ref, player)
                values.append(ref['normalized_value'])
            self.assertEqual(values, sorted(values, reverse=True))
            replay = deepcopy(data)
            prepare_market_normalization(data)
            self.assertEqual(data, replay)
