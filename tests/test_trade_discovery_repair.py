"""Discovery/repair acceptance over canonical prices and real legal lineups."""
import copy
import unittest
from unittest.mock import patch

from services.trade_intelligence import (
    generate_trade_workflow, assist_trade_request, create_trade_alternatives,
    build_trade_workspace, evaluate_trade_request,
)
from services.trade_search_policy import classify
from tests import test_capital_strategy_reconciliation as capital_fixtures


class DiscoveryRepairTests(unittest.TestCase):
    def setUp(self):
        fixture = capital_fixtures.CapitalStrategyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.data = fixture.data
        template = copy.deepcopy(self.data['teams'][0])
        self.data['league']['roster_positions'] = ['QB', 'WR'] + ['BN'] * 8
        self.data['teams'] = []
        self.data['players'] = {}
        fixture.points = {}
        for rid in range(1, 8):
            team = dict(copy.deepcopy(template), roster_id=rid, team_name=f'Fixture {rid}', strategy='RETOOL')
            team['players'] = []
            for suffix, position, points, age in (
                ('q', 'QB', 20 if rid == 1 else 8, 31),
                ('w', 'WR', 5 if rid == 1 else 13 + rid, 29),
                ('qb', 'QB', 14 if rid == 1 else 6, 23),
                ('wb', 'WR', 4 if rid == 1 else 11, 22),
            ):
                pid = f'{rid}{suffix}'
                team['players'].append({'id': pid, 'name': pid, 'position': position, 'roster_slot': 'Bench'})
                self.data['players'][pid] = {'full_name': pid, 'position': position, 'age': age}
                fixture.points[pid] = points
            team['picks_owned'] = [{'year': 2028, 'round': r, 'original_roster_id': rid + 20,
                                    'current_owner_id': rid} for r in (1, 2, 4)]
            self.data['teams'].append(team)
        fixture.prices(**{pid: 100 if pid.endswith('b') else 250 for pid in fixture.points})
        fixture.publish()
        # pass_yd is the fixture scoring statistic; projection eligibility is
        # from each canonical player position, not a fake pick projection.
        self.addCleanup(patch.stopall)
        patch('services.trade_intelligence._trade_projection_service', return_value=fixture.reader).start()

    def search(self, workflow, **kwargs):
        return generate_trade_workflow(self.data, dict(workflow=workflow, active_roster_id=1,
            strategy='RETOOL', **kwargs))

    def proposal(self, sent=None, received=None, **kwargs):
        return dict({'active_roster_id': 1, 'partner_roster_id': 2, 'strategy': 'RETOOL',
                    'assets_sent': sent or ['1q'], 'assets_received': received or ['2w']}, **kwargs)

    def test_recommended_diverse_top_five_and_next_page(self):
        first = self.search('recommended')
        self.assertEqual(first['count'], 5)
        self.assertEqual(len({r['family_id'] for r in first['results']}), 5)
        self.assertGreaterEqual(len({r['proposal']['partner_roster_id'] for r in first['results']}), 3)
        second = self.search('recommended', excluded_recommendation_families=[r['family_id'] for r in first['results']])
        self.assertTrue(second['results'])
        self.assertFalse({r['family_id'] for r in first['results']} & {r['family_id'] for r in second['results']})
        self.assertLessEqual(first['search_evidence']['evaluated'], 180)

    def test_recommended_fewer_than_five_are_shown(self):
        self.data['teams'] = self.data['teams'][:2]
        self.fixture.publish()
        result = self.search('recommended', excluded_assets=['2q', '2qb', '2wb', '2028-R1-22', '2028-R2-22', '2028-R4-22'])
        self.assertGreater(result['count'], 0)
        self.assertLess(result['count'], 5)

    def test_shop_player_and_pick_keep_exact_asset_all_teams_and_optional_partner(self):
        for asset in ('1q', '2028-R1-21'):
            result = self.search('shop', asset_id=asset)
            self.assertTrue(result['results'], result['search_evidence'])
            self.assertEqual(result['search_evidence']['eligible_partners'], 6)
            for market in result['markets']:
                for row in market['returns']:
                    self.assertIn(asset, row['proposal']['assets_sent'])
        one = self.search('shop', asset_id='1q', partner_roster_id=2)
        self.assertTrue(one['results'])
        self.assertEqual(one['search_evidence']['teams_searched'], 1)

    def test_trade_for_actual_owner_retained_target_and_varied_shapes(self):
        result = self.search('trade_for', asset_id='2w')
        self.assertGreaterEqual(result['count'], 2)
        for row in result['results']:
            self.assertIn('2w', row['proposal']['assets_received'])
            self.assertEqual(row['proposal']['partner_roster_id'], 2)
        shapes = {(len(r['proposal']['assets_sent']), len(r['proposal']['assets_received'])) for r in result['results']}
        kinds = {tuple(a['kind'] for a in r['proposal_presentation']['send']) for r in result['results']}
        self.assertTrue(len(shapes) > 1 or len(kinds) > 1)

    def test_make_cheaper_evaluated_preview_preserves_original_and_target(self):
        payload = self.proposal(sent=['1q', '2028-R2-21'], instruction='make it cheaper')
        before = copy.deepcopy(payload)
        original_cost = evaluate_trade_request(self.data, payload, projection_reader=self.fixture.reader)['evaluation']['values']['sent']
        result = assist_trade_request(self.data, payload)
        self.assertTrue(result['results'], result)
        self.assertTrue(result['preview_only'])
        for row in result['results']:
            self.assertLess(row['evaluation']['values']['sent'], original_cost)
            self.assertIn('2w', row['proposal']['assets_received'])
        self.assertEqual(payload, before)

    def test_protect_exact_player_and_one_pick_other_picks_still_usable(self):
        self.data['teams'][1]['strategy'] = 'REBUILD'
        self.fixture.publish()
        player = assist_trade_request(self.data, self.proposal(instruction='keep this player', constraint_asset_id='1q'))
        self.assertEqual(player['constraints']['protected_assets'], ['1q'])
        self.assertTrue(player['results'])
        for row in player['results']:
            self.assertNotIn('1q', row['proposal']['assets_sent'])
        pick = assist_trade_request(self.data, self.proposal(sent=['2028-R1-21'], received=['2wb'],
            instruction='do not trade this pick', constraint_asset_id='2028-R1-21'))
        self.assertEqual(pick['constraints']['protected_assets'], ['2028-R1-21'])
        self.assertTrue(pick['results'])
        self.assertTrue(any('2028-R2-21' in row['proposal']['assets_sent'] for row in pick['results']))
        self.assertTrue(all('2028-R1-21' not in row['proposal']['assets_sent'] for row in pick['results']))
        workspace = build_trade_workspace(self.data, 1)
        from services.trade_intelligence import _bounded_adjustment_candidates
        candidates = _bounded_adjustment_candidates(workspace, self.proposal(protected_assets=['2028-R1-21']))
        self.assertTrue(any('2028-R2-21' in {a.asset_id for a in row.assets_sent} for row in candidates))
        self.assertTrue(all('2028-R1-21' not in {a.asset_id for a in row.assets_sent} for row in candidates))

    def test_younger_changes_return_when_supported_without_changing_fixed_target(self):
        result = assist_trade_request(self.data, self.proposal(instruction='make it younger'))
        self.assertTrue(result['results'], result)
        for row in result['results']:
            players = [self.data['players'][i]['age'] for i in row['proposal']['assets_received'] if i in self.data['players']]
            self.assertLess(sum(players) / len(players), 29)
        fixed = assist_trade_request(self.data, self.proposal(instruction='make it younger', origin_workflow='trade_for'))
        for row in fixed['results']:
            self.assertIn('2w', row['proposal']['assets_received'])

    def test_missing_history_survives_with_disclosure_and_bad_counterparty_does_not(self):
        result = evaluate_trade_request(self.data, self.proposal(), projection_reader=self.fixture.reader)['evaluation']
        self.assertIn(classify(result), ('CREDIBLE RECOMMENDATION', 'OPTIONAL / LOWER-RANKED TRADE'))
        self.assertEqual(result['dimensions']['confidence']['assessment'], 'MEDIUM')
        self.assertEqual(result['dimensions']['counterparty_plausibility']['manager_history']['disclosure'], 'Limited manager-history evidence')
        bad = evaluate_trade_request(self.data, self.proposal(sent=['2028-R4-21']), projection_reader=self.fixture.reader)['evaluation']
        self.assertEqual(bad['dimensions']['counterparty_plausibility']['assessment'], 'LOW')
        self.assertNotIn(classify(bad), ('CREDIBLE RECOMMENDATION', 'OPTIONAL / LOWER-RANKED TRADE'))

    def test_unsupported_goal_before_search(self):
        with patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('expensive evaluation')):
            result = self.search('recommended', recommendation_filter='sell_high')
        self.assertEqual(result['result_state'], 'UNSUPPORTED GOAL')
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)

    def test_near_miss_is_assessed_package_with_actual_blocker(self):
        result = self.search('trade_for', asset_id='2w',
            excluded_assets=['1q', '1qb', '1w', '1wb', '2028-R1-21', '2028-R2-21'])
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['near_misses'])
        for row in result['near_misses']:
            self.assertIn('2w', row['proposal']['assets_received'])
            self.assertTrue(row['blockers'])
            self.assertFalse(row['eligible'])
            self.assertIn('evaluation', row)

    def test_impossible_shop_locks_explain_exact_relaxation(self):
        result = assist_trade_request(self.data, self.proposal(instruction='keep this player',
            constraint_asset_id='1q', origin_workflow='shop', origin_asset_id='1q'))
        self.assertEqual(result['state'], 'CONSTRAINT_CONFLICT')
        self.assertEqual(result['blocking_asset_ids'], ['1q'])
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['smallest_optional_relaxation'])

    def test_alternatives_preserve_shop_asset_preview_and_diagnostics_conserve(self):
        payload = self.proposal(sent=['1q', '2028-R2-21'], origin_workflow='shop', origin_asset_id='1q')
        result = create_trade_alternatives(self.data, payload)
        self.assertTrue(result['results'], result)
        self.assertTrue(result['preview_only'])
        for row in result['results']:
            self.assertIn('1q', row['proposal']['assets_sent'])
            self.assertIn('2w', row['proposal']['assets_received'])
        d = result['search_evidence']
        self.assertEqual(d['evaluated'], sum(d[k] for k in ('hard_invalid', 'missing_evidence', 'counterparty_limited', 'strategically_rejected', 'filtered', 'eligible')))

    def test_required_projection_missing_is_honest_not_a_history_veto(self):
        self.fixture.reader = type('Missing', (), {'snapshot': lambda s: None, 'week_snapshot': lambda s, *a, **k: None})()
        with patch('services.trade_intelligence._trade_projection_service', return_value=self.fixture.reader):
            result = self.search('trade_for', asset_id='2w')
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['result_state'], 'MISSING REQUIRED EVIDENCE')
        self.assertGreater(result['search_evidence']['missing_evidence'], 0)

    def test_progressive_search_expands_only_when_first_pass_is_insufficient(self):
        from services import recommended_trade_search
        real = recommended_trade_search.discover
        phases = []
        def first_pass_empty(*args, **kwargs):
            phase = kwargs.get('search_phase', 0)
            phases.append(phase)
            result = real(*args, **kwargs)
            if phase == 0:
                result['theses'] = []
            return result
        with patch('services.recommended_trade_search.discover', side_effect=first_pass_empty):
            result = self.search('recommended')
        self.assertTrue(result['results'])
        self.assertEqual(phases[0], 0)
        self.assertIn(1, phases)
        self.assertLessEqual(result['search_evidence']['evaluated'], 180)

    def test_unknown_counterparty_intent_does_not_erase_concrete_capital_or_production_story(self):
        workspace = build_trade_workspace(self.data, 1)
        workspace['competitive_windows'] = {}
        for team in workspace['teams']:
            team.pop('strategy', None)
        for payload in (self.proposal(sent=['2028-R1-21', '2028-R2-21']),
                        self.proposal(sent=['1q'], received=['2028-R1-22'], strategy='REBUILD')):
            result = evaluate_trade_request(self.data, payload, workspace=workspace,
                projection_reader=self.fixture.reader)['evaluation']
            counter = result['dimensions']['counterparty_plausibility']
            self.assertEqual(counter['manager_strategy']['strategy'], None)
            self.assertEqual(counter['assessment'], 'PLAUSIBLE')
            self.assertIn('COUNTERPARTY_STRATEGY_UNCONFIRMED', counter['reason_codes'])
            self.assertIsNone(counter['acceptance_probability'])

    def test_exact_acquired_pick_fields_survive_search_and_evaluation(self):
        result = self.search('shop', asset_id='2028-R1-21')
        for row in result['results']:
            pick = next(a for a in row['proposal_presentation']['send'] if a['asset_id'] == '2028-R1-21')
            self.assertEqual((pick['year'], pick['round'], pick['original_franchise'], pick['current_owner']), (2028, 1, 21, 1))
            self.assertIn('projected_range', pick)
            self.assertIn('range_confidence', pick)
            production = row['evaluation']['dimensions']['strategic_fit']['active']['production_evidence']
            self.assertEqual(production['weeks_counted_once'], [2, 3, 4, 5])

    def test_unpriced_target_is_missing_evidence_before_any_evaluation(self):
        from dataclasses import replace
        workspace = build_trade_workspace(self.data, 1)
        workspace['pools'][2] = tuple(replace(a, trade_value=None) if a.asset_id == '2w' else a for a in workspace['pools'][2])
        with patch('services.trade_intelligence.build_trade_workspace', return_value=workspace), \
                patch('services.trade_intelligence.evaluate_trade_request', side_effect=AssertionError('unpriced target evaluated')):
            result = self.search('trade_for', asset_id='2w')
        self.assertEqual(result['result_state'], 'MISSING REQUIRED EVIDENCE')
        self.assertEqual(result['search_evidence']['missing_asset_ids'], ['2w'])
        self.assertEqual(result['search_evidence']['full_evaluations'], 0)

    def test_adjustment_funnel_records_instruction_pruning_and_assessment_separately(self):
        result = assist_trade_request(self.data, self.proposal(sent=['1q', '2028-R2-21'], instruction='make it cheaper'))
        d = result['search_evidence']
        self.assertGreater(d['constructions_generated'], d['evaluated'])
        self.assertGreater(d['constructions_pruned'], 0)
        self.assertEqual(d['evaluated'], sum(d[k] for k in ('hard_invalid', 'missing_evidence', 'counterparty_limited', 'strategically_rejected', 'filtered', 'eligible')))

    def test_proposal_locks_remain_hard_independent_of_strategy(self):
        from services.trade_intelligence import TradeInputError
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy), self.assertRaises(TradeInputError) as error:
                evaluate_trade_request(self.data, self.proposal(strategy=strategy, protected_assets=['1q']),
                                       projection_reader=self.fixture.reader)
            self.assertEqual(error.exception.assets, ('1q',))

    def test_positive_average_does_not_hide_a_supported_horizon_cost(self):
        from src.core.trade_intelligence.strategy_dimensions import disclosed_costs
        strategy = {'production_evidence': {'mean_weekly_delta': 2},
            'horizons': {'current_week': {'delta': -3}, 'next_n': {'delta': 6}},
            'future_capital': {}, 'reserve_slot_changes': {}}
        self.assertIn('Supported production declines in current week', disclosed_costs(strategy, 0))
