from dataclasses import replace
import unittest

from src.core.valuation.consensus import build_canonical_consensus
from src.core.valuation.normalization import normalize_value


class MarketConsensusIndependenceTests(unittest.TestCase):
    def test_market_api_preserves_separate_quotes_and_explicit_state(self):
        from dataclasses import asdict
        from src.core.market_intelligence.aggregation.consensus import build_consensus
        from src.core.market_intelligence.models import ProviderQuote
        a = ProviderQuote('FantasyCalc', 'p1', 6000, 80, None, 'external', True, '',
                          normalized_value=500, raw_scale=(0, 12000))
        b = replace(a, provider='DynastyProcess', value=5000, raw_scale=(0, 10000))
        single = asdict(build_consensus('p1', (a,), ('FantasyCalc', 'DynastyProcess')))
        self.assertEqual(single['evidence_state'], 'SINGLE-PROVIDER MARKET')
        self.assertEqual(single['confidence'], 80)
        combined = asdict(build_consensus('p1', (a, b), ('FantasyCalc', 'DynastyProcess')))
        self.assertIsNone(combined['value'])
        self.assertEqual(combined['evidence_state'], 'MARKET UNAVAILABLE')
        self.assertEqual(len(combined['quotes']), 2)

    def test_market_history_requires_comparable_ordered_boundaries(self):
        from datetime import datetime, timezone
        from src.core.market_intelligence.history import MarketSnapshot
        from src.core.market_intelligence.trends import calculate_trend
        a = MarketSnapshot('p1', '2026-09-01T00:00:00+00:00', 'A', 100, 80, 'price', '0-1000', '2qb', 'v1')
        b = replace(a, timestamp='2026-09-02T00:00:00+00:00', value=110)
        now = datetime(2026, 9, 3, tzinfo=timezone.utc)
        self.assertEqual(calculate_trend((b, a), now).momentum, 10)
        for bad in (replace(b, provider='B'), replace(b, value_scale='0-10000'),
                    replace(b, format_key='1qb'), replace(b, methodology='v2'),
                    replace(b, value_concept=None), replace(b, timestamp=a.timestamp),
                    replace(b, timestamp='2026-09-04T00:00:00+00:00')):
            self.assertIsNone(calculate_trend((a, bad), now).momentum)

    def test_mirrored_source_is_one_vote_and_conflicting_mirror_is_excluded(self):
        row = normalize_value('DynastyProcess', 5000)
        mirror = replace(row, provider='FantasyPros')
        single = build_canonical_consensus((row,))
        repeated = build_canonical_consensus((row, mirror))
        self.assertEqual(single.market_consensus, repeated.market_consensus)
        self.assertEqual(single.confidence_score, repeated.confidence_score)
        self.assertEqual(len(repeated.providers_used), 1)
        self.assertIsNone(build_canonical_consensus((row, replace(mirror, normalized_value=5))).market_consensus)

    def test_raw_provider_switch_is_not_market_movement(self):
        from src.core.data_platform.aggregation import trend
        from tests.test_data_platform import FixtureProvider
        rows = tuple(FixtureProvider(name, value).fetch('p1', {})
                     for name, value in (('FantasyCalc', 12000), ('DynastyProcess', 5000)))
        result = trend('p1', rows)
        self.assertIsNone(result.absolute_change)
        self.assertIsNone(result.momentum)
        self.assertEqual(result.direction, 'Unavailable')

    def test_duplicate_observation_cannot_inflate_confidence_or_weight(self):
        row = normalize_value('FantasyCalc', 6000)
        self.assertEqual(build_canonical_consensus((row,)), build_canonical_consensus((row,) * 10))

    def test_conflicting_provider_quotes_excluded_independent_of_order(self):
        row = normalize_value('FantasyCalc', 6000)
        conflict = replace(row, normalized_value=10)
        other = normalize_value('DynastyProcess', 5000)
        for values in ((row, conflict, other), (other, conflict, row)):
            self.assertEqual(build_canonical_consensus(values), build_canonical_consensus((other,)))

    def test_internal_value_cannot_masquerade_as_external_market(self):
        for provider in ('DTOS', 'DTOS Pick'):
            self.assertIsNone(build_canonical_consensus((normalize_value(provider, 80),)).market_consensus)

    def test_invalid_and_zero_confidence_quotes_not_corroboration(self):
        row = normalize_value('FantasyCalc', 6000)
        for bad in (replace(row, confidence_score=0), replace(row, normalized_value=1001),
                    replace(row, raw_value=float('nan'))):
            self.assertIsNone(build_canonical_consensus((bad,)).market_consensus)

    def test_rounding_display_weights_does_not_change_calculation(self):
        rows = tuple(replace(normalize_value('FantasyCalc', 12000), provider=str(i), confidence_score=1,
                             compatibility_key='explicit-test-format')
                     for i in range(7))
        self.assertEqual(build_canonical_consensus(rows).market_consensus, 1000)

    def test_unknown_provider_format_cannot_create_consensus(self):
        a = normalize_value('FantasyCalc', 6000)
        b = normalize_value('DynastyProcess', 5000)
        result = build_canonical_consensus((a, b))
        self.assertIsNone(result.market_consensus)
        self.assertIn('compatibility', result.warning)
        self.assertEqual(result.evidence_state, 'MARKET UNAVAILABLE')
        self.assertEqual(build_canonical_consensus((a,)).confidence_score, a.confidence_score)
        self.assertEqual(build_canonical_consensus((a,)).evidence_state, 'SINGLE-PROVIDER MARKET')

    def test_explicit_compatible_contract_and_mismatch(self):
        a = replace(normalize_value('FantasyCalc', 6000), compatibility_key='verified-test-format')
        b = replace(normalize_value('DynastyProcess', 5000), compatibility_key=a.compatibility_key)
        self.assertEqual(build_canonical_consensus((a, b)).evidence_state, 'MULTI-PROVIDER CONSENSUS')
        self.assertIsNone(build_canonical_consensus((a, replace(b, compatibility_key='other'))).market_consensus)
