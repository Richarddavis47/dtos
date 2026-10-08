"""Canonical calculator arithmetic, owned balancing and unchanged bilateral analysis."""
import copy
from dataclasses import asdict, replace
from statistics import median
from time import perf_counter
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from services.trade_calculator import balance_trade_market, calculate_trade_market, market_generation, market_verdict
from tests import test_capital_strategy_reconciliation as capital
from tests import test_trade_workspace_batch1 as boundary


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.f = capital.CapitalStrategyTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        self.f.prices(a=350, b=100, c=250, d=100, e=200, f=20)
        self.payload = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['a'],
                        'assets_received': ['c'], 'workflow': 'create', 'strategy': 'RETOOL'}

    def calculate(self, **updates):
        return calculate_trade_market(self.data, {**self.payload, **updates})

    def balance(self, **updates):
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.f.reader):
            return balance_trade_market(self.data, {**self.payload, **updates})

    def test_receiving_side_favored_exact_decimal_gap_and_no_arbitrary_band(self):
        self.assertEqual(self.calculate()['market']['verdict'], 'SIDE_B_FAVORED')
        self.assertEqual(self.calculate()['market']['absolute_gap'], 100)
        self.assertEqual(self.calculate(assets_sent=['b'])['market']['verdict'], 'SIDE_A_FAVORED')
        self.assertEqual(self.calculate(assets_received=['c', 'd'])['market']['verdict'], 'APPROXIMATELY_BALANCED')
        ws = trade.build_trade_workspace(self.data, 1, market_only=True)
        a, b = ws['pools'][1][:2]
        result = market_verdict([replace(a, trade_value=0.1), replace(b, trade_value=0.2)], [replace(a, trade_value=0.3)])
        self.assertEqual(result['absolute_gap'], 0)
        self.assertEqual(market_verdict([replace(a, trade_value=0.300001)], [replace(a, trade_value=0.3)])['verdict'], 'SIDE_B_FAVORED')

    def test_prepared_facts_match_normal_workspace_strategy_independent_and_no_fois(self):
        normal = trade.build_trade_workspace(self.data, 1)
        with patch('services.trade_intelligence.build_league_model', side_effect=AssertionError('Basic calculator must not build FOIS')):
            fast = trade.build_trade_workspace(self.data, 1, market_only=True)
            reports = [self.calculate(strategy=s) for s in ('WIN NOW', 'RETOOL', 'REBUILD')]
        self.assertEqual(market_generation(normal), market_generation(fast))
        self.assertTrue(all(r['market'] == reports[0]['market'] for r in reports))
        self.assertFalse(reports[0]['advanced_analysis_performed'])
        self.assertEqual(reports[0]['provider_requests'], 0)

    def test_missing_price_partial_never_zero_no_verdict_or_forced_balance(self):
        ws = trade.build_trade_workspace(self.data, 1, market_only=True)
        ws['pools'][1] = tuple(replace(a, trade_value=None) if a.asset_id == 'a' else a for a in ws['pools'][1])
        result = calculate_trade_market(self.data, {**self.payload, 'assets_sent': ['a', 'b']}, workspace=ws)
        self.assertEqual(result['market']['verdict'], 'UNAVAILABLE')
        self.assertIsNone(result['market']['sent']['total'])
        self.assertEqual(result['market']['sent']['known_subtotal'], 100)
        self.assertEqual(result['market']['sent']['missing_asset_ids'], ['a'])
        with patch('services.trade_intelligence.build_trade_workspace', return_value=ws):
            balanced = self.balance(assets_sent=['a', 'b'])
        self.assertEqual(balanced['results'], [])
        self.assertEqual(balanced['state'], 'MARKET_EVIDENCE_UNAVAILABLE')

    def test_add_remove_exact_acquired_pick_and_duplicate_rejection(self):
        added = self.calculate(assets_sent=['a', '2028-R2-3'])
        self.assertEqual(added['market']['sent']['total'], 450)
        pick = added['assets_sent'][1]
        self.assertEqual((pick['season'], pick['round'], pick['original_roster_id'], pick['current_owner_id']), (2028, 2, 3, 1))
        self.assertEqual(self.calculate()['market']['sent']['total'], 350)
        with self.assertRaisesRegex(trade.TradeInputError, 'twice'):
            self.calculate(assets_sent=['a', 'a'])

    def test_balancing_addition_and_swap_owned_narrow_gap_no_mutation(self):
        before = copy.deepcopy(self.data)
        result = self.balance()
        kinds = {r['balance_adjustment']['change'] for r in result['results']}
        self.assertTrue({'ADD_PLAYER', 'ADD_PICK', 'SWAP_ASSET'}.issubset(kinds), kinds)
        ws = trade.build_trade_workspace(self.data, 1)
        for row in result['results']:
            trade.validate_trade_ownership(ws, row['proposal'])
            self.assertLess(row['balance_adjustment']['suggested']['absolute_gap'], 100)
            if row['balance_adjustment']['change'].startswith('ADD'):
                self.assertEqual(row['proposal']['assets_sent'], ('a',))
                self.assertTrue(set(row['proposal']['assets_received']) > {'c'})
        self.assertEqual(self.data, before)
        self.assertTrue(result['preview_only'])
        self.assertLessEqual(result['search_evidence']['evaluated'], 8)
        self.assertLessEqual(result['search_evidence']['constructed'], 512)
        self.assertEqual(result['search_evidence']['reuse']['candidate_results_retained'], 0)
        self.assertEqual(result['search_evidence']['reuse']['workers_created'], 0)

    def test_reverse_addition_direction_and_exact_player_pick_locks(self):
        result = self.balance(assets_sent=['b'], assets_received=['c'], protected_assets=['e', '2028-R1-3'])
        self.assertTrue(result['results'])
        for row in result['results']:
            self.assertTrue({'e', '2028-R1-3'}.isdisjoint(row['proposal']['assets_sent']))
            if row['balance_adjustment']['change'].startswith('ADD'):
                self.assertEqual(row['proposal']['assets_received'], ('c',))
                self.assertTrue(set(row['proposal']['assets_sent']) > {'b'})

    def test_same_round_acquired_picks_remain_distinct_under_exact_lock(self):
        self.data['teams'][0]['picks_owned'].append({'year': 2028, 'round': 1, 'original_roster_id': 8, 'current_owner_id': 1})
        result = self.balance(assets_sent=['b'], assets_received=['c'], protected_assets=['2028-R1-3'])
        ws = trade.build_trade_workspace(self.data, 1, market_only=True)
        picks = {a.asset_id: a for a in ws['pools'][1] if a.kind == 'pick'}
        self.assertIn('2028-R1-8', picks)
        self.assertEqual(picks['2028-R1-8'].current_owner_id, 1)
        self.assertTrue(all('2028-R1-3' not in r['proposal']['assets_sent'] for r in result['results']))
        self.assertTrue(any('2028-R1-8' in r['proposal']['assets_sent'] for r in result['results']))
        self.assertNotEqual(asdict(picks['2028-R1-8']), asdict(picks['2028-R1-3']))

    def test_required_anchors_protected_original_and_specific_optional_conflicts(self):
        result = self.balance(required_outgoing_asset='a', required_incoming_asset='c')
        self.assertTrue(result['results'])
        for row in result['results']:
            self.assertIn('a', row['proposal']['assets_sent'])
            self.assertIn('c', row['proposal']['assets_received'])
        conflict = self.balance(protected_assets=['a'])
        self.assertEqual(conflict['state'], 'PROTECTED_ASSET_CONFLICT')
        self.assertEqual(conflict['blocking_asset_ids'], ['a'])
        self.assertIn('never', conflict['smallest_optional_relaxation'])
        self.assertEqual(self.balance(required_outgoing_asset='c')['state'], 'PROTECTED_ASSET_CONFLICT')

    def test_generation_change_and_ownership_transition_block_stale_offer(self):
        generation = self.calculate()['market_generation']
        self.f.prices(a=360)
        with self.assertRaisesRegex(trade.TradeInputError, 'Market evidence changed'):
            self.calculate(market_generation=generation)
        self.data['teams'][1]['players'] = [p for p in self.data['teams'][1]['players'] if p['id'] != 'c']
        with self.assertRaises(trade.TradeInputError):
            self.calculate()
        self.assertNotEqual(generation, market_generation(trade.build_trade_workspace(self.data, 1, market_only=True)))

    def test_mid_balance_generation_publication_rejects_mixed_response(self):
        original = trade.evaluate_trade_request
        def publish(*args, **kwargs):
            row = original(*args, **kwargs)
            self.data['market_data']['generation'] = 'new-generation'
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=publish):
            with self.assertRaisesRegex(trade.TradeInputError, 'during balancing'):
                self.balance()

    def test_exact_pick_substitution_narrows_gap(self):
        result = self.balance(assets_sent=['a', '2028-R1-3'], assets_received=['c', '2028-R1-4'],
                              required_outgoing_asset='a', required_incoming_asset='c', protected_assets=['b', 'e'],
                              excluded_assets=['d', 'f', '2028-R2-4', '2028-R4-4', '2028-R4-3'])
        swaps = [r for r in result['results'] if r['balance_adjustment']['change'] == 'SWAP_PICK']
        self.assertTrue(swaps, [r['balance_adjustment']['change'] for r in result['results']])
        self.assertLess(swaps[0]['balance_adjustment']['suggested']['absolute_gap'], 100)

    def test_advanced_integration_preserves_package_market_and_overpay_visible(self):
        payload = {**self.payload, 'assets_sent': ['2028-R1-3', '2028-R2-3'], 'assets_received': ['c'], 'strategy': 'WIN NOW'}
        arithmetic = calculate_trade_market(self.data, payload)
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.f.reader):
            advanced = trade.evaluate_trade_request(self.data, payload)
        self.assertEqual(advanced['proposal']['assets_sent'], tuple(payload['assets_sent']))
        self.assertEqual(advanced['evaluation']['market_evidence']['sent'], arithmetic['market']['sent'])
        self.assertEqual(arithmetic['market']['verdict'], 'SIDE_B_FAVORED')
        self.assertIn('multi_horizon_impact', advanced['evaluation'])

    def test_poor_stuffing_and_capacity_never_promoted_as_attractive(self):
        original = trade.evaluate_trade_request
        def poor(*args, **kwargs):
            row = original(*args, **kwargs)
            row['evaluation']['dimensions']['package_quality']['partner']['assessment'] = 'POOR'
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=poor):
            result = self.balance()
        self.assertEqual(result['results'], [])
        self.assertTrue(result['near_misses'])
        self.assertTrue(all(r['balance_adjustment']['quality'] == 'POOR' for r in result['near_misses']))

    def test_actual_arithmetic_improvement_with_three_noncontributors_is_a_near_miss(self):
        self.f.points.update(a=10, b=5, e=6, c=3, d=2, f=1)
        self.f.prices(a=350, b=100, e=100, c=100, d=100, f=100)
        self.f.publish()
        result = self.balance(assets_received=['c', 'd'], required_outgoing_asset='a',
                              required_incoming_asset='c', protected_assets=['b', 'e'],
                              excluded_assets=['2028-R1-3', '2028-R2-3', '2028-R4-3',
                                               '2028-R1-4', '2028-R2-4', '2028-R4-4'])
        stuffing = [r for r in result['near_misses'] if set(r['proposal']['assets_received']) == {'c', 'd', 'f'}]
        self.assertTrue(stuffing, result['state'])
        self.assertEqual(stuffing[0]['evaluation']['dimensions']['package_quality']['active']['assessment'], 'POOR')
        self.assertLess(stuffing[0]['balance_adjustment']['suggested']['absolute_gap'], 150)
        self.assertFalse(result['results'])

    def test_real_capacity_issue_is_disclosed_not_promoted(self):
        self.data['league']['roster_positions'] = ['QB', 'BN', 'BN']
        self.f.publish()
        result = self.balance(assets_sent=['2028-R1-3'], assets_received=['c'])
        # Equal totals need no forced suggestion; deliberately underpay below.
        self.assertEqual(result['state'], 'ALREADY_BALANCED')
        result = self.balance(assets_sent=['b'], assets_received=['c'], required_incoming_asset='c')
        for row in result['results']:
            self.assertFalse(any((q.get('roster_capacity') or {}).get('additional_spots_to_resolve')
                                 for q in row['evaluation']['dimensions']['package_quality'].values()))

    def test_fact_resolution_once_and_bounded_baseline_reuse_performance(self):
        with patch('services.trade_intelligence.cached_market_facts', wraps=trade.cached_market_facts) as facts:
            result = self.balance()
        self.assertEqual(facts.call_count, 1)
        self.assertGreater(result['search_evidence']['reuse']['lineup_hits'], 0)
        self.assertLessEqual(result['search_evidence']['projection_weeks_read'], 4)
        times = []
        for _ in range(3):
            start = perf_counter()
            self.calculate()
            times.append(perf_counter() - start)
        self.assertLess(max(times), 2)
        print('CALCULATOR_PROFILE', {'basic_p50_seconds': median(times), 'basic_worst_seconds': max(times),
                                    'balance_seconds': result['search_evidence']['total_seconds'], 'evaluations': result['search_evidence']['evaluated']})


class CalculatorApiTests(unittest.TestCase):
    def setUp(self):
        self.f = boundary.AuthenticatedTradeBoundaryTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_real_calculation_and_authentication_csrf_workspace_boundaries(self):
        f = self.f
        w = f.client.get('/api/trades/workspace?mode=calculator').json()
        self.assertIn('calculator_generation', w)
        self.assertEqual(f.client.get('/trades/calculator?front_office=1').status_code, 200)
        payload = {**f.payload, 'workspace_context': w['workspace_context']}
        response = f.client.post('/api/trades/calculate', json=payload, headers={'X-CSRF-Token': f.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['market']['verdict'], 'APPROXIMATELY_BALANCED')
        for path in ('calculate', 'balance'):
            self.assertEqual(f.client.post('/api/trades/' + path, json=payload).status_code, 403)
            response = f.client.post('/api/trades/' + path, json={**payload, 'active_roster_id': 2}, headers={'X-CSRF-Token': f.csrf})
            self.assertEqual(response.status_code, 422)
        f.client.cookies.clear()
        self.assertEqual(f.client.post('/api/trades/calculate', json=payload).status_code, 401)
