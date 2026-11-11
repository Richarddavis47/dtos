"""Prepared-only Front Office composition and scope controls."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from tests import test_active_roster_grading as fixtures


class FrontOfficeBriefTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ActiveRosterGradingTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_cache_miss_has_no_factory_and_no_inferred_direction(self):
        from services.front_office_brief import prepared_evidence, select_insights
        from src.core.intelligence.roster_diagnostics import diagnostic_store
        # Establish the asserted cold-cache premise even after prepared-HQ tests.
        diagnostic_store.clear()
        with patch('services.front_office_brief.intelligence_orchestrator', self.f.engine), \
             patch.object(self.f.engine, 'analyze', side_effect=AssertionError('factory')), \
             patch('src.core.intelligence.roster_diagnostics._compute', side_effect=AssertionError('solver')):
            facts = prepared_evidence(self.f.data, 1, '')
        self.assertIsNone(facts['assessment'])
        items = select_insights(facts, [], [])
        self.assertEqual([i['family'] for i in items], ['goal', 'preparation'])
        self.assertIn('unchanged', items[0]['drawback'])

    def test_saved_goal_with_cold_evidence_has_preparation_action_without_a_factory(self):
        from services.front_office_brief import prepared_evidence, select_insights
        from src.ui.front_office_brief import cards
        for goal in ('WIN NOW', 'RETOOL', 'REBUILD'):
            with self.subTest(goal=goal), \
                 patch('services.front_office_brief.intelligence_orchestrator', self.f.engine), \
                 patch.object(self.f.engine.cache, 'peek', return_value=None), \
                 patch.object(self.f.engine, 'analyze', side_effect=AssertionError('factory')), \
                 patch('services.front_office_brief.prepared_diagnostics', return_value=None), \
                 patch('services.front_office_brief.compatible_profile', return_value=None), \
                 patch('services.front_office_brief.prepared_need', side_effect=AssertionError('missing diagnostic')):
                facts = prepared_evidence(self.f.data, 1, goal)
                items = select_insights(facts, [], [])
            self.assertEqual([item['family'] for item in items], ['preparation'])
            self.assertEqual(items[0]['href'], '/teams/1')
            self.assertEqual(facts['strategy'], goal)
            rendered = cards(items)
            self.assertIn('not evidence of roster weakness', rendered)
            self.assertIn('does not start a trade search or change your goal', rendered)
            self.assertNotIn('Choose your goal', rendered)

    def test_existing_qualified_need_leads_and_hands_off_only_its_current_position(self):
        from services.front_office_brief import select_insights
        from src.ui.front_office_brief import cards
        facts = self.prepared('WIN NOW')
        def diagnostic(**flags):
            return dict(evidence={'calculation_supported': True}, conclusion_state='current',
                        base_reason='Supported current legal-lineup evidence.', **flags)
        facts = {**facts, 'diagnostics': {'teams': {'1': {'positions': {
            'QB': diagnostic(resilience_need=True),
            'WR': diagnostic(starter_need=True, quality_depth_need=True),
        }}}}, 'trade_need': {'position': 'WR', 'kind': 'starter',
                           'href': '/trades/recommended?front_office=1&team_need=exact-current-fingerprint'}}
        before = deepcopy(facts)
        items = select_insights(facts, [], [])
        self.assertEqual(items[0]['key'], 'position:WR')
        self.assertIn('improve the lineup', items[0]['title'])
        self.assertEqual(items[0]['action'], 'Explore WR trades')
        self.assertEqual(items[0]['href'], facts['trade_need']['href'])
        qb = next(item for item in items if item['key'] == 'position:QB')
        self.assertEqual(qb['href'], '/teams/1#positional-depth')
        self.assertIn('Cost and uncertainty', cards(items))
        self.assertEqual(facts, before)
        # A presentation hint cannot promote provisional findings to a search action.
        facts['diagnostics']['teams']['1']['positions']['WR']['conclusion_state'] = 'provisional'
        items = select_insights(facts, [], [])
        wr = next(item for item in items if item['key'] == 'position:WR')
        self.assertEqual(items[0]['key'], 'position:QB')
        self.assertEqual(wr['href'], '/teams/1#positional-depth')
        self.assertTrue(wr['title'].startswith('Provisional:'))

    def test_missing_assessment_keeps_independently_prepared_diagnostics(self):
        from services.front_office_brief import select_insights
        facts = self.prepared('REBUILD')
        facts['assessment'] = None
        items = select_insights(facts, [], [])
        self.assertTrue(any(item['family'] in {'need', 'depth'} for item in items))
        self.assertFalse(any(item['family'] == 'preparation' for item in items))

    def test_exact_goal_cache_hit_and_source_transition_miss(self):
        from services.front_office_brief import prepared_evidence
        prepared = self.f.engine.analyze(self.f.data, 1, {'strategy':'REBUILD'}, include_trade_opportunities=False)
        with patch('services.front_office_brief.intelligence_orchestrator', self.f.engine):
            self.assertIs(prepared_evidence(self.f.data, 1, 'REBUILD')['assessment'], prepared.team_assessment)
            self.assertIsNone(prepared_evidence(self.f.data, 1, '')['assessment'])
            self.assertIsNone(prepared_evidence(self.f.data, 2, 'REBUILD')['assessment'])
            self.f.snapshot['projection_snapshot_id'] = 'replacement'
            self.assertIsNone(prepared_evidence(self.f.data, 1, 'REBUILD')['assessment'])

    def prepared(self, goal='WIN NOW'):
        from services.front_office_brief import prepared_evidence
        self.f.engine.analyze(self.f.data, 1, {'strategy':goal}, include_trade_opportunities=False)
        with patch('services.front_office_brief.intelligence_orchestrator', self.f.engine):
            return prepared_evidence(self.f.data, 1, goal)

    def test_equal_starters_different_reserve_quality(self):
        from services.front_office_brief import select_insights
        from src.core.trade_intelligence.lineup import optimal_legal_lineup
        selected = {p.asset_id for p in optimal_legal_lineup(
            [dict(p, projected_points=40) for p in self.f.data['teams'][0]['players']], self.f.data['league']['roster_positions']).entries}
        results = []
        for depth in (1,25):
            for player in self.f.data['teams'][0]['players']:
                self.f.snapshot['players'][player['id']]['weekly_projected_points'] = 40 if player['id'] in selected else depth
            facts = self.prepared()
            results.append((facts['assessment'].roster_evidence.optimal_lineup_projection, select_insights(facts, [], [])))
        self.assertEqual(results[0][0], results[1][0])
        self.assertNotEqual(results[0][1], results[1][1])
        self.assertTrue(any('replacement' in x['title'] for x in results[0][1]))
        self.assertNotIn('No material downside', str(results))

    def test_rebuild_exact_owned_firsts_before_current_production(self):
        from services.front_office_brief import select_insights
        self.f.data['teams'][0]['picks_owned'] = [dict(year=2029, round=1, original_roster_id=2, current_owner_id=1)]
        facts = self.prepared('REBUILD')
        before = deepcopy(self.f.data)
        items = select_insights(facts, [], [])
        self.assertEqual(items[0]['family'], 'capital')
        self.assertIn('2029', items[0]['reason'])
        self.assertIn('owned by your team', items[0]['reason'])
        self.assertNotIn('owner 1', items[0]['reason'])
        self.assertIn('original 2', ' '.join(items[0]['details']))
        self.assertIn('owner 1', ' '.join(items[0]['details']))
        self.assertIn('Unknown ranges', items[0]['drawback'])
        self.assertEqual(self.f.data, before)

    def test_optional_exploratory_missing_price_and_ineligible_not_endorsed(self):
        from services.front_office_brief import select_insights
        facts = self.prepared()
        base = dict(home_offer='token', home_assessment_strategy='WIN NOW', evaluation=dict(
            recommendation='WORTH PURSUING', generated_trade_eligible=True,
            market_evidence={'availability':'full'}, why_you_would_do_it='Supported improvement', major_drawback='Future cost'))
        variants = [dict(exploration=True), dict(evaluation={**base['evaluation'], 'generated_trade_eligible':False}),
                    dict(evaluation={**base['evaluation'], 'recommendation':'FAIR / OPTIONAL'}),
                    dict(evaluation={**base['evaluation'], 'recommendation':'REJECT'}),
                    dict(evaluation={**base['evaluation'], 'market_evidence':{'availability':'partial'}}),
                    dict(home_assessment_strategy='REBUILD')]
        for change in variants:
            with self.subTest(change=change):
                self.assertFalse(any(i['family']=='offer' for i in select_insights(facts, [], [{**base, **change}])))
        self.assertTrue(any(i['family']=='offer' for i in select_insights(facts, [], [base])))

    def test_missing_scoring_and_projection_zero_do_not_become_depth_claims(self):
        from services.front_office_brief import select_insights
        for p in self.f.snapshot['players'].values():
            p['weekly_projected_points'] = 0
        facts = self.prepared('RETOOL')
        self.assertEqual(facts['assessment'].roster_evidence.optimal_lineup_projection, 0)
        self.f.data['league']['scoring_settings'] = {}
        facts = self.prepared('RETOOL')
        self.assertFalse(any(i['family'] in {'need','depth'} for i in select_insights(facts, [], [])))

    def test_no_goal_does_not_infer_direction_and_selection_is_bounded(self):
        from services.front_office_brief import select_insights
        facts = self.prepared('')
        items = select_insights(facts, [], [])
        self.assertLessEqual(len(items), 4)
        self.assertTrue(any(i['family']=='goal' for i in items))
        self.assertEqual(items, select_insights(facts, [], []))

    def test_superflex_qb3_retains_value_and_no_automatic_shop_action(self):
        from tests import test_reserve_quality as reserve
        from services.front_office_brief import prepared_evidence, select_insights
        f = reserve.ReserveQualityTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.data['league']['roster_positions'] = ['QB','SUPER_FLEX'] + ['BN']*6
        f.fixture.points.update(a=30,b=29,e=28,c=27,d=26,f=25)
        f.fixture.publish()
        with patch('src.core.projection_intelligence.projection_service.snapshot', f.fixture.reader.snapshot), \
             patch('services.front_office_brief.intelligence_orchestrator', self.f.engine):
            self.f.engine.analyze(f.data,1,{'strategy':'WIN NOW'},include_trade_opportunities=False)
            facts = prepared_evidence(f.data,1,'WIN NOW')
        items = select_insights(facts,[],[])
        qb = next(i for i in items if 'position:QB' in i['issues'])
        self.assertIn('28', qb['reason'])
        self.assertIn('not automatically surplus', qb['drawback'])
        self.assertEqual(facts['assessment'].roster_evidence.optimal_lineup_projection,59)
        self.assertNotIn('/trades/shop', qb['href'])

    def test_independent_needs_merge_with_evaluated_offer_and_family_order_is_stable(self):
        from services.front_office_brief import select_insights
        facts = self.prepared('RETOOL')
        # Selector-only interface control. Real evaluator admission is covered
        # separately by FrontOfficeBriefHTTPTests, without verdict patching.
        facts = {**facts, 'diagnostics':{'teams':{'1':{'positions':{
            p: dict(starter_need=True, evidence={'calculation_supported':True}, conclusion_state='current',base_reason=p+' gap')
            for p in ('RB','WR')}}}}}
        def offer(token):
            return dict(home_offer=token,home_assessment_strategy='RETOOL',evaluation=dict(
                recommendation='WORTH PURSUING',generated_trade_eligible=True,market_evidence={'availability':'full'},
                why_you_would_do_it='Supported lineup improvement',major_drawback='Capital cost',dimensions={'roster_diagnostics':{'sides':{'active':{'positions':{
                    'RB':{'pre':{'starter_need':True,'evidence':{'calculation_supported':True}},
                          'post':{'starter_need':False,'evidence':{'calculation_supported':True}}}}}}}}))
        result=select_insights(facts,[],[offer('first'),offer('second')])
        self.assertFalse(any(i['key']=='position:RB' for i in result))
        self.assertTrue(any(i['key']=='position:WR' for i in result))
        self.assertEqual([i['key'] for i in result if i['family']=='offer'],['offer:first','offer:second'])
        self.assertIn('RB gap',next(i['reason'] for i in result if i['family']=='offer'))
