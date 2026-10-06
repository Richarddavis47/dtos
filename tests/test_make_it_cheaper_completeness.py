"""Cheaper repair completeness over canonical prices, owned picks and legal lineups."""
import copy
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from services import trade_intelligence as trade
from services.trade_cheaper_repair import cheaper_phase, market_cost
from src.core.intelligence.team_strength import prepare_for_data
from src.core.trade_intelligence.models import TradeProposal
from src.core.valuation.config import NORMALIZATION_VERSION
from tests import test_capital_strategy_reconciliation as capital_fixtures


class CheaperRepairCompletenessTests(unittest.TestCase):
    def setUp(self):
        fixture = capital_fixtures.CapitalStrategyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.data = fixture, fixture.data
        self.data['league']['roster_positions'] = ['QB', 'TE'] + ['BN'] * 22
        active = [('daniels', 'Jayden Daniels', 'QB', 20, 735),
                  ('backup', 'QB reserve', 'QB', 19, 500),
                  ('bijan', 'Bijan Robinson', 'RB', 18, 900),
                  ('te', 'TE reserve', 'TE', 3, 450)]
        # Ten target-priced replacements crowd low-value picks out of v1.21.7.
        active += [(f'depth{i}', f'Depth WR {i}', 'WR', 1, 750 + i * 5) for i in range(12)]
        partner = [('mcbride', 'Trey McBride', 'TE', 18, 775),
                   ('pqb', 'Partner QB', 'QB', 8, 800),
                   ('pte', 'Partner TE reserve', 'TE', 17, 500)]
        fixture.points, self.data['players'] = {}, {}
        for team, players in zip(self.data['teams'], (active, partner)):
            team['strategy'], team['players'], team['picks_owned'] = 'WIN NOW', [], []
            for pid, name, position, points, _ in players:
                team['players'].append({'id': pid, 'name': name, 'position': position, 'roster_slot': 'Bench'})
                self.data['players'][pid] = {'full_name': name, 'position': position, 'age': 24}
                fixture.points[pid] = points
        self.data['teams'][0]['picks_owned'] = [
            {'year': year, 'round': round_, 'original_roster_id': origin, 'current_owner_id': 1}
            for year, round_, origin in ((2029, 3, 1), (2027, 4, 1), (2027, 4, 3))]
        fixture.prices(**{pid: price for pid, _, _, _, price in active + partner})
        # Valid prepared canonical references pin fixture prices independently of
        # the deliberately crowded provider population. Strategy never prices them.
        for row in self.data['market_data']['providers']['FantasyCalc'].values():
            row['normalization_reference'] = {'provider': 'FantasyCalc', 'raw_value': float(row['value']),
                'normalized_value': int(row['value'] / 12), 'version': NORMALIZATION_VERSION,
                'generation': 'cheaper-fixture', 'method': 'provider_range_linear'}
        self.data['market_data']['pick_quotes']['FantasyCalc'] = [self.quote(2029, 3, 28), self.quote(2027, 4, 16)]
        payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
            'stats': {'pass_yd': points}, 'player': {'position': self.data['players'][pid]['position']}}
            for pid, points in fixture.points.items()] for week in (2, 3, 4, 5)}
        fixture.reader.publish_horizon(payloads, data=self.data, league_id='league-1', season=2026, current_week=2)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(fixture.reader, self.data)
        self.addCleanup(patch.stopall)
        patch('services.trade_intelligence._trade_projection_service', return_value=fixture.reader).start()
        self.payload = {'active_roster_id': 1, 'partner_roster_id': 2, 'assets_sent': ['daniels', '2029-R3-1'],
            'assets_received': ['mcbride'], 'strategy': 'WIN NOW', 'instruction': 'make it cheaper',
            'origin_workflow': 'shop', 'origin_asset_id': 'daniels', 'protected_assets': ['bijan', '2027-R4-3']}

    @staticmethod
    def quote(year, round_, value):
        return {'provider': 'FantasyCalc', 'market_format': 'fc:12:2qb:ppr', 'year': year, 'round': round_,
            'pick_type': 'generic_round', 'availability': 'current', 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'value': value * 12, 'confidence': 80,
            'normalization_reference': {'provider': 'FantasyCalc', 'raw_value': float(value * 12),
                'normalized_value': value, 'version': NORMALIZATION_VERSION, 'generation': 'cheaper-fixture',
                'method': 'provider_range_linear'}}

    def workspace(self):
        return trade.build_trade_workspace(self.data, 1)

    def repair(self, **extra):
        return trade.assist_trade_request(self.data, {**self.payload, **extra})

    def several_picks(self):
        for year, round_, price in ((2027, 3, 24), (2028, 4, 18)):
            self.data['teams'][0]['picks_owned'].append({'year': year, 'round': round_, 'original_roster_id': 1,
                                                      'current_owner_id': 1})
            self.data['market_data']['pick_quotes']['FantasyCalc'].append(self.quote(year, round_, price))

    def test_scout_763_to_751_is_actually_evaluated_and_returned(self):
        original = copy.deepcopy(self.payload)
        evaluate, assessed = trade.evaluate_trade_request, []
        def observe(data, payload, **kwargs):
            assessed.append(set(payload['assets_sent']))
            return evaluate(data, payload, **kwargs)
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=observe):
            result = self.repair()
        revised = next(r for r in result['results'] if set(r['proposal']['assets_sent']) == {'daniels', '2027-R4-1'})
        self.assertIn({'daniels', '2027-R4-1'}, assessed)
        self.assertEqual(revised['evaluation']['recommendation'], 'WORTH PURSUING')
        self.assertEqual(revised['adjustment_evidence']['current_outgoing_cost'], 763)
        self.assertEqual(revised['adjustment_evidence']['alternative_outgoing_cost'], 751)
        self.assertEqual(revised['adjustment_evidence']['market_cost_reduction'], 12)
        self.assertEqual(self.payload, original)
        self.assertTrue(result['preview_only'])
        self.assertEqual(result['original_proposal']['assets_sent'], original['assets_sent'])
        self.assertEqual(result['constraints']['protected_assets'], ['2027-R4-3', 'bijan'])

    def test_first_candidate_fails_second_is_still_evaluated(self):
        evaluate, assessed = trade.evaluate_trade_request, []
        def first_fails(data, payload, **kwargs):
            row = evaluate(data, payload, **kwargs)
            assessed.append(row)
            if len(assessed) == 1:
                row['evaluation'].update(generated_trade_eligible=False, recommendation='NOT WORTH IT')
                row['evaluation']['recommendation_trace']['rule_reasons'] = ['FIXTURE_STRATEGIC_REJECTION']
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=first_fails):
            result = self.repair()
        self.assertGreaterEqual(len(assessed), 2)
        self.assertTrue(any(set(r['proposal']['assets_sent']) == {'daniels', '2027-R4-1'} for r in result['results']))
        self.assertEqual(result['search_evidence']['strategically_rejected'], 1)

    def test_several_cheaper_packages_return_ranked_subset_and_stop_usefully(self):
        self.several_picks()
        result = self.repair()
        self.assertEqual(result['count'], 3)
        self.assertEqual(result['search_evidence']['repair_stop_reason'], 'SUFFICIENT_USEFUL_ALTERNATIVES')
        self.assertLess(result['search_evidence']['full_evaluations'], 160)
        costs = [r['adjustment_evidence']['alternative_outgoing_cost'] for r in result['results']]
        self.assertTrue(all(c < 763 for c in costs))
        self.assertEqual(len({tuple(sorted(r['proposal']['assets_sent'])) for r in result['results']}), 3)

    def test_player_and_exact_pick_locks_other_fourth_is_usable(self):
        workspace = self.workspace()
        workspace['pools'][1] = tuple(replace(a, trade_value=12) if a.asset_id == 'bijan' else a
                                     for a in workspace['pools'][1])
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace):
            result = self.repair()
        self.assertTrue(result['results'])
        for row in result['results']:
            self.assertFalse({'bijan', '2027-R4-3'} & set(row['proposal']['assets_sent']))
        self.assertTrue(any('2027-R4-1' in r['proposal']['assets_sent'] for r in result['results']))
        self.assertGreater(result['search_evidence']['prune_reason_counts']['EXACT_LOCK_CONFLICT'], 0)

    def test_required_shop_anchor_and_trade_for_target_are_not_removed(self):
        shop = self.repair()
        self.assertTrue(shop['results'])
        self.assertTrue(all('daniels' in r['proposal']['assets_sent'] for r in shop['results']))
        self.assertGreater(shop['search_evidence']['prune_reason_counts']['REQUIRED_SHOP_ANCHOR_MISSING'], 0)
        target = self.repair(origin_workflow='trade_for', origin_asset_id='mcbride')
        self.assertTrue(target['results'])
        self.assertTrue(all('mcbride' in r['proposal']['assets_received'] for r in target['results']))

    def test_malformed_constructed_candidate_cannot_drop_required_target(self):
        workspace = self.workspace()
        assets = {a.asset_id: a for p in workspace['pools'].values() for a in p}
        invalid = TradeProposal(1, 2, (assets['daniels'],), (assets['pte'],), 'Wrong target')
        diagnostics = {'cheap_package_pairs_inspected': 1, 'cheaper_by_price_candidates': 1,
                       'prune_reason_counts': {}, 'missing_asset_ids': []}
        with patch('services.trade_intelligence.cheaper_phase', return_value=((invalid,), diagnostics)), \
             patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('invalid target evaluated')):
            result = self.repair(origin_workflow='trade_for', origin_asset_id='mcbride')
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['search_evidence']['prune_reason_counts']['REQUIRED_INCOMING_TARGET_MISSING'], 3)

    def test_equal_cost_is_not_cheaper_and_full_precision_is_retained(self):
        workspace = self.workspace()
        def priced(value):
            workspace['pools'][1] = tuple(replace(a, trade_value=value) if a.asset_id == '2027-R4-1' else a
                                         for a in workspace['pools'][1])
        priced(28)
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace):
            equal = self.repair()
        self.assertFalse(any('2027-R4-1' in r['proposal']['assets_sent'] for r in equal['results']))
        priced(27.9999)
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace):
            precise = self.repair()
        revised = next(r for r in precise['results'] if '2027-R4-1' in r['proposal']['assets_sent'])
        self.assertLess(revised['adjustment_evidence']['alternative_outgoing_cost'], 763)
        self.assertAlmostEqual(revised['adjustment_evidence']['market_cost_reduction'], .0001)
        self.assertIsNone(market_cost((replace(workspace['pools'][1][0], trade_value=float('nan')),)))

    def test_missing_current_price_does_not_invent_comparison(self):
        workspace = self.workspace()
        workspace['pools'][1] = tuple(replace(a, trade_value=None) if a.asset_id == '2029-R3-1' else a
                                     for a in workspace['pools'][1])
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace), \
             patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('unpriced comparison')):
            result = self.repair()
        self.assertEqual(result['result_state'], 'MISSING REQUIRED EVIDENCE')
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)
        self.assertIn('2029-R3-1', result['quiet_state'])

    def test_missing_candidate_price_is_disclosed_without_blocking_priced_routes(self):
        workspace = self.workspace()
        workspace['pools'][1] = tuple(replace(a, trade_value=None) if a.asset_id == '2027-R4-1' else a
                                     for a in workspace['pools'][1])
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace):
            result = self.repair()
        self.assertTrue(result['results'])
        self.assertFalse(any('2027-R4-1' in r['proposal']['assets_sent'] for r in result['results']))
        self.assertIn('2027-R4-1', result['search_evidence']['missing_asset_ids'])

    def test_no_cheaper_construction_explains_preserved_anchor(self):
        result = self.repair(assets_sent=['daniels'])
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)
        self.assertIn('No lower-cost construction', result['quiet_state'])
        self.assertIn('Shop anchor', result['quiet_state'])

    def test_evaluated_rejections_show_exact_reason_not_generic_failure(self):
        evaluate = trade.evaluate_trade_request
        def rejected(data, payload, **kwargs):
            row = evaluate(data, payload, **kwargs)
            row['evaluation'].update(generated_trade_eligible=False, recommendation='NOT WORTH IT')
            row['evaluation']['recommendation_trace']['rule_reasons'] = ['FIXTURE_COUNTERPARTY_MATERIAL_LOSS']
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=rejected):
            result = self.repair()
        self.assertEqual(result['count'], 0)
        self.assertGreater(result['search_evidence']['evaluated'], 1)
        self.assertIn('FIXTURE_COUNTERPARTY_MATERIAL_LOSS', result['quiet_state'])
        self.assertTrue(result['near_misses'])
        self.assertEqual(result['search_evidence']['repair_stop_reason'], 'CONSTRUCTIONS_EXHAUSTED')

    def test_budget_exhaustion_is_explicit_and_remaining_candidates_not_claimed_bad(self):
        self.several_picks()
        evaluate = trade.evaluate_trade_request
        def rejected(data, payload, **kwargs):
            row = evaluate(data, payload, **kwargs)
            row['evaluation'].update(generated_trade_eligible=False, recommendation='NOT WORTH IT')
            return row
        with patch('services.trade_intelligence.REPAIR_EVALUATION_BUDGET', 2), \
             patch('services.trade_intelligence.evaluate_trade_request', side_effect=rejected):
            result = self.repair()
        self.assertEqual(result['search_evidence']['full_evaluations'], 2)
        self.assertEqual(result['search_evidence']['repair_stop_reason'], 'EVALUATION_BUDGET_EXHAUSTED')
        self.assertGreater(result['search_evidence']['unevaluated_constructions'], 0)
        self.assertIn('2-evaluation repair budget', result['quiet_state'])
        self.assertIn('unassessed', result['quiet_state'])

    def test_progressive_package_change_reaches_credible_second_phase(self):
        self.several_picks()
        self.data['market_data']['pick_quotes']['FantasyCalc'][-1] = self.quote(2028, 4, 8)
        evaluate = trade.evaluate_trade_request
        def only_package_change(data, payload, **kwargs):
            row = evaluate(data, payload, **kwargs)
            if len(payload['assets_sent']) < 3:
                row['evaluation'].update(generated_trade_eligible=False, recommendation='NOT WORTH IT')
            return row
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=only_package_change):
            result = self.repair()
        self.assertTrue(result['results'])
        self.assertTrue(all(len(r['proposal']['assets_sent']) == 3 for r in result['results']))
        self.assertEqual([s['search_phase'] for s in result['search_evidence']['stages']], [0, 1, 2])

    def test_funnel_conserves_every_construction_and_evaluation(self):
        self.several_picks()
        result = self.repair()
        d = result['search_evidence']
        self.assertEqual(d['evaluation_budget'], 160)
        self.assertEqual(d['constructions_generated'], d['constructions_pruned'] + d['evaluated'] + d['unevaluated_constructions'])
        self.assertEqual(d['constructions_pruned'], sum(d['prune_reason_counts'].values()))
        self.assertEqual(d['evaluated'], sum(d[k] for k in ('hard_invalid', 'missing_evidence', 'counterparty_limited',
                                                          'strategically_rejected', 'filtered', 'eligible')))
        self.assertEqual(d['displayed'], result['count'])
        self.assertEqual(d['projection_weeks_read'], 4)
        self.assertEqual(d['provider_requests'], 0)
        self.assertEqual(d['durable_writes'], 0)

    def test_equivalent_pick_variants_do_not_fill_all_slots(self):
        self.data['teams'][0]['picks_owned'].append({'year': 2027, 'round': 4, 'original_roster_id': 4, 'current_owner_id': 1})
        result = self.repair()
        pick_variants = [r for r in result['results'] if '2027-R4-1' in r['proposal']['assets_sent']
                         or '2027-R4-4' in r['proposal']['assets_sent']]
        self.assertEqual(len(pick_variants), 1)
        self.assertGreater(result['search_evidence']['credible_cheaper'], result['count'])

    def test_constructor_rejects_wrong_owner_and_invalid_exact_pick(self):
        workspace = self.workspace()
        workspace['pools'][1] = tuple(replace(a, source_roster_id=2) if a.asset_id == '2027-R4-1' else a
                                     for a in workspace['pools'][1])
        _, d = cheaper_phase(workspace, dict(self.payload, required_outgoing_assets=['daniels']), 0, set())
        self.assertGreater(d['prune_reason_counts']['ASSET_NOT_OWNED'], 0)
        workspace = self.workspace()
        workspace['pools'][1] = tuple(replace(a, original_roster_id=99) if a.asset_id == '2027-R4-1' else a
                                     for a in workspace['pools'][1])
        _, d = cheaper_phase(workspace, dict(self.payload, required_outgoing_assets=['daniels']), 0, set())
        self.assertGreater(d['prune_reason_counts']['INVALID_PICK_IDENTITY'], 0)

    def test_full_160_evaluation_budget_is_enforced_on_progressive_failure(self):
        workspace = self.workspace()
        template = next(a for a in workspace['pools'][1] if a.asset_id == 'depth0')
        workspace['pools'][1] = tuple(a for a in workspace['pools'][1]
                                     if a.asset_id in {'daniels', '2029-R3-1', '2027-R4-1', '2027-R4-3', 'bijan'})
        workspace['pools'][1] += tuple(replace(template, asset_id=f'cheap{i}', label=f'Cheap fixture {i}',
                                             trade_value=1) for i in range(30))
        assessed = []
        def rejected(data, payload, **kwargs):
            assessed.append(payload)
            return {'proposal': {k: payload[k] for k in ('active_roster_id', 'partner_roster_id', 'assets_sent', 'assets_received')},
                    'evaluation': {'generated_trade_eligible': False, 'legal': True, 'recommendation': 'NOT WORTH IT',
                                   'recommendation_trace': {'rule_reasons': ['FIXTURE_MATERIAL_COST']}}}
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace), \
             patch('services.trade_intelligence.evaluate_trade_request', side_effect=rejected):
            result = self.repair()
        self.assertEqual(len(assessed), 160)
        self.assertEqual(result['search_evidence']['full_evaluations'], 160)
        self.assertTrue(result['search_evidence']['budget_reached'])
        self.assertEqual(result['search_evidence']['repair_stop_reason'], 'EVALUATION_BUDGET_EXHAUSTED')
        self.assertGreater(result['search_evidence']['unevaluated_constructions'], 0)
        self.assertIn('160-evaluation repair budget', result['quiet_state'])

    def test_empty_repair_distinguishes_legality_evidence_counterparty_and_strategy(self):
        evaluate = trade.evaluate_trade_request
        for field, wording in (('hard_invalid', 'legality'), ('missing_evidence', 'required projection'),
                               ('counterparty_limited', 'meaningful counterparty benefit'),
                               ('strategically_rejected', 'selected strategy')):
            with self.subTest(field=field):
                def reject(data, payload, **kwargs):
                    row = evaluate(data, payload, **kwargs)
                    e = row['evaluation']
                    e['generated_trade_eligible'] = False
                    e['recommendation_trace']['rule_reasons'] = ['EXACT_FIXTURE_BLOCKER']
                    if field == 'hard_invalid':
                        e['legal'] = False
                    elif field == 'missing_evidence':
                        e['recommendation'] = None
                        e['dimensions']['strategic_fit']['active']['projection_coverage_complete'] = False
                    elif field == 'counterparty_limited':
                        e['recommendation'] = 'WORTH PURSUING'
                        e['dimensions']['counterparty_plausibility']['assessment'] = 'LOW'
                    else:
                        e['recommendation'] = 'NOT WORTH IT'
                    return row
                with patch('services.trade_intelligence.evaluate_trade_request', side_effect=reject):
                    result = self.repair()
                self.assertEqual(result['count'], 0)
                self.assertEqual(result['search_evidence'][field], 2)
                self.assertIn(wording, result['quiet_state'])
                self.assertIn('EXACT_FIXTURE_BLOCKER', result['quiet_state'])
