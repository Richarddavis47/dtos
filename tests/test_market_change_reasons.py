from dataclasses import replace
from datetime import datetime, timezone
import unittest

from src.core.market_intelligence.history import MarketSnapshot
from src.core.market_intelligence.trends import calculate_trend


class MarketChangeReasonTests(unittest.TestCase):
    def test_price_rank_confidence_and_method_are_distinct(self):
        first = MarketSnapshot('p1', '2026-09-01T00:00:00Z', 'A', 100, 80,
            'external_provider_raw_price', 'A:raw_price_units', 'format-a', 'v1', 4, 2)
        later = replace(first, timestamp='2026-09-02T00:00:00Z')
        now = datetime(2026, 9, 3, tzinfo=timezone.utc)
        self.assertEqual(calculate_trend((first, later), now).reason_codes, ('UNCHANGED_EVIDENCE',))
        ranks = calculate_trend((first, replace(later, source_rank=5)), now)
        self.assertEqual(ranks.reason_codes, ('RANK_CHANGED_WITHOUT_PRICE_CHANGE',))
        self.assertEqual(ranks.momentum, 0)
        movement = calculate_trend((first, replace(later, value=110, confidence=70, source_tier=3)), now)
        self.assertEqual(set(movement.reason_codes), {'MARKET_PRICE_CHANGED', 'EVIDENCE_CONFIDENCE_CHANGED', 'SOURCE_TIER_CHANGED'})
        boundary = calculate_trend((first, replace(later, methodology='v2', value=500)), now)
        self.assertIsNone(boundary.momentum)
        self.assertEqual(boundary.reason_codes, ('METHODOLOGY_BOUNDARY',))
