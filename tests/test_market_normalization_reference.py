"""Provider normalization survives league relevance without copying populations."""
from copy import deepcopy
import unittest

from src.core.valuation.calibration import cached_market_consensus
from src.core.valuation.normalization import normalize_cached_value, prepare_market_normalization


class MarketNormalizationReferenceTests(unittest.TestCase):
    def fixture(self):
        return {"providers": {"FantasyCalc": {str(i): {"value": i * 100, "confidence": 90}
            for i in range(1, 101)}}}

    def test_two_league_subsets_use_same_full_population(self):
        market = self.fixture()
        prepare_market_normalization(market)
        expected = cached_market_consensus(market, ["50"])["50"]
        for members in (("50",), tuple(str(i) for i in range(30, 70))):
            subset = deepcopy(market)
            subset["providers"]["FantasyCalc"] = {key: row for key, row in subset["providers"]["FantasyCalc"].items() if key in members}
            self.assertEqual(cached_market_consensus(subset, ["50"])["50"], expected)

    def test_unchanged_preparation_is_idempotent(self):
        market = self.fixture()
        prepare_market_normalization(market)
        before = deepcopy(market)
        prepare_market_normalization(market)
        self.assertEqual(market, before)
        reference = market["providers"]["FantasyCalc"]["50"]["normalization_reference"]
        self.assertEqual(reference["population_size"], 100)
        self.assertFalse(any(isinstance(value, (list, dict)) for value in reference.values()))

    def test_material_population_change_invalidates_reference(self):
        market = self.fixture()
        prepare_market_normalization(market)
        before = deepcopy(market["providers"]["FantasyCalc"]["50"]["normalization_reference"])
        market["providers"]["FantasyCalc"]["1"]["value"] = 11000
        prepare_market_normalization(market)
        self.assertNotEqual(before["generation"], market["providers"]["FantasyCalc"]["50"]["normalization_reference"]["generation"])

    def test_stale_raw_value_cannot_reuse_old_normalized_value(self):
        market = self.fixture()
        prepare_market_normalization(market)
        row = market["providers"]["FantasyCalc"]["50"]
        row["value"] = 0
        self.assertEqual(normalize_cached_value("FantasyCalc", row).normalized_value, 0)

    def test_source_version_change_cannot_reuse_reference(self):
        market = self.fixture()
        prepare_market_normalization(market)
        row = market["providers"]["FantasyCalc"]["50"]
        row["normalization_reference"]["version"] = "obsolete"
        self.assertEqual(normalize_cached_value("FantasyCalc", row).method, "provider_range_linear")

    def test_zero_confidence_is_not_replaced_by_default_confidence(self):
        market = self.fixture()
        market["providers"]["FantasyCalc"]["50"]["confidence"] = 0
        prepare_market_normalization(market)
        self.assertEqual(cached_market_consensus(market, ["50"])["50"][1], 0)

    def test_cached_repreparation_preserves_full_population_after_filter(self):
        for provider, fmt in (('FantasyCalc', 'fc:12:2qb:ppr'), ('DynastyProcess', 'dp:2qb')):
            market = {'providers': {provider: self.fixture()['providers']['FantasyCalc']},
                      'pick_quotes': {provider: [{'value': 5000, 'market_format': fmt,
                          'year': 2028, 'round': 1, 'original_roster_id': 7}]}}
            prepare_market_normalization(market)
            expected = deepcopy(market['providers'][provider]['50'])
            pick = deepcopy(market['pick_quotes'][provider][0])
            market['providers'][provider] = {'50': market['providers'][provider]['50']}
            before = deepcopy(market)
            for _ in range(3):
                prepare_market_normalization(market)
                self.assertEqual(market, before)
                self.assertEqual(market['providers'][provider]['50'], expected)
                self.assertEqual(market['pick_quotes'][provider][0], pick)

    def test_changed_or_mixed_partial_references_fail_atomically(self):
        from unittest.mock import patch
        for change in ('raw', 'version', 'generation', 'missing', 'pick'):
            market = self.fixture()
            market['pick_quotes'] = {'FantasyCalc': [{'value': 5000, 'market_format': 'fc:12:2qb:ppr'}]}
            prepare_market_normalization(market)
            market['providers']['FantasyCalc'] = {k: v for k, v in market['providers']['FantasyCalc'].items() if k in {'49', '50'}}
            row = market['providers']['FantasyCalc']['50']
            if change == 'raw':
                row['value'] += 1
            elif change == 'version':
                row['normalization_reference']['version'] = 'obsolete'
            elif change == 'generation':
                row['normalization_reference']['generation'] = '0' * 64
            elif change == 'missing':
                row.pop('normalization_reference')
            else:
                market['pick_quotes']['FantasyCalc'][0]['value'] += 1
            before = deepcopy(market)
            with self.assertRaisesRegex(ValueError, 'Complete Market population'), patch('socket.create_connection', side_effect=AssertionError('no source work')):
                prepare_market_normalization(market)
            self.assertEqual(market, before)

    def test_fresh_complete_source_replaces_old_curve_and_preserves_zero(self):
        market = self.fixture()
        market['providers']['FantasyCalc']['0'] = {'value': 0, 'confidence': 90}
        prepare_market_normalization(market)
        before = market['providers']['FantasyCalc']['50']['normalization_reference']['generation']
        # A fresh provider adapter emits a new full payload without references.
        fresh = {'providers': {'FantasyCalc': {str(i): {'value': i * 110, 'confidence': 90} for i in range(101)}}}
        prepare_market_normalization(fresh)
        self.assertNotEqual(fresh['providers']['FantasyCalc']['50']['normalization_reference']['generation'], before)
        zero = fresh['providers']['FantasyCalc']['0']
        expected = normalize_cached_value('FantasyCalc', zero).normalized_value
        fresh['providers']['FantasyCalc'] = {'0': zero, '50': fresh['providers']['FantasyCalc']['50']}
        prepare_market_normalization(fresh)
        self.assertEqual(normalize_cached_value('FantasyCalc', zero).normalized_value, expected)
        self.assertEqual(zero['value'], 0)
        small = {'providers': {'FantasyCalc': {'0': {'value': 0}, '1': {'value': 100}}}}
        prepare_market_normalization(small)
        small['providers']['FantasyCalc'].pop('1')
        prepare_market_normalization(small)
        self.assertEqual(normalize_cached_value('FantasyCalc', small['providers']['FantasyCalc']['0']).normalized_value, 0)

    def test_pick_only_retention_and_unsupported_format(self):
        market = self.fixture()
        market['pick_quotes'] = {'FantasyCalc': [{'value': 5000, 'market_format': 'fc:12:2qb:ppr'}]}
        prepare_market_normalization(market)
        expected = deepcopy(market['pick_quotes']['FantasyCalc'][0])
        market['providers']['FantasyCalc'] = {}
        market['pick_quotes']['FantasyCalc'].append({'value': 5000, 'market_format': 'unproven', 'normalization_reference': expected['normalization_reference']})
        prepare_market_normalization(market)
        self.assertEqual(market['pick_quotes']['FantasyCalc'][0], expected)
        self.assertNotIn('normalization_reference', market['pick_quotes']['FantasyCalc'][1])

    def test_known_source_count_prevents_missing_references_from_looking_complete(self):
        market = self.fixture()
        market['provider_status'] = {'FantasyCalc': {'records_retrieved': 100}}
        prepare_market_normalization(market)
        market['providers']['FantasyCalc'] = {'50': market['providers']['FantasyCalc']['50']}
        row = market['providers']['FantasyCalc']['50']
        row.pop('normalization_reference')
        before = deepcopy(market)
        with self.assertRaisesRegex(ValueError, 'Complete Market population'):
            prepare_market_normalization(market)
        self.assertEqual(market, before)
        # A legacy subset-recomputed reference is not proof of a full curve.
        subset = deepcopy(market)
        subset.pop('provider_status')
        prepare_market_normalization(subset)
        market['providers'] = subset['providers']
        before = deepcopy(market)
        with self.assertRaisesRegex(ValueError, 'Complete Market population'):
            prepare_market_normalization(market)
        self.assertEqual(market, before)

    def test_empty_partial_family_does_not_block_other_supported_provider(self):
        market = {'providers': {'FantasyCalc': {}, 'DynastyProcess': {'50': {'value': 5000}}},
                  'provider_status': {'FantasyCalc': {'records_retrieved': 100}}}
        prepare_market_normalization(market)
        self.assertEqual(market['providers']['FantasyCalc'], {})
        self.assertIsNotNone(market['providers']['DynastyProcess']['50']['normalization_reference']['normalized_value'])
