from datetime import datetime, timezone
import unittest

from src.core.data_platform.provider_activation import market_identity_map
from src.core.valuation.normalization import normalize_cached_value
from src.core.data_platform.defaults import build_data_platform
from src.core.market_intelligence.engine import MarketIntelligence
from src.core.market_intelligence.history import MarketSnapshot
from src.core.market_intelligence.trends.engine import calculate_trend
from src.core.valuation.source_time import market_times


class MarketSourceBoundaryTests(unittest.TestCase):
    def test_conflicting_exact_ids_are_not_last_row_wins(self):
        rows = [{'fantasypros_id': 'x', 'sleeper_id': '1'},
                {'fantasypros_id': 'x', 'sleeper_id': '2'},
                {'fantasypros_id': 'y', 'sleeper_id': '3'}]
        self.assertEqual(market_identity_map(rows), {'y': '3'})
        self.assertEqual(market_identity_map(reversed(rows)), {'y': '3'})

    def test_identical_crosswalk_copies_are_safe(self):
        row = {'fantasypros_id': 'x', 'sleeper_id': '1'}
        self.assertEqual(market_identity_map([row, row]), {'x': '1'})

    def test_old_source_new_retrieval_not_fresh_or_backdated(self):
        observed = datetime.now(timezone.utc).isoformat()
        result = normalize_cached_value('DynastyProcess', {'value': 5000,
            'source_updated_at': '2000-01-01'}, updated_at=observed)
        self.assertEqual(result.freshness, 'stale')
        self.assertEqual(result.updated_at, observed)

    def test_retrieval_is_not_source_freshness(self):
        now = datetime.now(timezone.utc).isoformat()
        unknown = normalize_cached_value('FantasyCalc', {'value': 5000,
            'updated_at': now}, updated_at=now, provider_confidence=85)
        fresh = normalize_cached_value('FantasyCalc', {'value': 5000,
            'retrieved_at': now, 'source_updated_at': now}, provider_confidence=85)
        stale = normalize_cached_value('FantasyCalc', {'value': 5000,
            'retrieved_at': now, 'source_updated_at': '2000-01-01'}, provider_confidence=85)
        self.assertEqual(unknown.freshness, 'unknown')
        self.assertEqual(fresh.freshness, 'fresh')
        self.assertEqual(stale.freshness, 'stale')
        self.assertLess(stale.confidence_score, fresh.confidence_score)
        self.assertLess(unknown.confidence_score, fresh.confidence_score)
        self.assertEqual(stale.updated_at, now)

    def test_cached_read_does_not_refresh_evidence(self):
        platform = build_data_platform()
        row = {'value': 5000, 'confidence': 85, 'retrieved_at': '2026-01-02T00:00:00+00:00',
               'source_updated_at': '2000-01-01', 'published_at': '2000-01-02'}
        market = {'providers': {'FantasyCalc': {'1': row}}}
        context = {'market_data': market}
        first = platform.fetch('FantasyCalc', '1', context)
        second = platform.fetch('FantasyCalc', '1', context)
        self.assertEqual(first.timestamp, second.timestamp)
        self.assertEqual(second.freshness, 'stale')
        self.assertEqual(second.normalization['published_at'], '2000-01-02')
        quote = MarketIntelligence._quote(second, market)
        expected = normalize_cached_value('FantasyCalc', row, provider_confidence=85)
        self.assertEqual(quote.confidence, expected.confidence_score)
        self.assertEqual(quote.observed_at, row['retrieved_at'])
        self.assertEqual(market_times(row, '2099-01-01')['retrieved_at'], row['retrieved_at'])

    def test_as_of_trend_does_not_backdate_later_retrieval(self):
        # Source represented an older state, but DTOS did not know it then.
        def snapshot(time, value):
            return MarketSnapshot('1', time, 'FantasyCalc', value, 60,
                'external_provider_raw_price', 'raw', '2qb', 'v1')
        rows = (snapshot('2026-01-01T00:00:00+00:00', 100),
                snapshot('2026-01-10T00:00:00+00:00', 200))
        before = calculate_trend(rows, datetime(2026, 1, 5, tzinfo=timezone.utc))
        after = calculate_trend(tuple(reversed(rows)), datetime(2026, 1, 11, tzinfo=timezone.utc))
        self.assertIsNone(before.momentum)
        self.assertEqual(after.momentum, 100)
        self.assertIn('MARKET_PRICE_CHANGED', after.reason_codes)

    def test_late_older_source_is_not_forward_market_movement(self):
        from dataclasses import replace
        first = MarketSnapshot('1', '2026-01-10T00:00:00+00:00', 'FantasyCalc', 100, 60,
            'external_provider_raw_price', 'raw', '2qb', 'v2', source_updated_at='2026-01-09')
        later = replace(first, timestamp='2026-01-11T00:00:00+00:00', value=200,
                        source_updated_at='2026-01-01')
        result = calculate_trend((first, later), datetime(2026, 1, 12, tzinfo=timezone.utc))
        self.assertIsNone(result.momentum)
        self.assertIn('SOURCE_TIME_ORDER_UNAVAILABLE', result.reason_codes)

    def test_projection_effective_time_does_not_backdate_knowledge(self):
        from src.core.intelligence_memory.pipeline import CheckpointPipeline
        data = {'projection_intelligence': {'players': {'1': {
            'canonical_projection': 10, 'source_timestamp': '2026-01-01',
            'generated_at': '2026-01-10'}}}}
        observation, = CheckpointPipeline._projection_observations(data, 'player:1')
        self.assertEqual(observation.observed_at, '2026-01-10')
        self.assertEqual(observation.metadata['source_updated_at'], '2026-01-01')

    def test_legacy_cache_preserves_source_freshness_and_retrieval(self):
        from src.core.market_intelligence.cache import MarketQuoteCache
        from src.core.market_intelligence.providers.fantasycalc import FantasyCalcProvider
        source = {'providers': {'FantasyCalc': {'1': {'value': 5000, 'confidence': 85,
            'retrieved_at': '2026-01-10', 'source_updated_at': '2000-01-01'}}}}
        quote = FantasyCalcProvider().quote('1', {'id': '1'}, source)
        self.assertEqual(quote.freshness, 'stale')
        cache = MarketQuoteCache()
        first = cache.quote('FantasyCalc', '1', lambda: quote, namespace='test', context_mode='online')
        hit = cache.quote('FantasyCalc', '1', lambda: quote, namespace='test', context_mode='online')
        fallback = cache.quote('FantasyCalc', '1', lambda: quote, namespace='test', context_mode='offline', allow_cached_fallback=True)
        for item in (first, hit, fallback):
            self.assertEqual(item.retrieved_at, '2026-01-10')
            self.assertEqual(item.freshness, 'stale')
