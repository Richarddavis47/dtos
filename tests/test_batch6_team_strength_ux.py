"""Prepared-only Team HQ presentation; no optimization or remote calls."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from routes.teams import TEAM_HQ_CSS
from src.ui.team_strength import strength_panel


def prepared_profile():
    weekly = {}
    for week, pid, points in ((2, 'reserve', 27.335), (3, 'submitted', 0.0)):
        weekly[week] = {
            'optimal': {'available': True, 'projected_points': points, 'entries': [
                {'slot': 'QB', 'asset_id': pid, 'projected_points': points}]},
            'known_bye_player_ids': ['reserve'] if week == 3 else [],
            'bye_evidence_availability': 'supported',
            'reserve_capacity': {'supported_slots': 0},
            'previous_optimal_players_on_known_bye': ['reserve'] if week == 3 else [],
            'optimal_entries_since_previous_week': ['submitted'] if week == 3 else [],
            'total_change_since_previous_week': -27.335 if week == 3 else None}
    return {'generation': 'fixture', 'actual_submitted_starter_ids': ['submitted'], 'weekly': weekly,
        'horizons': {name: {'total': 27.335, 'weeks_requested': [2] if name == 'current_week' else [2, 3],
            'weeks_supported': [2] if name == 'current_week' else [2, 3], 'availability': 'complete',
            'source_confidence_range': [0.8, 0.9], 'league_rank': 1}
            for name in ('current_week', 'next_n', 'rest_of_regular_season', 'playoff_window')}}


class TeamStrengthUXTests(unittest.TestCase):
    def test_equal_submitted_and_optimal_is_not_an_improvement_alert(self):
        profile = prepared_profile()
        profile['actual_submitted_starter_ids'] = ['reserve']
        for row in profile['weekly'].values():
            row['previous_optimal_players_on_known_bye'] = []
        html = strength_panel(profile)
        self.assertIn('These players match the submitted starters.', html)
        self.assertNotIn('In the supported optimal lineup, not submitted:', html)
        self.assertIn('No supported prior-optimal-starter bye transition', html)
        self.assertNotIn('improvement opportunity', html.lower())
        self.assertLess(html.index('Current-week optimal lineup'), html.index('Current-week strength'))

    def test_prepared_values_identity_precision_and_no_second_engine(self):
        profile = prepared_profile()
        original = deepcopy(profile)
        players = [{'id': 'reserve', 'name': '<Reserve QB>'}, {'id': 'submitted', 'name': 'Submitted QB'}]
        with patch('src.core.intelligence.team_strength.optimal_legal_lineup', side_effect=AssertionError('read must not optimize')):
            html = strength_panel(profile, league_id='A', roster_id=1, players=players)
            for _ in range(100):
                self.assertEqual(strength_panel(profile, league_id='A', roster_id=1, players=players), html)
        self.assertEqual(profile, original)
        self.assertIn('27.335 projected points', html)
        self.assertIn('In the supported optimal lineup, not submitted', html)
        self.assertIn('DTOS has not changed your Sleeper lineup', html)
        self.assertIn('prior optimal starters on a known NFL bye', html)
        self.assertIn('Whole-lineup projected change: -27.335', html)
        self.assertIn('not attributed only to byes', html)
        self.assertIn('0 supported reserve slots', html)
        self.assertIn('&lt;Reserve QB&gt;', html)
        self.assertNotIn('<Reserve QB>', html)
        self.assertIn('not an outcome probability', html)

    def test_partial_is_not_complete_or_an_automatic_lineup_recommendation(self):
        profile = prepared_profile()
        profile['weekly'][2]['optimal'].update(available=False, projected_points=None)
        profile['horizons']['current_week'].update(total=None, availability='partial', weeks_supported=[],
                                                  supported_week_subtotal=None)
        profile.pop('actual_submitted_starter_ids')
        html = strength_panel(profile, league_id='A', roster_id=1)
        self.assertIn('Partial lineup only', html)
        self.assertIn('Submitted-lineup comparison unavailable', html)
        self.assertNotIn('These players match the submitted starters', html)
        self.assertIn('0/1 weeks', html)
        self.assertIn('<b>Unavailable</b>', html)
        profile['weekly'][2]['optimal']['entries'] = []
        self.assertIn('Current-week optimal lineup is unavailable', strength_panel(profile))

    def test_mobile_desktop_disclosures_links_and_contained_table(self):
        profile = prepared_profile()
        with sync_playwright() as engine:
            browser = engine.chromium.launch(headless=True)
            try:
                for width in (375, 390, 1280):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 900})
                        page.set_content(TEAM_HQ_CSS + strength_panel(profile, league_id='A', roster_id=1))
                        for name in ('Current-week optimal lineup · compare submitted starters', 'Weekly coverage and depth'):
                            summary = page.locator('summary').filter(has_text=name)
                            self.assertGreaterEqual(summary.bounding_box()['height'], 44)
                            summary.focus()
                            page.keyboard.press('Enter')
                            self.assertTrue(summary.evaluate('(e) => e.parentElement.open'))
                        for anchor in page.locator('.thq-optimal a').all():
                            self.assertGreaterEqual(anchor.bounding_box()['height'], 44)
                            self.assertTrue(anchor.get_attribute('href').startswith('/players/'))
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        self.assertEqual(page.locator('.thq-table-scroll').get_attribute('tabindex'), '0')
                        self.assertIn('0.00', page.locator('table').inner_text())
                        page.close()
            finally:
                browser.close()
