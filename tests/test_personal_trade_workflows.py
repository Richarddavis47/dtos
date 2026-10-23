"""Actual Custom Trade workflow controls over canonical prepared league evidence."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from services.trade_calculator import balance_trade_market, calculate_trade_market
from tests import test_capital_strategy_reconciliation as capital


class PersonalTradeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = capital.CapitalStrategyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.data = self.fixture.data
        workspace = trade.build_trade_workspace(self.data, 1)
        values = {a.asset_id: a.trade_value for pool in workspace['pools'].values() for a in pool}
        self.context = {'mode': 'custom', 'revision': 1, 'baseline_generation': 'fixture-seed',
                        'market_generation': 'fixture-current', 'method': 'market-rank-slot-curve-v1',
                        'scope': ['fixture-account', 'league-1', 1], 'values': dict(values),
                        'neutral_values': dict(values), 'preferences': {}}
        self.reader_patch = patch('services.trade_intelligence._trade_projection_service', return_value=self.fixture.reader)
        self.reader_patch.start()
        self.addCleanup(self.reader_patch.stop)

    def payload(self, **updates):
        return {'active_roster_id': 1, 'partner_roster_id': 2,
                'assets_sent': ['a'], 'assets_received': ['2028-R1-4'], 'strategy': 'REBUILD',
                'workflow': 'create', '_personal_context': self.context, **updates}

    def assert_neutral_dimensions(self, row, intent):
        neutral = trade.evaluate_trade_request(self.data, {**row['proposal'], 'strategy': intent},
                                              projection_reader=self.fixture.reader)['evaluation']
        custom = row['evaluation']
        self.assertEqual(custom['market_evidence'], neutral['market_evidence'])
        self.assertEqual(custom['lineup_impact'], neutral['lineup_impact'])
        self.assertEqual(custom['multi_horizon_impact'], neutral['multi_horizon_impact'])
        self.assertEqual(custom['dimensions']['counterparty_plausibility'], neutral['dimensions']['counterparty_plausibility'])
        self.assertEqual(custom['dimensions']['strategic_fit']['partner'], neutral['dimensions']['strategic_fit']['partner'])
        self.assertEqual(custom['dimensions']['package_quality']['partner'], neutral['dimensions']['package_quality']['partner'])
        self.assertEqual(custom['dimensions']['confidence'], neutral['dimensions']['confidence'])
        self.assertEqual(custom['personalization']['mode'], 'custom')
        return custom, neutral

    def test_seeded_custom_actual_shop_trade_for_and_recommended_preserve_canonical_evidence(self):
        before = deepcopy(self.data)
        for workflow, active, target, intent in (
            ('shop', 1, 'a', 'REBUILD'), ('shop', 2, '2028-R1-4', 'WIN NOW'),
            ('trade_for', 2, 'a', 'WIN NOW'), ('recommended', 1, None, 'REBUILD'),
            ('recommended', 2, None, 'WIN NOW')):
            with self.subTest(workflow=workflow, active=active):
                result = trade.generate_trade_workflow(self.data, self.payload(workflow=workflow,
                    active_roster_id=active, partner_roster_id=0, asset_id=target, strategy=intent,
                    **({'shop_preference': 'draft_capital'} if workflow == 'shop' and active == 1 else {})))
                self.assertGreater(result['count'], 0)
                self.assertTrue(any(row['evaluation']['generated_trade_eligible'] for row in result['results']))
                for row in result['results']:
                    custom, neutral = self.assert_neutral_dimensions(row, intent)
                    self.assertEqual(custom['recommendation'], neutral['recommendation'])
                    self.assertEqual(custom['generated_trade_eligible'], neutral['generated_trade_eligible'])
                    if not custom['generated_trade_eligible']:
                        self.assertEqual(custom['recommendation'], 'FAIR / OPTIONAL')
        self.assertEqual(self.data, before)

    def test_actual_adjust_and_alternatives_preserve_targets_and_neutral_counterparty(self):
        payload = self.payload(active_roster_id=2, partner_roster_id=1,
            assets_sent=['2028-R4-4'], assets_received=['a'], strategy='WIN NOW',
            instruction='make this trade work')
        for operation in (trade.assist_trade_request, trade.create_trade_alternatives):
            with self.subTest(operation=operation.__name__):
                result = operation(self.data, payload)
                self.assertGreater(result['count'], 0)
                for row in result['results']:
                    self.assertIn('a', row['proposal']['assets_received'])
                    custom, _ = self.assert_neutral_dimensions(row, 'WIN NOW')
                    self.assertTrue(trade._trade_for_eligible(custom))

    def test_custom_calculator_and_balance_change_personal_cost_without_market_or_lineup_changes(self):
        self.fixture.prices(a=350, b=100, c=250, d=100, e=200, f=20)
        workspace = trade.build_trade_workspace(self.data, 1)
        values = {a.asset_id: a.trade_value for pool in workspace['pools'].values() for a in pool}
        self.context['neutral_values'] = dict(values)
        self.context['values'] = dict(values, a=250, c=350)
        payload = self.payload(assets_sent=['a'], assets_received=['c'], strategy='RETOOL')
        result = calculate_trade_market(self.data, payload)
        self.assertEqual(result['market']['sent']['total'], 350)
        self.assertEqual(result['market']['received']['total'], 250)
        self.assertEqual(result['personal']['sent']['total'], 250)
        self.assertEqual(result['personal']['received']['total'], 350)
        self.assertNotEqual(result['market']['verdict'], result['personal']['verdict'])
        balance = balance_trade_market(self.data, payload)
        self.assertGreater(balance['search_evidence']['evaluated'], 0)
        self.assertEqual(balance['valuation_context'], 'Custom DTOS personal valuation')
        self.assertEqual(balance['neutral_original_market'], result['market'])
        for row in balance['results']:
            custom, _ = self.assert_neutral_dimensions(row, 'RETOOL')
            self.assertLess(row['balance_adjustment']['suggested']['absolute_gap'], 100)
            self.assertEqual(custom['personalization']['mode'], 'custom')

    def test_saved_exact_protections_block_generated_outgoing_but_not_manual_assessment(self):
        self.context['preferences'] = {'a': {'protect': True}, '2028-R1-3': {'protect': True},
                                       '2028-R1-4': {'target': True}, 'c': {'avoid': True}}
        result = trade.generate_trade_workflow(self.data, self.payload(workflow='shop', asset_id='a', partner_roster_id=0))
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['state'], 'CONSTRAINT_CONFLICT')
        manual = trade.evaluate_trade_request(self.data, self.payload(), projection_reader=self.fixture.reader)
        self.assertEqual(tuple(manual['proposal']['assets_sent']), ('a',))
        self.assertTrue(any('a' in row for row in manual['evaluation']['personal_preference_warnings']))
        generated = trade.generate_trade_workflow(self.data, self.payload(workflow='recommended', partner_roster_id=0, asset_id=None))
        for row in generated['results']:
            self.assertTrue({'a', '2028-R1-3'}.isdisjoint(row['proposal']['assets_sent']))
            self.assertIn('personal_preference_matches', row)
        # A protection applies to the original-franchise key, never all firsts.
        self.assertNotIn('2028-R1-4', generated['constraints']['protected_assets'])

    def test_missing_personal_price_is_unavailable_but_genuine_zero_remains_numeric(self):
        self.context['values']['a'] = None
        missing = calculate_trade_market(self.data, self.payload())
        self.assertIsNone(missing['personal']['sent']['total'])
        self.assertEqual(missing['personal']['sent']['missing_asset_ids'], ['a'])
        before = deepcopy(self.data)
        payload = self.payload()
        original = deepcopy(payload)
        with self.assertRaises(trade.TradeInputError) as rejected:
            trade.evaluate_trade_request(self.data, payload, projection_reader=self.fixture.reader)
        self.assertEqual(rejected.exception.code, 'personal_evidence_unavailable')
        self.assertEqual(self.data, before)
        self.assertEqual(payload, original)
        self.context['values']['a'] = 0
        zero = calculate_trade_market(self.data, self.payload())
        self.assertEqual(zero['personal']['sent']['total'], 0)
        self.assertEqual(zero['personal']['availability'], 'full')
        self.assertEqual(zero['market'], missing['market'])

    def test_custom_reassessment_does_not_run_an_extra_lineup_solver(self):
        from src.core.trade_intelligence.horizon_impact import evaluate_horizon_impact
        with patch('src.core.intelligence.evaluate_horizon_impact', wraps=evaluate_horizon_impact) as evaluate, \
                patch('src.core.trade_intelligence.bilateral.optimal_legal_lineup', side_effect=AssertionError('Legacy solver forbidden')):
            trade.evaluate_trade_request(self.data, self.payload(), projection_reader=self.fixture.reader)
        self.assertEqual(evaluate.call_count, 1)
