from dataclasses import replace
import unittest

from src.core.fois.engine import FOISEngine
from src.core.fois.facts import FOISFacts, SeasonResult, TradeFact, WaiverFact


def facts(values=(65, 65, 65), outcome=None):
    return FOISFacts('league', 'franchise', 'owner',
        (SeasonResult(2024, 9, 5, 3, league_size=10),),
        trades=tuple(TradeFact(str(i), 2024, None, process_score=v,
                               outcome_score=outcome, process_confidence='medium')
                     for i, v in enumerate(values)))


def trading(score):
    return next(c for c in score.category_scores if c.category_key == 'trading_asset_management')


class ActiveQualityTests(unittest.TestCase):
    def test_mean_preserves_difference_hidden_by_median(self):
        engine = FOISEngine()
        base = trading(engine.evaluate(facts()))
        stronger = trading(engine.evaluate(facts((65, 65, 90))))
        weaker = trading(engine.evaluate(facts((65, 65, 20))))
        self.assertGreater(stronger.normalized_score, base.normalized_score)
        self.assertLess(weaker.normalized_score, base.normalized_score)
        self.assertEqual(base.details['process']['mean_magnitude'], 65)

    def test_outcome_does_not_change_process_category(self):
        engine = FOISEngine()
        base = trading(engine.evaluate(facts()))
        later = trading(engine.evaluate(facts(outcome=100)))
        self.assertEqual(base.normalized_score, later.normalized_score)
        self.assertEqual(later.details['outcome']['mean_magnitude'], 100)

    def test_volume_missing_and_impact_do_not_manufacture_quality(self):
        engine = FOISEngine()
        base = facts()
        extended = replace(base, trades=base.trades + tuple(
            TradeFact('missing'+str(i), 2024, None, impact_weight=1000) for i in range(50)))
        self.assertEqual(trading(engine.evaluate(base)).normalized_score,
                         trading(engine.evaluate(extended)).normalized_score)
        weighted = replace(base, trades=tuple(replace(t, impact_weight=1000) for t in base.trades))
        self.assertEqual(trading(engine.evaluate(base)).normalized_score,
                         trading(engine.evaluate(weighted)).normalized_score)

    def test_minimum_sample_results_only_not_overall(self):
        score = FOISEngine().evaluate(facts((90, 90)))
        self.assertIsNone(trading(score).normalized_score)
        self.assertIsNone(score.overall_score)
        self.assertEqual(trading(score).details['process']['supported_magnitudes'], 2)

    def test_scoped_waiver_direction_remains_ungraded_in_active_path(self):
        row = WaiverFact('w', 2024, None, faab_bid=0, decision_evaluation={
            'process': {'evaluability': 'partially_evaluable', 'quality': None, 'confidence': 'limited_scope', 'assessment': [
                {'dimension': 'contemporaneous_asset_exchange', 'assessment': 'higher_observed_market'}]},
            'outcome': {'evaluability': 'insufficient', 'quality': None, 'confidence': 'unavailable'}})
        score = FOISEngine().evaluate(replace(facts(), waivers=(row,)))
        category = next(c for c in score.category_scores if c.category_key == 'waivers_transactions')
        self.assertIsNone(category.normalized_score)
        self.assertEqual(category.details['process']['dimensions'],
                         {'contemporaneous_asset_exchange': {'higher_observed_market': 1}})

    def test_league_identity_and_unchanged_stability(self):
        engine = FOISEngine()
        a = engine.evaluate(facts(), generated_at='fixed')
        self.assertEqual(a, engine.evaluate(facts(), generated_at='fixed'))
        b = engine.evaluate(replace(facts(), league_id='other'), generated_at='fixed')
        self.assertNotEqual(a.score_key, b.score_key)
        self.assertEqual(a.category_scores, b.category_scores)
