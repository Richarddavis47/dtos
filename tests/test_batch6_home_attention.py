import unittest
from copy import deepcopy
from unittest.mock import patch

from services.home_attention import attention_state
from src.ui.home_attention import attention_panel


class AttentionTests(unittest.TestCase):
    def test_home_directory_never_builds_on_miss_or_expiry(self):
        from types import SimpleNamespace
        from src.core.intelligence.cache import IntelligenceCache
        from services.team_headquarters import build_team_directory
        cache = IntelligenceCache()
        engine = SimpleNamespace(cache=cache, context=lambda *args: SimpleNamespace(snapshot_key='A'),
                                 analyze=lambda *args, **kwargs: self.fail('read-side construction'))
        with patch('services.team_headquarters.intelligence_orchestrator', engine):
            self.assertEqual(build_team_directory(self.data, prepared_only=True), {})
            card = SimpleNamespace(preseason=False, overall=SimpleNamespace(rank=2, grade='B'),
                                   projected_wins=None, playoff_odds=None, championship_odds=None)
            key = 'snapshot:A:result_without_trade_opportunities'
            cache.get_or_create(key, lambda: SimpleNamespace(roster=SimpleNamespace(team_intelligence={1: card})))
            self.assertEqual(build_team_directory(self.data, prepared_only=True)[1]['rank'], 2)
            cache.invalidate()
            cache.get_or_create(key, lambda: 'expired', ttl=-1)
            self.assertEqual(build_team_directory(self.data, prepared_only=True), {})

    def setUp(self):
        self.data = {'league': {'league_id': 'A'}, 'teams': [{'roster_id': 1}]}
        self.profile = {'season': 2026, 'current_week': 2, 'semantic_generation': 'g', 'methodology_version': 'm',
                        'teams': {'1': {'horizons': {'next_n': {'weeks_requested': [2, 3]}},
                                        'weekly': {'2': {'optimal': {'available': True, 'unsupported_slots': []}},
                                                   '3': {'optimal': {'available': True, 'unsupported_slots': []}}}}}}

    def run_state(self):
        with patch('services.home_attention.compatible_profile', return_value=self.profile):
            return attention_state(self.data, 1, {})

    def test_optimal_exists_is_quiet_not_edge(self):
        result = self.run_state()
        self.assertEqual(result['items'], [])
        self.assertEqual(len(result['candidates']), 2)
        self.assertIn('not proof that no changes exist', attention_panel(result))

    def test_current_partial_is_coverage_not_poor_performance(self):
        self.profile['teams']['1']['weekly']['2']['optimal'] = {'available': False, 'unsupported_slots': ['QB']}
        result = self.run_state()
        self.assertEqual(result['items'][0]['kind'], 'current_state')
        html = attention_panel(result)
        self.assertIn('not a prediction of poor performance', html)
        self.assertIn('DTOS-derived evidence', html)
        self.assertIn('/teams/1', html)

    def test_future_gap_requires_supported_bye_context(self):
        row = self.profile['teams']['1']['weekly']['3']
        row['optimal'] = {'available': False, 'unsupported_slots': ['TE']}
        self.assertEqual(self.run_state()['items'], [])
        row['previous_optimal_players_on_known_bye'] = ['x']
        self.assertEqual(len(self.run_state()['items']), 1)

    def test_multiple_weeks_compose_without_losing_context(self):
        for row in self.profile['teams']['1']['weekly'].values():
            row.update(optimal={'available': False, 'unsupported_slots': ['QB']}, previous_optimal_players_on_known_bye=['x'])
        result = self.run_state()
        self.assertEqual(result['deduplicated'], 1)
        self.assertEqual(result['items'][0]['related_weeks'], [3])

    def test_incompatible_generation_and_league_fail_closed(self):
        with patch('services.home_attention.compatible_profile', return_value=None):
            self.assertEqual(attention_state(self.data, 1, {})['items'], [])
        self.assertEqual(attention_state(self.data, 9, {})['items'], [])

    def test_replay_does_not_mutate_evidence(self):
        before = deepcopy((self.data, self.profile))
        first = self.run_state()
        for _ in range(100):
            self.assertEqual(self.run_state(), first)
        self.assertEqual((self.data, self.profile), before)

    def test_mobile_desktop_shared_disclosure(self):
        from playwright.sync_api import sync_playwright
        self.profile['teams']['1']['weekly']['2']['optimal'] = {'available': False, 'unsupported_slots': ['QB']}
        html = attention_panel(self.run_state())
        with sync_playwright() as browser_engine:
            browser = browser_engine.chromium.launch(headless=True)
            try:
                for width in (390, 1280):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    page.set_content(html)
                    for control in page.locator('summary').all():
                        control.focus()
                        page.keyboard.press('Enter')
                        self.assertTrue(control.evaluate('(e) => e.parentElement.open'))
                        self.assertGreaterEqual(control.bounding_box()['height'], 44)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    self.assertEqual(page.locator('a').get_attribute('href'), '/teams/1')
                    page.close()
            finally:
                browser.close()


if __name__ == '__main__':
    unittest.main()
