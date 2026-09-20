import unittest
from unittest.mock import patch
from copy import deepcopy
from src.core.trade_intelligence.strategy_dimensions import reconcile_result
from src.core.trade_intelligence.market_balance import market_balance
from src.core.trade_intelligence.models import TradeAsset, TradeProposal


def asset(pid, price, owner):
    return TradeAsset(pid, 'player', pid, 'QB', None, None, price, None, 0, owner, trade_value=price)


def side(roster, delta):
    horizons = {name: {'delta': delta, 'availability': 'complete'} for name in
                ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window')}
    return {'roster_id': str(roster), 'horizons': horizons, 'weekly': {2: {
        'delta': delta,
        'pre': {'reserve_capacity': {'supported_slots': 1}, 'optimal': {'entries': []}},
        'post': {'reserve_capacity': {'supported_slots': 1}, 'optimal': {'entries': []}}}}}


class TradeStrategyTests(unittest.TestCase):
    def test_active_prepared_path_never_executes_legacy_heuristics(self):
        from src.core.trade_intelligence.bilateral import evaluate_bilateral
        from src.core.trade_intelligence.evidence_context import TradeEvidenceContext
        context = TradeEvidenceContext('league', {}, {}, {}, 'generation')
        history = {'evidence_references': ['supported'], 'trend_signals': []}
        for price in (None, 100):
            proposal = TradeProposal(1, 2, (asset('a', price, 1),), (asset('b', 200, 2),), 'Manual')
            with self.subTest(price=price), \
                    patch('src.core.trade_intelligence.bilateral.optimal_legal_lineup', side_effect=AssertionError('legacy optimizer')), \
                    patch('src.core.trade_intelligence.bilateral._package_quality', side_effect=AssertionError('legacy package')), \
                    patch('src.core.trade_intelligence.bilateral._strategic_reasons', side_effect=AssertionError('legacy strategy')), \
                    patch('src.core.trade_intelligence.bilateral.assess_historical_fit', return_value=history) as assess:
                report = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={'league_id': 'league'},
                                            evidence_context=context, horizon_impact={'sides': {'active': side(1, 5), 'partner': side(2, -5)}})
                self.assertIs(assess.call_args.args[0], context)
                self.assertEqual(report['dimensions']['historical_counterparty_evidence'], history)
                self.assertEqual(report['dimensions']['counterparty_plausibility']['historical_context'], history)

    def test_wrong_league_historical_context_is_not_consumed(self):
        from src.core.trade_intelligence.bilateral import evaluate_bilateral
        from src.core.trade_intelligence.evidence_context import TradeEvidenceContext
        context = TradeEvidenceContext('other', {'2': {'private': 'other league'}}, {}, {}, 'generation')
        proposal = TradeProposal(1, 2, (asset('a', 100, 1),), (asset('b', 200, 2),), 'Manual')
        report = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={'league_id': 'league'},
                                    evidence_context=context, horizon_impact={'sides': {}})
        self.assertEqual(report['provenance']['wrong_league_evidence_rejected'], 1)
        self.assertEqual(report['provenance']['wrong_league_evidence_consumed'], 0)
        self.assertEqual(report['dimensions']['historical_counterparty_evidence']['evidence_references'], [])
        self.assertNotIn('other league', str(report))

    def test_acceptance_leagues_reject_each_others_historical_context(self):
        from src.core.trade_intelligence.bilateral import evaluate_bilateral
        from src.core.trade_intelligence.evidence_context import TradeEvidenceContext
        leagues = ('1313066632158924800', '1313063672284721152')
        proposal = TradeProposal(1, 2, (asset('a', 100, 1),), (asset('b', 200, 2),), 'Manual')
        for own, foreign in (leagues, tuple(reversed(leagues))):
            with self.subTest(league=own):
                context = TradeEvidenceContext(foreign, {'2': {'private': 'must not cross'}}, {}, {}, 'G')
                result = evaluate_bilateral(proposal, active_team={}, partner_team={}, league={'league_id': own},
                                            evidence_context=context, horizon_impact={'sides': {}})
                self.assertEqual(result['provenance']['wrong_league_evidence_rejected'], 1)
                self.assertEqual(result['provenance']['wrong_league_evidence_consumed'], 0)
                self.assertNotIn('must not cross', str(result))

    def evaluate(self, prices=(100, 200), deltas=(5, -5), historical=None, windows=None):
        proposal = TradeProposal(1, 2, (asset('a', prices[0], 1),), (asset('b', prices[1], 2),), 'Manual')
        impact = {'team_strength_generation': 'G', 'sides': {'active': side(1, deltas[0]), 'partner': side(2, deltas[1])}}
        result = {'legal': True, 'market_evidence': market_balance(proposal.assets_sent, proposal.assets_received), 'dimensions': {}}
        return reconcile_result(result, proposal, impact, historical, team_windows=windows)

    def test_user_gain_and_counterparty_loss_are_distinct(self):
        result = self.evaluate()
        self.assertEqual(result['recommendation'], 'SMASH ACCEPT')
        self.assertEqual(result['dimensions']['counterparty_plausibility']['assessment'], 'LOW')
        self.assertFalse(result['generated_trade_eligible'])

    def test_overpay_not_automatic_rejection_or_fairness_rewrite(self):
        result = self.evaluate(prices=(200, 100), deltas=(5, 2))
        self.assertEqual(result['recommendation'], 'WORTH PURSUING')
        self.assertEqual(result['market_evidence']['difference'], -100)
        self.assertIn('MARKET_OVERPAY', result['reason_codes'])
        self.assertEqual(result['dimensions']['counterparty_plausibility']['assessment'], 'STRONG')

    def test_unavailable_is_not_negative_quality(self):
        result = self.evaluate(prices=(None, 100))
        self.assertEqual(result['recommendation'], 'WORTH PURSUING')
        self.assertIn('PURSUIT_ONLY_MARKET_TERMS_UNRESOLVED', result['recommendation_trace']['rule_reasons'])
        self.assertIn('CURRENT_LINEUP_UPGRADE', result['reason_codes'])
        self.assertEqual(result['dimensions']['confidence']['assessment'], 'LIMITED')
        coverage = result['dimensions']['confidence']['dimensions']
        self.assertEqual(coverage['market']['availability'], 'partial')
        self.assertTrue(coverage['projection_and_lineup']['active']['current_week']['complete_delta_available'])
        self.assertEqual(coverage['fois']['availability'], 'unavailable')

    def test_fair_requires_positive_evidence_of_parity_not_unknowns(self):
        report = self.evaluate(prices=(100, 100), deltas=(0, 0))
        self.assertEqual(report['recommendation'], 'FAIR / OPTIONAL')
        report = self.evaluate(prices=(None, 100), deltas=(0, 0))
        self.assertIsNone(report['recommendation'])

    def test_mixed_horizons_are_unresolved_not_automatically_fair(self):
        proposal = TradeProposal(1, 2, (asset('a', 100, 1),), (asset('b', 100, 2),), 'Manual')
        impact = {'sides': {'active': side(1, 5), 'partner': side(2, -5)}}
        impact['sides']['active']['horizons']['playoff_window']['delta'] = -5
        report = reconcile_result({'legal': True, 'market_evidence': market_balance(proposal.assets_sent, proposal.assets_received), 'dimensions': {}}, proposal, impact)
        self.assertIsNone(report['recommendation'])
        self.assertIn('MATERIAL_TRADEOFF_UNRESOLVED', report['reason_codes'])

    def test_equal_market_can_be_not_worth_it_for_lineup_cost(self):
        report = self.evaluate(prices=(100, 100), deltas=(-5, 5))
        self.assertEqual(report['recommendation'], 'NOT WORTH IT')
        self.assertEqual(report['market_evidence']['difference'], 0)

    def test_reserve_improvement_is_not_automatically_stuffing(self):
        from src.core.trade_intelligence.package_quality import package_profile
        incoming = tuple(asset(pid, 100, 2) for pid in ('b', 'c', 'd'))
        impact = side(1, -5)
        impact['weekly'][2]['post']['reserve_capacity']['supported_slots'] = 2
        profile = package_profile(incoming, (asset('a', 300, 1),), impact)
        self.assertEqual(profile['assessment'], 'MIXED')
        self.assertNotIn('PACKAGE_STUFFING', profile['reason_codes'])
        self.assertIn('RESERVE_COVERAGE_GAIN_WITH_STARTER_LOSS', profile['reason_codes'])
        self.assertIsNone(profile['centerpiece_evidence']['elite_tier'])

    def test_opposite_weekly_effects_are_labeled_mixed_not_contradictory(self):
        from src.core.trade_intelligence.package_quality import package_profile
        from src.core.trade_intelligence.strategy_dimensions import strategic_profile
        impact = side(1, 5)
        impact['weekly'][2]['post']['reserve_capacity']['supported_slots'] = 2
        impact['weekly'][3] = deepcopy(impact['weekly'][2])
        impact['weekly'][3]['delta'] = -5
        impact['weekly'][3]['post']['reserve_capacity']['supported_slots'] = 0
        incoming, outgoing = (asset('b', 100, 2),), (asset('a', 100, 1),)
        package = package_profile(incoming, outgoing, impact)
        strategy = strategic_profile(incoming, outgoing, impact, package)
        self.assertIn('MIXED_WEEKLY_LINEUP_EFFECTS', package['reason_codes'])
        self.assertNotIn('SUPPORTED_LINEUP_GAIN', package['reason_codes'])
        self.assertIn('MIXED_WEEKLY_DEPTH_EFFECTS', strategy['reason_codes'])
        self.assertNotIn('DEPTH_LOSS', strategy['reason_codes'])

    def test_historical_tendency_never_dictates_behavior(self):
        prior = {'assessment': 'LOW', 'reasons': ['Different historical preference'], 'evidence_references': ['ref']}
        original = deepcopy(prior)
        result = self.evaluate(prices=(100, 100), deltas=(5, 2), historical=prior)
        self.assertEqual(result['dimensions']['counterparty_plausibility']['assessment'], 'STRONG')
        self.assertIsNone(result['dimensions']['counterparty_plausibility']['acceptance_probability'])
        self.assertEqual(prior, original)

    def test_best_for_requires_matching_canonical_window_generation(self):
        windows = {'1': {'classification': 'Contender', 'generation': 'old', 'confidence': 80}}
        self.assertEqual(self.evaluate(windows=windows)['dimensions']['best_for']['active'], 'NO CLEAR FIT')
        windows['1']['generation'] = 'G'
        self.assertEqual(self.evaluate(windows=windows)['dimensions']['best_for']['active'], 'CONTENDING')

    def test_pick_receipt_does_not_invent_compensating_long_term_utility(self):
        pick = TradeAsset('2028-R1-2', 'pick', '2028 first', None, None, None, 300, None, 0, 2,
                          trade_value=300, season=2028, round=1, original_roster_id=2, current_owner_id=2)
        proposal = TradeProposal(1, 2, (asset('player', 900, 1),), (pick,), 'Manual')
        result = {'legal': True, 'market_evidence': market_balance(proposal.assets_sent, proposal.assets_received), 'dimensions': {}}
        impact = {'sides': {'active': side(1, -10), 'partner': side(2, 10)}}
        report = reconcile_result(result, proposal, impact)
        self.assertIsNone(report['recommendation'])
        self.assertIn('LONG_TERM_COMPENSATION_UNESTABLISHED', report['reason_codes'])
        self.assertEqual(report['dimensions']['strategic_fit']['active']['future_capital']['received'][0]['canonical_owner'], 2)
