"""Released prepared producers and HTML must explain depth without repetition."""
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
import unittest
from unittest.mock import patch

from tests import test_roster_diagnostic_http as fixtures
from tests import test_my_team_outlook as outlook
from tests.test_customer_home_team import DisclosureText


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
        f = self.fixture()
        f.publish('2020-01-01T00:00:00+00:00')
        response = f.f.f.client.get('/teams/1')
        self.assertEqual(response.status_code, 200)
        depth = response.text.split('id="positional-depth"', 1)[1].split('</section>', 1)[0]
        normal = DisclosureText(depth).text
        qualification = 'Provisional: check dates and player availability.'
        # The shared, visible qualification is concise. The source-specific
        # stale evidence remains attached to the optional position details.
        self.assertEqual(depth.count(qualification), 1)
        self.assertEqual(normal.count(qualification), 1)
        self.assertIn('QB · RB · WR · TE', normal)
        self.assertNotIn('Current-week evidence supports this roster comparison.', normal)
        self.assertIn('Stale', depth)
        self.assertEqual(depth.count('<details><summary>Replacement options and calculations</summary>'), 4)

    def test_distinct_position_warnings_and_zero_are_preserved_without_mutation(self):
        from routes.teams import _positional_depth
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
        positions['RB']['best_reserve_points'] = None
        self.assertGreater(positions['QB']['reserve_expected'], 0)
        qualifications = (
            'Roster comparison cannot be verified; review projections, scoring and availability.',
            'Current-week evidence supports this roster comparison.',
            'Provisional: check dates and player availability.',
        )
        for value, display in ((0, '0.00'), (-2.126, '-2.13')):
            with self.subTest(backup_points=value):
                positions['QB']['best_reserve_points'] = value
                before = deepcopy((positions, view['team']['players'], view.get('projection_snapshot')))
                with patch('src.core.trade_intelligence.lineup.optimal_legal_lineup', side_effect=AssertionError('solver')):
                    rendered = _positional_depth(view)
                normal = DisclosureText(rendered).text
                self.assertEqual((positions, view['team']['players'], view.get('projection_snapshot')), before)
                for position in ('QB', 'RB', 'WR', 'TE'):
                    detail = position + ': distinct supported detail.'
                    self.assertIn(detail, rendered)
                    self.assertNotIn(detail, normal, 'Position calculations stay available on demand')
                    for row in positions[position]['diagnostic'].get('eligibility') or []:
                        if row.get('excluded') or row.get('status') != 'active':
                            self.assertIn(escape(row['name']), rendered)
                            self.assertIn(escape(row['reason']), rendered)
                for qualification in qualifications:
                    self.assertEqual(rendered.count(qualification), 1)
                    self.assertEqual(normal.count(qualification), 1)
                self.assertIn('QB · RB', normal)
                self.assertIn(f'Best supported backup: {display} points.', normal)
                # Missing RB cover is one named gap, not an unavailable numeric
                # contribution repeated on every position or an inferred zero.
                self.assertIn('Backup point comparisons are incomplete at', normal)
                gap = normal.split('Backup point comparisons are incomplete at', 1)[1].split('.', 1)[0]
                self.assertIn('RB', gap)
                self.assertNotIn('Best supported backup: Unavailable points.', normal)
                self.assertNotIn('Best supported reserve: Unavailable points.', rendered)
                self.assertEqual(rendered.count('<details><summary>Replacement options and calculations</summary>'), 4)


if __name__ == '__main__':
    unittest.main()
