"""Future-week availability through normal preparation and rendered My Team."""
from datetime import timedelta
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.lineup_review_fixture import authenticated_prepared
from tests import test_upcoming_bye_moves as fixtures


def add_bench(data, pid, position, *, status='Active', injury_status=None):
    row = dict(id=pid, player_id=pid, name=f'Example {pid} reserve', position=position,
               fantasy_positions=[position], roster_slot='Bench', status=status, injury_status=injury_status)
    data['teams'][0]['players'].append(row)
    data['players'][pid] = dict(row)


def open_week(page):
    if page.goto('https://dtos.test/teams/1').status != 200:
        raise AssertionError('My Team unavailable')
    page.locator('.thq-tabs a[href="#team-byes"]').click()
    page.locator('#bye-week-9 > summary').click()
    return page.locator('[data-bye-week="9"]')


def capture(page, name):
    if directory := os.environ.get('DTOS_BYE_SCREENSHOTS'):
        Path(directory).mkdir(parents=True, exist_ok=True)
        page.locator('#upcoming-byes').screenshot(path=str(Path(directory, name)))


class UpcomingByeAvailabilityTests(unittest.TestCase):
    def _fixture(self, *, bench='RB'):
        return authenticated_prepared(self, empty=False, bench_position=bench, points={'bq': 1})

    def _check_moves(self, week, data, byes, moves):
        fixtures.UpcomingByeMovesTests._verify_moves(self, week, data, byes, moves)

    def test_prefers_available_alternative_to_ir_across_roster_orders(self):
        fixture, data, service, now = self._fixture()
        data['players']['1-bq']['injury_status'] = 'IR'
        add_bench(data, '1-z', 'RB')
        data['players_fetched_at'] = (now - timedelta(minutes=12)).isoformat()
        roster = data['teams'][0]['players']
        with fixtures.phone(fixture) as page:
            for order in (roster[:], roster[::-1], roster[2:] + roster[:2]):
                roster[:] = order
                fixtures.install_schedule(service, data, now, byes={'1-r'})
                week = open_week(page)
                self.assertEqual(week.get_attribute('data-bye-state'), 'covered')
                self.assertIn('Example 1-z reserve\nStart at RB', week.inner_text())
                self.assertNotIn('Example BQ 1', week.inner_text())
                self.assertIn('Sleeper player status checked 12 minutes ago.', week.inner_text())
                self._check_moves(week, data, {'1-r'}, {1: '1-z'})
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            capture(page, 'available-alternative-390.png')

    def test_available_superflex_chain_wins_over_shorter_out_plan(self):
        fixture, data, service, now = self._fixture(bench='QB')
        add_bench(data, '1-a', 'RB', injury_status='O')
        fixtures.install_schedule(service, data, now, byes={'1-r'})
        with fixtures.phone(fixture) as page:
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'covered')
            self.assertIn('Example S 1\nStart at RB · from Superflex', week.inner_text())
            self.assertIn('Example BQ 1\nStart at Superflex', week.inner_text())
            self._check_moves(week, data, {'1-r'}, {1: '1-s', 3: '1-bq'})
            week.get_by_role('link', name='View Week 9 Matchups').tap()
            page.wait_for_url('https://dtos.test/matchups?week=9')
            page.go_back()
            self.assertEqual(page.locator('#upcoming-byes').count(), 1)

    def test_competing_replacements_render_conditional_cover_and_dependency(self):
        fixture, data, service, now = self._fixture()
        add_bench(data, '1-a', 'QB', injury_status='IR')
        add_bench(data, '1-z', 'QB', injury_status='D')
        fixtures.install_schedule(service, data, now, byes={'1-r', '1-s'})
        with fixtures.phone(fixture) as page:
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'conditional')
            self.assertIn('Sleeper listed Example 1-z reserve as doubtful', week.inner_text())
            self.assertNotIn('Example 1-a reserve', week.inner_text())
            self.assertIn('Use this lineup only if all its players are available.', week.inner_text())
            self._check_moves(week, data, {'1-r', '1-s'}, {1: '1-bq', 3: '1-z'})
            capture(page, 'conditional-cover-390.png')
            # Both replacements remain necessary. No verified status for the
            # second player can establish an eligibility shortfall.
            data['players']['1-z'].update(status=None, injury_status=None)
            fixtures.install_schedule(service, data, now, byes={'1-r', '1-s'})
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'conditional')
            self.assertIn('Example 1-z reserve has unconfirmed availability.', week.inner_text())
            self._check_moves(week, data, {'1-r', '1-s'}, {1: '1-bq', 3: '1-z'})
            data['players']['1-z']['injury_status'] = 'Out'
            fixtures.install_schedule(service, data, now, byes={'1-r', '1-s'})
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'conditional')
            self.assertIn('Sleeper listed Example 1-a reserve as on injured reserve', week.inner_text())
            self._check_moves(week, data, {'1-r', '1-s'}, {1: '1-bq', 3: '1-a'})

    def test_aged_retained_plan_and_missing_status_clock_are_conditional(self):
        fixture, data, service, now = self._fixture()
        fixtures.install_schedule(service, data, now, byes={'1-r'})
        with fixtures.phone(fixture) as page:
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'covered')
            with patch('src.core.intelligence.upcoming_byes.datetime') as clock:
                clock.now.return_value = now + timedelta(hours=8)
                week = open_week(page)
                self.assertEqual(week.get_attribute('data-bye-state'), 'conditional')
                self.assertIn('Sleeper player status checked 8 hours ago. That check is stale.', week.inner_text())
                self._check_moves(week, data, {'1-r'}, {1: '1-bq'})
            data['players_fetched_at'] = None
            fixtures.install_schedule(service, data, now, byes={'1-r'})
            week = open_week(page)
            self.assertEqual(week.get_attribute('data-bye-state'), 'conditional')
            self.assertIn('The time of the Sleeper status check is unavailable.', week.inner_text())
            self._check_moves(week, data, {'1-r'}, {1: '1-bq'})
