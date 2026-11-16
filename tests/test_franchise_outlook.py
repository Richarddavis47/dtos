"""Evidence selection and shared presentation; no new franchise score."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from services.franchise_outlook import franchise_outlook


class FranchiseOutlookTests(unittest.TestCase):
    def render(self, positions=None, inventory=None):
        data={'league':{'league_id':'L'},'week':10}
        card=SimpleNamespace(league_id='L',roster_id=1,future_capital_evidence={})
        result=SimpleNamespace(team_assessment=SimpleNamespace(team=card,roster_id=1,projection_week=10,league_id='L',generation='g'),context=SimpleNamespace(projection_snapshot=None))
        diagnostic={'league_id':'L','week':10,'projection_generation':'p','required_slot_count':10,'teams':{'1':{'positions':positions or {},'optimal_points':0,'optimal_ids':list(range(10)), 'evidence':{'calculation_supported':True,'conclusion_state':'current'}}}}
        old=dict(position='old position',brief='old rank',strength='old strength',concern='old concern',future='old inventory',details=['Prepared Team Strength covers 1/1 current weeks; complete-horizon points: 900.'])
        inventory=inventory or dict(complete=False,reason='Ownership incomplete; remaining totals unknown.',before=[])
        with patch('services.franchise_outlook.roster_overview',return_value={}),patch('services.franchise_outlook.prepared_outlook',return_value=deepcopy(old),create=True),patch('services.franchise_outlook.prepared_comparison',return_value=diagnostic),patch('services.franchise_outlook.inventory_baseline',return_value=inventory):
            return franchise_outlook(data,result)

    def test_current_zero_is_not_missing_and_saved_rank_is_not_reused(self):
        row=self.render()
        self.assertIn('0',row['position'])
        self.assertNotIn('old',row['position'])
        self.assertIn('unknown',row['future'])

    def test_supported_strength_and_depth_remain_separate(self):
        row=self.render({'QB':dict(strength=True,conclusion_state='current',evidence={'calculation_supported':True}),'RB':dict(quality_depth_need=True,conclusion_state='current',evidence={'calculation_supported':True})})
        self.assertIn('QB',row['strength'])
        self.assertIn('RB',row['concern'])
        self.assertIn('eligible backups',row['concern'])

    def test_provisional_findings_keep_their_qualification(self):
        row=self.render({'RB':dict(starter_need=True,strength=True,conclusion_state='provisional',evidence={'calculation_supported':True})})
        self.assertTrue(row['strength'].startswith('Provisional:'))
        self.assertTrue(row['concern'].startswith('Provisional:'))

    def test_unavailable_flags_cannot_become_a_weakness(self):
        row=self.render({'RB':dict(starter_need=True,conclusion_state='unavailable',evidence={'calculation_supported':False})})
        self.assertIn('no roster weakness',row['concern'])

    def test_complete_zero_inventory_is_zero_only_for_retained_seasons(self):
        row=self.render(inventory=dict(complete=True,before=[],seasons=[2027,2028],reason=''))
        self.assertIn('0 owned picks in 2027, 2028',row['future'])
        self.assertIn('not a forecast',row['future'])

    def test_partial_inventory_preserves_supported_count_without_total(self):
        row=self.render(inventory=dict(complete=False,before=[[2027,1,2]],reason='Partial ownership; totals unknown.'))
        self.assertIn('1 individually supported',row['future'])
        self.assertIn('not a complete inventory',row['future'])

    def test_own_and_acquired_exact_firsts_stay_distinct(self):
        row=self.render(inventory=dict(complete=True,before=[[2027,1,1],[2027,1,2]],seasons=[2027],reason=''))
        self.assertIn('2 first-round picks (1 originally yours)',row['future'])

    def test_home_cannot_restore_unconfirmed_totals_from_assessment_prices(self):
        from services.front_office_brief import select_insights
        outlook=self.render()
        facts=dict(roster_id=1,strategy='REBUILD',league_id='L',generation='g',week=10,league_name='Fixture',outlook=outlook,
            assessment=SimpleNamespace(team=SimpleNamespace(future_capital_evidence=dict(league_id='L',roster_id=1,generation='g',picks=[dict(identity=dict(round=1,year=2027))],priced_pick_count=1))))
        cards=select_insights(facts,[],[])
        capital=next(c for c in cards if c['family']=='capital')
        self.assertEqual(capital['title'],'Review recorded draft picks')
        self.assertIn('unknown',capital['reason'])
        self.assertNotIn('1 owned',capital['title']+capital['reason'])

    def test_recorded_horizon_cannot_explain_current_diagnostic(self):
        row=self.render()
        self.assertIn('0.00',row['position'])
        self.assertNotIn('900', ' '.join(row['details']))
