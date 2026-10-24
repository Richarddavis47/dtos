"""Released prepared producers and HTML must explain depth without repetition."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from tests import test_roster_diagnostic_http as fixtures
from tests import test_my_team_outlook as outlook


class PlainEnglishHomeDepthTests(unittest.TestCase):
    def fixture(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        return f

    def test_actual_home_prepared_response_explains_unknown_direction_and_goal(self):
        f = self.fixture()
        f.publish(datetime.now(timezone.utc).isoformat())
        f.f.f.client.cookies.delete('dtos_strategy')
        response = f.f.f.client.get('/api/trades/home-opportunities?front_office=1')
        self.assertEqual(response.status_code, 200)
        rendered = response.json()['brief_html']
        self.assertIn('DTOS cannot determine whether to contend, retool or rebuild', rendered)
        self.assertIn('Choose your goal', rendered)
        self.assertIn('/teams/1#my-team-strategy', rendered)
        self.assertNotIn('no competitive direction is inferred', rendered)
        self.assertNotIn('objective legal-lineup calculations', rendered)

    def test_actual_stale_depth_groups_one_shared_warning_for_named_positions(self):
        from src.ui.intelligence_presentation import projection_evidence_summary
        f = self.fixture()
        f.publish('2020-01-01T00:00:00+00:00')
        response = f.f.f.client.get('/teams/1')
        self.assertEqual(response.status_code, 200)
        depth = response.text.split('id="positional-depth"', 1)[1].split('</section>', 1)[0]
        qualification = projection_evidence_summary({'conclusion_state': 'provisional'})
        self.assertEqual(depth.count(qualification), 1)
        self.assertIn('QB · RB · WR · TE', depth)
        self.assertEqual(depth.count('<summary>Lineup eligibility and surplus</summary>'), 4)

    def test_distinct_position_warnings_and_zero_are_preserved_without_mutation(self):
        from routes.teams import _positional_depth
        from src.ui.intelligence_presentation import projection_evidence_summary
        f = outlook.MyTeamOutlookTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        view = f.view()
        positions = view['overview']['positions']
        for position, state in [('QB', 'unavailable'), ('RB', 'unavailable'),
                                ('WR', 'current'), ('TE', 'provisional')]:
            positions[position]['diagnostic'] = deepcopy(positions[position]['diagnostic'])
            positions[position]['diagnostic']['evidence']['conclusion_state'] = state
            positions[position]['diagnostic']['interpretation'] = position + ': distinct supported detail.'
        positions['QB']['best_reserve_points'] = 0
        positions['RB']['best_reserve_points'] = None
        before = deepcopy((positions, view['team']['players'], view.get('projection_snapshot')))
        with patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('solver')):
            rendered = _positional_depth(view)
        self.assertEqual((positions, view['team']['players'], view.get('projection_snapshot')), before)
        for position in ('QB', 'RB', 'WR', 'TE'):
            self.assertIn(position + ': distinct supported detail.', rendered)
        for state in ('unavailable', 'current', 'provisional'):
            self.assertEqual(rendered.count(projection_evidence_summary({'conclusion_state':state})), 1)
        self.assertIn('QB · RB', rendered)
        self.assertIn('Best supported reserve: 0.00 points.', rendered)
        self.assertIn('Best supported reserve: Unavailable points.', rendered)


if __name__ == '__main__':
    unittest.main()
