"""Real compatible publications -> completed Trade DTO -> auditable slot views."""
from collections import Counter
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from services.trade_intelligence import evaluate_trade_request
from services.trade_lineup_detail import lineup_detail_view, render_lineup_details, render_lineup_risks
from services.trade_search_policy import SearchFunnel, classify
from tests import test_multileague_projection_compatibility as fixtures


class TradeLineupDetailTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.MultiLeagueProjectionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.data = self.f.data
        self.data['market_data'] = {'providers': {'FantasyCalc': {
            pid: {'value': 3000, 'confidence': 90}
            for pid, p in self.data['players'].items() if p['position'] not in {'K', 'DEF'}}}}
        self.f.publish()

    def evaluate(self, sent=None, received=None):
        return evaluate_trade_request(self.data, {'active_roster_id': 1, 'partner_roster_id': 2,
            'assets_sent': sent or ['1-10'], 'assets_received': received or ['2-0'],
            'workflow': 'create', 'strategy': 'RETOOL'}, projection_reader=self.f.service)['evaluation']

    def test_full_source_to_slot_sum_and_independent_post_optimization(self):
        next(r for r in self.f.feed if r['player_id'] == '2-0')['stats'] = {'pass_yd': 125}
        self.f.publish()
        before = deepcopy(self.data)
        e = self.evaluate()
        view = lineup_detail_view(e)
        for side in ('active', 'partner'):
            for phase in ('pre', 'post'):
                detail = view['sides'][side][8]['phases'][phase]
                self.assertEqual(detail['state'], 'complete')
                self.assertEqual(Counter(p['slot'] for p in detail['entries']),
                                 Counter(self.data['league']['roster_positions'][:10]))
                self.assertAlmostEqual(sum(p['projected_points'] for p in detail['entries']), detail['total'])
                self.assertTrue(all(p['name'].startswith('Example ') for p in detail['entries']))
        # The outgoing starting QB is independently replaced by retained bench QB,
        # not mechanically by the lower-projected incoming player.
        active = view['sides']['active'][8]['phases']
        self.assertEqual(next(p['asset_id'] for p in active['pre']['entries'] if p['slot'] == 'QB'), '1-10')
        self.assertEqual(next(p['asset_id'] for p in active['post']['entries'] if p['slot'] == 'QB'), '1-0')
        self.assertEqual(self.data, before)

    def test_presentation_is_pure_and_json_reload_preserves_exact_context(self):
        e = self.evaluate()
        before = deepcopy(e)
        with patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('No render solving')), \
             patch('services.sleeper.sleeper_get', side_effect=AssertionError('No render source calls')):
            html = render_lineup_details(e)
            self.assertEqual(lineup_detail_view(e), lineup_detail_view(json.loads(json.dumps(e))))
        self.assertIn('not your submitted Sleeper starters', html)
        self.assertIn('K</th>', html)
        self.assertIn('DEF</th>', html)
        self.assertEqual(e, before)

    def test_wrong_scope_generation_snapshot_scoring_week_and_sum_withhold_detail(self):
        original = self.evaluate()
        cases = [lambda e: e['lineup_detail_context'].update(league_id='foreign'),
                 lambda e: e['lineup_detail_context'].update(season=2025),
                 lambda e: e['lineup_detail_context'].update(projection_generation='foreign'),
                 lambda e: e['lineup_detail_context']['weeks']['8'].update(scoring_profile_id='foreign'),
                 lambda e: e['lineup_detail_context']['weeks']['8'].update(week=9),
                 lambda e: e['multi_horizon_impact']['sides']['active']['weekly'][8]['pre'].update(projection_snapshot_id='foreign'),
                 lambda e: e['multi_horizon_impact']['sides']['active']['weekly'][8]['pre'].update(scoring_profile_id='foreign'),
                 lambda e: e['multi_horizon_impact']['sides']['active']['weekly'][8]['pre']['optimal']['entries'][0].update(projected_points=999)]
        for mutate in cases:
            with self.subTest(mutation=cases.index(mutate)):
                e = deepcopy(original)
                mutate(e)
                detail = lineup_detail_view(e)['sides']['active'][8]['phases']['pre']
                self.assertEqual(detail['state'], 'unavailable')
                self.assertEqual(detail['entries'], [])
        # An independently valid other side survives a phase-local mismatch.
        self.assertEqual(lineup_detail_view(e)['sides']['partner'][8]['phases']['post']['state'], 'complete')

    def test_duplicate_player_illegal_slot_and_foreign_roster_are_rejected(self):
        original = self.evaluate()
        for field, value in [('slot', 'SUPER_FLEX'), ('asset_id', '12-0'), ('position', 'QB')]:
            e = deepcopy(original)
            entry = next(p for p in e['multi_horizon_impact']['sides']['active']['weekly'][8]['pre']['optimal']['entries'] if p['slot'] == 'DEF')
            entry[field] = value
            self.assertEqual(lineup_detail_view(e)['sides']['active'][8]['phases']['pre']['state'], 'unavailable')

    def test_missing_def_is_partial_and_explicit_zero_is_complete(self):
        self.f.feed = [r for r in self.f.feed if r['player_id'] != '1-9']
        self.f.publish()
        e = self.evaluate()
        p = lineup_detail_view(e)['sides']['active'][8]['phases']['pre']
        self.assertEqual(p['state'], 'partial')
        self.assertIsNone(p['total'])
        self.assertIn('DEF', p['unsupported_slots'])
        self.f.feed.append({'player_id': '1-9', 'season': 2026, 'week': 8,
                            'player': {'position': 'DEF'}, 'stats': {'sack': 0, 'int': 0}})
        self.f.publish()
        e = self.evaluate()
        p = lineup_detail_view(e)['sides']['active'][8]['phases']['pre']
        self.assertEqual(p['state'], 'complete')
        self.assertEqual(next(p['projected_points'] for p in p['entries'] if p['slot'] == 'DEF'), 0)

    def test_unresolved_identity_is_never_replaced_with_another_player(self):
        self.data['players']['1-9'].pop('name')
        self.data['teams'][0]['players'][9].pop('name')
        e = self.evaluate()
        html = render_lineup_details(e)
        p = lineup_detail_view(e)['sides']['active'][8]['phases']['pre']
        self.assertEqual(next(p['name'] for p in p['entries'] if p['slot'] == 'DEF'), 'Player identity not resolved')
        self.assertIn('Player identity not resolved', html)

    def test_out_ir_unknown_and_reserve_gaps_remain_week_specific(self):
        # Week 8 Out/IR is not an injury-recovery forecast for week 9.
        for pid, status in [('1-0', 'Out'), ('1-6', 'IR')]:
            self.data['players'][pid]['status'] = status
            next(p for p in self.data['teams'][0]['players'] if p['id'] == pid)['status'] = status
        self.data['teams'][0]['players'][6]['roster_slot'] = 'IR'
        self.data['players']['1-6']['roster_slot'] = 'IR'
        self.f.publish()
        e = self.evaluate(sent=['1-10'], received=['2-0'])
        p = lineup_detail_view(e)['sides']['active'][8]['phases']['pre']
        self.assertNotIn('1-0', {p['asset_id'] for p in p['entries']})
        self.assertNotIn('1-6', {p['asset_id'] for p in p['reserves']})
        self.assertTrue(any(w['player_id'] == '1-0' and 'OUT' in w['reason'] for w in p['warnings']))
        self.assertTrue(any(w['player_id'] == '1-6' and 'IR' in w['reason'] for w in p['warnings']))
        e['lineup_detail_context']['weeks']['8']['players']['2-0']['availability'] = 'unknown'
        risks = render_lineup_risks(e, lineup_detail_view(e))
        self.assertIn('Example 2-0', risks)
        self.assertIn('not confirmed', risks)

    def test_full_superflex_configuration_uses_its_own_slots_and_bonus_scoring(self):
        self.f.test_superflex_without_dedicated_te_preserves_legal_scoring()
        e = self.evaluate()
        for side in ('active', 'partner'):
            for phase in ('pre', 'post'):
                p = lineup_detail_view(e)['sides'][side][8]['phases'][phase]
                self.assertEqual(p['state'], 'complete')
                slots = [p['slot'] for p in p['entries']]
                self.assertIn('SUPER_FLEX', slots)
                self.assertNotIn('TE', slots)
                self.assertEqual(len(slots), 10)

    def test_precision_never_changes_canonical_totals_or_trade_verdict(self):
        e = self.evaluate()
        before = deepcopy(e)
        from services.trade_explanation import render_trade_explanation
        html = render_trade_explanation(e, league_id='one-qb')
        self.assertEqual(e, before)
        self.assertIn('115', html)
        # Historical observation formatting is a display control, not a replay.
        from src.ui.intelligence_presentation import manager_points
        self.assertEqual(manager_points(155.56980000000001), '155.57')
        self.assertEqual(manager_points(155.8992), '155.9')
        self.assertEqual(manager_points(161.2492), '161.25')
        from services.trade_lineup_evidence import weekly_total_display
        self.assertEqual(weekly_total_display(155.56980000000001), '155.5698')
        self.assertEqual(weekly_total_display(27.335), '27.335')
        self.assertEqual(weekly_total_display(0), '0')
        self.assertEqual(weekly_total_display(None), 'Unavailable')
        from services.trade_lineup_evidence import diagnostic_summary_display
        raw = {'pre_optimal_points': 155.56980000000001, 'post_optimal_points': 161.2492,
               'summary': 'Package optimal lineup: 155.56980000000001 → 161.2492 Sleeper-projected points. Recorded qualifications.'}
        original = deepcopy(raw)
        self.assertEqual(diagnostic_summary_display(raw), 'Package optimal lineup: 155.57 → 161.25 Sleeper-projected points. Recorded qualifications.')
        self.assertEqual(raw, original)

    def test_cause_counts_have_an_explicit_overlapping_denominator(self):
        self.f.feed = [r for r in self.f.feed if r['player_id'] != '2-9']
        self.f.publish()
        e = self.evaluate(sent=['1-0'], received=['2-10'])
        self.assertEqual(classify(e), 'MISSING REQUIRED EVIDENCE')
        funnel = SearchFunnel(180)
        funnel.assessed({'evaluation': e, 'proposal': {}})
        report = funnel.result(0)['evidence_limitations']
        self.assertEqual(report['assessments'], 1)
        self.assertGreaterEqual(report['blocking_requirement_counts']['current_week_lineup'], 1)
        self.assertEqual(report['unknown_cause_count'], 0)
        self.assertIn('categories overlap', report['meaning'])
        self.assertIn('reserve_depth', report['contextual_qualification_counts'])
        self.assertTrue(any('DEF' in r.get('unsupported_slots', [])
                            for r in e['evidence_limitations']['blocking_requirements']))

    def test_future_week_detail_has_its_own_points_and_missing_phase_is_independent(self):
        future = deepcopy(self.f.feed)
        for row in future:
            row['week'] = 9
            if row['player_id'] == '1-10':
                row['stats'] = {'pass_yd': 750}
        self.f.service.publish_horizon({8: self.f.feed, 9: future}, data=self.data,
                                      league_id='one-qb', season=2026, current_week=8)
        from src.core.intelligence.team_strength import prepare_for_data
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.f.service, self.data)
        e = self.evaluate()
        view = lineup_detail_view(e)
        self.assertEqual(view['sides']['active'][8]['phases']['pre']['total'], 115)
        self.assertEqual(view['sides']['active'][9]['phases']['pre']['total'], 125)
        self.assertNotEqual(view['sides']['active'][8]['projection_snapshot_id'], view['sides']['active'][9]['projection_snapshot_id'])
        e['multi_horizon_impact']['sides']['active']['weekly'][8]['post']['projection_snapshot_id'] = 'foreign'
        view = lineup_detail_view(e)
        self.assertEqual(view['sides']['active'][8]['phases']['pre']['state'], 'complete')
        self.assertEqual(view['sides']['active'][8]['phases']['post']['state'], 'unavailable')
        self.assertEqual(view['sides']['active'][9]['phases']['post']['state'], 'complete')

    def test_reported_totals_in_disposable_fixture_do_not_turn_user_gain_into_endorsement(self):
        # A numerical control matching reported totals, NOT the original private
        # Granite publication or its historical injury/Market observations.
        updates = {'1-5': {'rec_yd': 250, 'rec': 5},
                   '1-4': {'rec_yd': 308.992, 'rec': 5},
                   '2-3': {'rec_yd': 203.5, 'rec': 5},
                   '2-5': {'rec_yd': 174.16, 'rec': 5},
                   '2-10': {'pass_yd': 305.25}}
        self.data['league']['sport'] = 'nfl'
        self.data['league']['settings'].update(last_scored_leg=7, playoff_type=0)
        for row in self.f.feed:
            if row['player_id'] in updates:
                row['stats'] = updates[row['player_id']]
        for pid, name in [('1-10', 'Daniel Jones'), ('1-6', 'Sean Tucker'),
                          ('2-3', 'A.J. Brown'), ('2-6', 'Braelon Allen')]:
            self.data['players'][pid]['name'] = name
            next(p for t in self.data['teams'] for p in t['players'] if p['id'] == pid)['name'] = name
        self.data['players']['2-3']['status'] = 'Questionable'
        next(p for p in self.data['teams'][1]['players'] if p['id'] == '2-3')['status'] = 'Questionable'
        self.data['teams'][0]['picks_owned'] = [{'year': 2029, 'round': 1, 'original_roster_id': 1, 'current_owner_id': 1}]
        extra = dict(id='2-extra-rb', name='Fixture reserve running back', position='RB',
                     fantasy_positions=['RB'], status='Active', team='BUF', roster_slot='Bench')
        self.data['teams'][1]['players'].append(extra)
        self.data['players'][extra['id']] = extra.copy()
        self.f.feed.append({'player_id': extra['id'], 'season': 2026, 'week': 8,
                            'player': {'position': 'RB'}, 'stats': {'rush_yd': 100}})
        self.data['market_data']['providers']['FantasyCalc'][extra['id']] = {'value': 3000, 'confidence': 90}
        from tests import test_capital_strategy_reconciliation as capital
        helper = capital.CapitalStrategyTests()
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        quote = deepcopy(helper.data['market_data']['pick_quotes']['FantasyCalc'][0])
        quote.update(year=2029, value=12000)
        quote['normalization_reference'].update(raw_value=12000, normalized_value=1000)
        self.data['market_data']['pick_quotes'] = {'FantasyCalc': [quote]}
        horizon = {w: [dict(r, week=w) for r in self.f.feed] for w in range(8, 18)}
        self.f.service.publish_horizon(horizon, data=self.data, league_id='one-qb', season=2026, current_week=8)
        from src.core.intelligence.team_strength import prepare_for_data
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(self.f.service, self.data)
        e = self.evaluate(sent=['1-10', '1-6', '2029-R1-1'], received=['2-3', '2-6'])
        view = lineup_detail_view(e)
        for side, before, after in [('active', 155.8992, 161.2492), ('partner', 129.976, 122.416)]:
            self.assertAlmostEqual(view['sides'][side][8]['phases']['pre']['total'], before)
            self.assertAlmostEqual(view['sides'][side][8]['phases']['post']['total'], after)
        self.assertFalse(e['generated_trade_eligible'])
        self.assertIn(e['recommendation'], ('REJECT', 'NOT WORTH IT'))
        self.assertIn('2029-R1-1', e['provenance']['inputs']['assets_sent'])
        self.assertIn('A.J. Brown', render_lineup_risks(e, view))

    def test_discovery_materializes_only_returned_lineups_without_re_evaluation(self):
        from tests import test_trade_discovery_repair as discovery
        from services.trade_intelligence import generate_trade_workflow
        from services.trade_lineup_detail import bind_lineup_details
        f = discovery.DiscoveryRepairTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        with patch('services.trade_lineup_detail.bind_lineup_details', wraps=bind_lineup_details) as bind:
            response = generate_trade_workflow(f.data, {'active_roster_id': 1, 'workflow': 'recommended', 'strategy': 'WIN NOW'})
        rows = [r for key in ('results', 'near_misses', 'exploratory_results') for r in response.get(key) or []]
        # Related variants are returned assessments too, not extra search work.
        pending, seen = list(rows), set()
        rows = []
        while pending:
            row = pending.pop()
            if id(row) in seen:
                continue
            seen.add(id(row))
            rows.append(row)
            pending.extend(row.get('variants') or [])
        self.assertGreater(len(rows), 0)
        self.assertGreater(bind.call_count, 0)
        self.assertLessEqual(bind.call_count, len(rows))
        self.assertLess(bind.call_count, response['search_evidence']['full_evaluations'])
        for row in rows:
            self.assertIn('lineup_detail_context', row['evaluation'])
            self.assertIn('Before and after', row['evaluation']['explanation_html'])

    def test_unbound_retained_assessment_is_not_given_fabricated_provenance(self):
        from services.trade_intelligence import _with_lineup_details
        row = {'proposal': {'active_roster_id': 1, 'partner_roster_id': 2,
                           'assets_sent': ['1-0'], 'assets_received': ['2-0']},
               'evaluation': {'recommendation': 'FAIR / OPTIONAL'}}
        before = deepcopy(row)
        with patch('services.trade_lineup_detail.bind_lineup_details', side_effect=AssertionError('No binding without provenance')):
            self.assertEqual(_with_lineup_details(self.data, {'results': [row]}, self.f.service), {'results': [before]})


if __name__ == '__main__':
    unittest.main()
