"""Active quality aggregation must not manufacture evidence from coverage."""
import unittest

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult, TradeFact


class QualityBoundaryTests(unittest.TestCase):
    def facts(self, **kwargs):
        return FOISFacts('league', 'franchise', 'manager',
                         (SeasonResult(2025, 9, 4, None, league_size=10),), **kwargs)

    def test_results_alone_not_overall(self):
        score = FOISEngine().evaluate(self.facts())
        self.assertIsNone(score.overall_score)
        results = next(c for c in score.category_scores if c.category_key == 'results')
        self.assertIsNotNone(results.normalized_score)
        worst = next(m for m in results.metric_scores if m.metric_key == 'worst_finish')
        self.assertIsNone(worst.normalized_score)

    def test_activity_cannot_complete_overall(self):
        score = FOISEngine().evaluate(self.facts(trades=(TradeFact('tx', 2025, None),)))
        self.assertIsNone(score.overall_score)


if __name__ == '__main__':
    unittest.main()
