"""My Team section navigation in a prepared, authorized browser fixture."""
import unittest
from unittest.mock import patch

from routes.navigation import create_navigation_router
from tests.lineup_review_fixture import authenticated_prepared
from tests.test_upcoming_bye_moves import install_schedule, phone


class MyTeamSectionsBrowserTests(unittest.TestCase):
    def test_roster_and_exact_home_bye_survive_both_matchup_round_trips(self):
        fixture, data, service, now = authenticated_prepared(self, empty=False, points={'bq': 1})
        fixture.f.f.client.app.include_router(create_navigation_router())
        install_schedule(service, data, now, byes={'1-r'})

        with patch('services.trade_intelligence._trade_projection_service', return_value=service), phone(fixture) as page:
            page.set_default_timeout(7500)
            page.context.add_cookies([dict(name='dtos_strategy', value=fixture.f.cookie, url='https://dtos.test/')])
            writes = []
            page.on('request', lambda request: writes.append(request.url) if request.method != 'GET' else None)
            for width, height in ((320, 432), (390, 844), (1280, 900)):
                with self.subTest(width=width):
                    page.set_viewport_size(dict(width=width, height=height))
                    page.goto('https://dtos.test/teams/1')
                    tabs = page.get_by_role('navigation', name='My Team sections')
                    self.assertEqual(tabs.get_by_role('link').all_inner_texts(), ['Roster', 'Lineup', 'Byes', 'Picks'])
                    self.assertEqual(tabs.locator('[aria-current]').inner_text(), 'Roster')
                    self.assertEqual(page.locator('[data-team-section]:visible').count(), 1)
                    self.assertTrue(page.locator('#full-roster .thq-player').first.is_visible())
                    self.assertLess(page.locator('#full-roster .thq-player').first.bounding_box()['y'], 600)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    for link in tabs.get_by_role('link').all():
                        self.assertGreaterEqual(link.bounding_box()['height'], 44)

                    picks = tabs.get_by_role('link', name='Picks')
                    picks.focus()
                    picks.press('Enter')
                    page.locator('#draft-capital').wait_for(state='visible')
                    page.reload()
                    self.assertEqual(tabs.locator('[aria-current]').inner_text(), 'Picks')

                    page.goto('https://dtos.test/')
                    action = page.locator('#home-priority').get_by_role('link', name='Review bye plan')
                    action.wait_for()
                    self.assertEqual(action.get_attribute('href'), '/teams/1#bye-week-9')
                    action.tap()
                    self.assertEqual(tabs.locator('[aria-current]').inner_text(), 'Byes')
                    week = page.locator('#bye-week-9')
                    other = page.locator('#bye-week-10')
                    self.assertTrue(week.evaluate('e=>e.open'))
                    self.assertFalse(other.evaluate('e=>e.open'))
                    self.assertIn('Make these changes together.', week.inner_text())
                    self.assertIn('Start at RB · from Superflex', week.inner_text())
                    page.reload()
                    self.assertTrue(week.evaluate('e=>e.open'))
                    week.get_by_role('link', name='View Week 9 Matchups').tap()
                    page.wait_for_url('**/matchups?week=9')
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**/teams/1#bye-week-9')
                    self.assertTrue(week.evaluate('e=>e.open'))
                    self.assertFalse(other.evaluate('e=>e.open'))

                    page.goto('https://dtos.test/teams/1#team-byes')
                    other.locator('summary').press('Enter')
                    self.assertTrue(other.evaluate('e=>e.open'))
                    other.get_by_role('link', name='View Week 10 Matchups').tap()
                    page.wait_for_url('**/matchups?week=10')
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**/teams/1#team-byes')
                    other.locator('.thq-bye-content').wait_for()
                    self.assertFalse(week.evaluate('e=>e.open'))
                    self.assertEqual(tabs.locator('[aria-current]').inner_text(), 'Byes')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)

            # Other franchises do not inherit the selected owner's plans.
            page.goto('https://dtos.test/teams/2#bye-week-9')
            self.assertEqual(page.locator('.thq-tabs [aria-current]').inner_text(), 'Byes')
            self.assertEqual(page.locator('[data-bye-week]').count(), 0)
            self.assertEqual(writes, [])
