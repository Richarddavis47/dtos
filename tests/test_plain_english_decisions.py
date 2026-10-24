"""Customer explanations must qualify prepared facts without changing evidence."""
from copy import deepcopy
from dataclasses import replace
import unittest

from services.trade_decision import decision_context
from src.ui.front_office_brief import cards
from tests import test_my_team_outlook as outlook_fixtures
from tests import test_trade_missing_market_presentation as trade_fixtures


class PlainEnglishDecisionTests(unittest.TestCase):
    def test_unavailable_trend_is_not_flat_and_supported_zero_remains_numeric(self):
        from routes.market import _trend_observation_summary
        unavailable = _trend_observation_summary({'checkpoint_count':1, 'direction':'unavailable', 'magnitude':None})
        self.assertIn('missing history does not mean', unavailable)
        self.assertNotIn('Step 2', unavailable)
        zero = _trend_observation_summary({'checkpoint_count':2, 'direction':'stable', 'magnitude':0,
            'comparison_units':'0-1000', 'comparison_scope':'historical_only'})
        self.assertIn('+0.00 Market points', zero)
        self.assertNotIn('not enough', zero)

    def test_exact_pick_uses_known_team_label_and_keeps_source_identity_in_disclosure(self):
        from tests import test_front_office_brief as brief_fixtures
        from services.front_office_brief import select_insights
        fixture = brief_fixtures.FrontOfficeBriefTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.f.data['teams'][0]['picks_owned'] = [dict(year=2029, round=1,
            original_roster_id=2, original_team='Arkham Knights', current_owner_id=1)]
        facts = fixture.prepared('REBUILD')
        # Use the prepared producer's supported label; never manufacture a name.
        identity = facts['assessment'].team.future_capital_evidence['picks'][0]['identity']
        identity['original_team'] = 'Arkham Knights'
        item = next(row for row in select_insights(facts, [], []) if row['family'] == 'capital')
        self.assertIn('2029 first · Arkham Knights · owned by your team', item['reason'])
        self.assertNotIn('owner 1', item['reason'])
        html = cards([item])
        self.assertIn('original 2', html)
        self.assertIn('owner 1', html)
        self.assertIn('<summary>Supporting evidence</summary>', html)

    def test_unknown_depth_is_not_a_proven_risk_in_compact_takeaway(self):
        fixture = outlook_fixtures.MyTeamOutlookTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view = fixture.view()
        assessment = view['assessment']
        positions = deepcopy(assessment.roster_evidence.positions)
        for row in positions.values():
            row['reserve_covered'] = 0
        changed = replace(assessment, roster_evidence=replace(assessment.roster_evidence, positions=positions))
        before = deepcopy(changed)
        text = fixture.format(view, changed)
        self.assertIn('Depth evidence is incomplete', text['brief'])
        self.assertNotIn('Biggest depth risk', text['brief'])
        self.assertEqual(changed, before)

    def test_incompatible_summary_explains_next_step_without_diagnosing_weakness(self):
        fixture = outlook_fixtures.MyTeamOutlookTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        view = fixture.view()
        text = fixture.format(view, replace(view['assessment'], generation='superseded'))
        self.assertIn('Refresh', text['brief'])
        self.assertNotIn('Biggest depth risk', text['brief'])

    def test_weekly_gain_and_incomplete_recommendation_explain_coverage(self):
        fixture = trade_fixtures.MissingMarketPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        result = fixture.evaluate()
        result['recommendation_availability'] = 'unavailable'
        strategy = result['dimensions']['strategic_fit']['active']
        strategy['projection_coverage_complete'] = False
        before = deepcopy(result)
        context = decision_context(result)
        self.assertEqual(context['lineup']['delta'], 5)
        self.assertIn('This week', context['coverage_explanation'])
        self.assertIn('not a complete', context['coverage_explanation'])
        self.assertIn('periods', context['coverage_explanation'])
        self.assertEqual(result, before)

    def test_missing_price_preserves_conditional_heading_and_supported_zero(self):
        fixture = trade_fixtures.MissingMarketPresentationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.remove_prices('1q')
        result = fixture.evaluate()
        fixture.assert_conditional(result)
        context = decision_context(result)
        self.assertIn('Market', context['coverage_explanation'])
        self.assertIn('not an endorsement', context['qualification'])
        fixture.fixture.configure(sent=0, received=0, delta=0)
        zero = fixture.evaluate()
        self.assertEqual(zero['market_evidence']['availability'], 'full')
        self.assertEqual(zero['decision_context']['lineup']['delta'], 0)

    def test_reassuring_goal_information_is_not_labeled_a_tradeoff(self):
        item = dict(key='goal', family='goal', title='Choose your goal', reason='No goal is selected.',
                    drawback='Neutral Market values and lineup facts stay unchanged.',
                    action='Choose a goal', href='/account', details=[])
        html = cards([item])
        self.assertIn('Keep in mind:', html)
        self.assertNotIn('Tradeoff:', html)

    def test_depth_evidence_status_explains_missing_and_provisional(self):
        from src.ui.intelligence_presentation import projection_evidence_summary
        self.assertIn('cannot confirm', projection_evidence_summary({'conclusion_state':'unavailable'}))
        self.assertIn('provisional', projection_evidence_summary({'conclusion_state':'provisional'}))
        self.assertIn('current', projection_evidence_summary({'conclusion_state':'current'}))


if __name__ == '__main__':
    unittest.main()
