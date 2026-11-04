import unittest

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, TradeFact


class TradeEvidenceTests(unittest.TestCase):
    def test_explicit_zero_coverage_does_not_become_full_coverage(self):
        facts = FOISFacts('A', 'A:franchise:1', 'gm', (),
                          trades=(TradeFact('t', 2025, None, process_score=80),),
                          front_office_evidence={'evidence_completeness': 0})
        result = FOISEngine().evaluate(facts)
        category = next(c for c in result.category_scores if c.category_key == 'trading_asset_management')
        metric = next(m for m in category.metric_scores if m.metric_key == 'value_captured_at_transaction_time')
        self.assertEqual(metric.completeness, 0)

    def category(self, trades):
        facts = FOISFacts('A', 'A:franchise:1', 'gm', (), trades=tuple(trades))
        score = FOISEngine().evaluate(facts, generated_at='2026-01-01T00:00:00+00:00')
        return next(c for c in score.category_scores if c.category_key == 'trading_asset_management')

    def test_activity_without_quality_does_not_generate_grade(self):
        category = self.category([TradeFact(str(i), 2025, None) for i in range(20)])
        self.assertIsNone(category.normalized_score)

    def test_missing_assessments_change_coverage_not_quality(self):
        # A productivity flag is context, not a process-quality magnitude.
        trades = [TradeFact(str(i), 2025, True, process_score=80) for i in range(3)]
        supported = self.category(trades)
        partial = self.category(trades + [TradeFact('unknown', 2025, None)])
        self.assertEqual(supported.normalized_score, partial.normalized_score)
        self.assertLess(partial.completeness, supported.completeness)

    def test_supported_negative_is_not_missing(self):
        category = self.category([TradeFact('bad', 2025, False)])
        metric = next(m for m in category.metric_scores if m.metric_key == 'productive_trade_activity')
        self.assertEqual(metric.normalized_score, 0)
