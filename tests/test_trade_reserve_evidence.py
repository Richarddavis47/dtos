"""Prepared publication -> independent optimized phases -> visible reserve facts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch

from services.trade_decision import decision_context
from services.trade_explanation import render_trade_explanation
from services.trade_lineup_detail import lineup_detail_view, render_lineup_details
from tests import test_trade_lineup_detail as fixtures
from tests import test_reserve_quality as reserve_fixtures


class TradeReserveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.TradeLineupDetailTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def missing_bench(self):
        p = {'id': '1-unknown', 'name': 'Uncovered bench receiver', 'position': 'WR',
             'fantasy_positions': ['WR'], 'status': 'Active'}
        self.f.data['players'][p['id']] = p
        self.f.data['teams'][0]['players'].append(p.copy())
        self.f.f.publish()

    def phase(self, e, side='active', phase='pre', week=8):
        return lineup_detail_view(e)['sides'][side][week]['phases'][phase]['reserve_evidence']

    def test_partial_subtotal_and_independent_partner_effect_reach_primary_summary(self):
        self.missing_bench()
        e = self.f.evaluate()
        view = decision_context(e)
        self.assertIn('10.00 points (known subtotal only, 1 covered reserve slots)', view['your_side_summary'])
        self.assertIn('Uncovered bench receiver: no numerical projection', view['your_side_summary'])
        self.assertIn('full reserve change is unknown', view['your_side_summary'])
        self.assertIn('before 10.00 points (supported', view['their_side_summary'])
        self.assertIn('after 20.00 points (supported', view['their_side_summary'])
        self.assertIn('week 8 reserve-production change: +10.00', view['their_side_summary'])
        self.assertNotIn('week 8 reserve-production change:', view['your_side_summary'])
        self.assertEqual(self.phase(e)['known_subtotal'], 10)
        self.assertIsNone(self.phase(e)['points'])
        self.assertIn('known subtotal only', e['explanation_html'])

    def test_missing_projection_and_verified_zero_are_distinct(self):
        self.f.f.feed = [r for r in self.f.f.feed if r['player_id'] != '1-0']
        self.f.f.publish()
        missing = self.f.evaluate()
        self.assertIsNone(self.phase(missing)['points'])
        self.assertIn('Example 1-0: no numerical projection', ' '.join(self.phase(missing)['reasons']))
        self.assertNotIn('0.00 points (supported', decision_context(missing)['your_side_summary'])
        self.f.f.feed.append({'player_id': '1-0', 'season': 2026, 'week': 8,
            'player': {'position': 'QB', 'fantasy_positions': ['QB']}, 'stats': {'pass_yd': 0}})
        self.f.f.publish()
        zero = self.f.evaluate()
        self.assertEqual(self.phase(zero)['points'], 0)
        self.assertIn('0.00 points (supported', decision_context(zero)['your_side_summary'])

    def test_supported_empty_pool_is_zero_without_inventing_a_second_lineup(self):
        self.f.data['teams'][0]['players'] = [p for p in self.f.data['teams'][0]['players'] if p['id'] != '1-0']
        self.f.f.publish()
        e = self.f.evaluate()
        phase = self.phase(e)
        self.assertEqual((phase['points'], phase['candidate_count'], phase['supported_slots']), (0, 0, 0))
        self.assertEqual(phase['state'], 'supported')
        self.assertIn('not a second required starting lineup', render_lineup_details(e))

    def test_wrong_reserve_snapshot_withholds_only_affected_phase(self):
        e = self.f.evaluate()
        e['multi_horizon_impact']['sides']['active']['weekly'][8]['pre']['reserve_capacity']['qualification']['projection_snapshot_id'] = 'foreign'
        self.assertIsNone(self.phase(e)['known_subtotal'])
        self.assertEqual(self.phase(e, phase='post')['state'], 'supported')
        self.assertEqual(self.phase(e, side='partner')['state'], 'supported')
        summary = decision_context(e)['your_side_summary']
        self.assertIn('before unknown; after 10.00 points', summary)
        self.assertNotIn('week 8 reserve-production change:', summary)

    def test_wrong_generation_scoring_and_owner_never_publish_reserve_numbers(self):
        for kind in ('projection_generation', 'scoring_profile_id', 'ownership'):
            with self.subTest(kind=kind):
                e = self.f.evaluate()
                if kind == 'ownership':
                    e['lineup_detail_context']['rosters']['active']['pre'].remove('1-0')
                else:
                    e['lineup_detail_context'][kind] = 'foreign'
                self.assertIsNone(self.phase(e)['known_subtotal'])
                self.assertEqual(self.phase(e)['state'], 'unavailable')

    def test_out_and_ir_are_not_usable_missing_reserves(self):
        for status in ('Out', 'IR'):
            with self.subTest(status=status):
                self.f.data['players']['1-0']['status'] = status
                self.f.data['teams'][0]['players'][0]['status'] = status
                self.f.f.feed = [r for r in self.f.f.feed if r['player_id'] != '1-0']
                self.f.f.publish()
                e = self.f.evaluate()
                self.assertEqual(self.phase(e)['points'], 0)
                self.assertEqual(self.phase(e)['missing_player_count'], 0)
                self.assertIn('Excluded from usable cover', render_lineup_details(e))

    def test_superflex_reserves_use_its_own_slots_and_scoring(self):
        self.f.f.test_superflex_without_dedicated_te_preserves_legal_scoring()
        e = self.f.evaluate()
        view = lineup_detail_view(e)
        for side in ('active', 'partner'):
            for phase in ('pre', 'post'):
                p = view['sides'][side][8]['phases'][phase]
                self.assertEqual(p['reserve_evidence']['state'], 'supported')
                self.assertAlmostEqual(sum(r['projected_points'] for r in p['reserves']), p['reserve_evidence']['points'])
                self.assertIn('SUPER_FLEX', [r['slot'] for r in p['entries']])
                self.assertNotIn('TE', [r['slot'] for r in p['entries']])
                self.assertEqual(p['reserve_evidence']['points'], 0)

    def test_missing_irrelevant_k_def_projections_do_not_hide_proven_empty_superflex_cover(self):
        self.f.f.test_superflex_without_dedicated_te_preserves_legal_scoring()
        self.f.f.feed = [r for r in self.f.f.feed if r['player_id'] not in {'1-8', '1-9'}]
        self.f.f.publish()
        e = self.f.evaluate()
        self.assertEqual(self.phase(e)['points'], 0)
        self.assertEqual(self.phase(e)['candidate_count'], 0)
        self.assertEqual(self.phase(e)['missing_player_count'], 0)
        self.assertIn('No eligible starting slot', render_lineup_details(e))

    def test_unknown_eligibility_is_not_removed_to_make_cover_appear_complete(self):
        self.missing_bench()
        self.f.data['players']['1-unknown'].update(position=None, fantasy_positions=[])
        self.f.data['teams'][0]['players'][-1].update(position=None, fantasy_positions=[])
        self.f.f.publish()
        e = self.f.evaluate()
        self.assertIsNone(self.phase(e)['points'])
        self.assertNotEqual(self.phase(e)['state'], 'supported')

    def test_missing_starter_preserves_known_cover_but_withholds_full_effect(self):
        self.f.f.feed = [r for r in self.f.f.feed if r['player_id'] != '1-9']
        self.f.f.publish()
        e = self.f.evaluate()
        reserve = self.phase(e)
        self.assertEqual(reserve['known_subtotal'], 10)
        self.assertIsNone(reserve['points'])
        self.assertIn('starting lineup is incomplete', ' '.join(reserve['reasons']))
        self.assertIn('full reserve change is unknown', decision_context(e)['your_side_summary'])
        self.assertEqual(self.phase(e, side='partner')['state'], 'supported')

    def test_missing_identity_is_never_replaced_with_another_player(self):
        self.missing_bench()
        e = self.f.evaluate()
        e['lineup_detail_context']['identities']['1-unknown'] = None
        html = render_trade_explanation(e, league_id='one-qb')
        self.assertIn('Player identity not resolved: no numerical projection', html)
        self.assertNotIn('1-unknown:', html)

    def test_aging_retains_conditional_qualification(self):
        e = self.f.evaluate()
        old = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        for phase in ('pre', 'post'):
            q = e['multi_horizon_impact']['sides']['active']['weekly'][8][phase]['reserve_capacity']['qualification']
            q.update(source_timestamps=[old], conclusion_state='current')
        self.assertEqual(self.phase(e)['qualification'], 'provisional')
        self.assertIn('Conditional week 8 reserve-production change', decision_context(e)['your_side_summary'])
        self.assertIn('Original projection observations are not confirmed Fresh', render_lineup_details(e))

    def test_later_week_missing_does_not_erase_current_reserves(self):
        e = self.f.evaluate()
        summary = decision_context(e)['their_side_summary']
        self.assertIn('weeks 9, 10', summary)
        self.assertIn('week 8 reserve-production change: +10.00', summary)
        self.assertNotIn('week 9 reserve-production change:', summary)

    def test_other_supported_week_retains_its_own_reserve_projection(self):
        from src.core.intelligence.team_strength import prepare_for_data
        other = deepcopy(self.f.f.feed)
        for row in other:
            row['week'] = 9
            if row['player_id'] == '1-0':
                row['stats']['pass_yd'] = 350
        self.f.f.service.publish_horizon({8: self.f.f.feed, 9: other}, data=self.f.data,
            league_id='one-qb', season=2026, current_week=8)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.f.f.service, self.f.data)
        e = self.f.evaluate()
        self.assertEqual(self.phase(e, week=8)['points'], 10)
        self.assertEqual(self.phase(e, week=9)['points'], 14)
        self.assertIsNone(self.phase(e, week=10)['points'])
        html = render_lineup_details(e)
        self.assertIn('Reserve production: 14 points', html)
        self.assertIn('Other weekly reserve effects', decision_context(e)['your_side_summary'])

    def test_rendering_does_not_solve_refresh_acquire_or_mutate(self):
        self.missing_bench()
        e = self.f.evaluate()
        before = deepcopy(e)
        with patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('no solve')), \
             patch('services.sleeper.sleeper_get', side_effect=AssertionError('no source work')):
            html = render_trade_explanation(e, league_id='one-qb')
            self.assertEqual(self.phase(e), self.phase(json.loads(json.dumps(e))))
        self.assertIn('not your submitted Sleeper starters', html)
        self.assertEqual(e, before)
        self.assertEqual(self.f.data['teams'][0]['starters'], ['0'])

    def test_real_qualified_consolidation_keeps_its_reserve_cost_and_verdict(self):
        f = reserve_fixtures.ReserveQualityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.fixture.points.update(a=20, b=14, e=13, c=28, d=3, f=4)
        f.fixture.prices(a=125, b=125, c=250)
        f.fixture.publish()
        for strategy in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(strategy=strategy):
                e = f.evaluate(sent=('a', 'b'), received=('c',), strategy=strategy)
                self.assertEqual(e['recommendation'], 'WORTH PURSUING')
                self.assertEqual(e['lineup_impact']['active']['delta'], 8)
                self.assertEqual(f.quality(e)['mean_weekly_delta'], -1)
                self.assertIn('reserve-production change: -1.00', decision_context(e)['your_side_summary'])


if __name__ == '__main__':
    unittest.main()
