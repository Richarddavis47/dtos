import os
from datetime import timedelta
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from src.core.intelligence.team_strength import prepare_for_data
from src.core.intelligence.upcoming_byes import _week, prepare_upcoming_byes
from tests.lineup_review_fixture import authenticated_prepared
from tools.validation.browser_runtime import launch_chromium


class UpcomingByeTests(unittest.TestCase):
    def test_kicker_and_defense_coverage_does_not_require_points(self):
        roster = {
            'idle': ('BUF', ('K',), True), 'backup': ('KC', ('K',), True),
            'defense': ('KC', ('DEF',), True),
        }
        row = _week(['K', 'DEF'], roster, {'9:KC': True}, {'idle': 9}, 9, {})
        self.assertEqual((row['state'], row['affected'], row['moves']), ('covered', ['K'], [['K', 'backup']]))
        self.assertFalse(row['projection_ready'])

    def test_two_byes_compete_for_one_replacement(self):
        roster = {
            'qb': ('KC', ('QB',), True), 'rb': ('BUF', ('RB',), True),
            'wr': ('BUF', ('WR',), True), 'only_sub': ('KC', ('RB', 'WR'), True),
        }
        byes = {'rb': 9, 'wr': 9}
        row = _week(['QB', 'FLEX', 'SUPER_FLEX'], roster, {'9:KC': True}, byes, 9, {})
        self.assertEqual(row['state'], 'shortfall')
        self.assertEqual(len(row['unfilled']), 1)
        self.assertEqual(set(row['byes']), set(byes))
        roster['unknown_player'] = (None, (), True)
        unknown = _week(['QB', 'FLEX', 'SUPER_FLEX'], roster, {'9:KC': True}, byes, 9, {})
        self.assertEqual(unknown['state'], 'unknown')
        self.assertEqual(unknown['unfilled'], [])

    def test_superflex_fit_reports_the_complete_set_of_moves(self):
        roster = {
            'starter-qb': ('KC', ('QB',), True), 'bye-rb': ('BUF', ('RB',), True),
            'starter-flex': ('KC', ('RB',), True), 'backup-qb': ('KC', ('QB',), True),
        }
        row = _week(['QB', 'RB', 'SUPER_FLEX'], roster, {'9:KC': True}, {'bye-rb': 9}, 9, {'available': True})
        self.assertEqual(row['state'], 'covered')
        self.assertEqual(row['moves'], [['RB', 'starter-flex'], ['SUPER_FLEX', 'backup-qb']])

    def test_no_rollover_forecast_outside_the_scheduled_league_season(self):
        data = {'league': {'sport': 'nfl', 'status': 'in_season'}, 'week': 18}
        self.assertEqual(prepare_upcoming_byes(data, {'regular_season_weeks': list(range(1, 19))},
                                              None, None, {}), {})
        data['league']['status'] = 'pre_draft'
        self.assertEqual(prepare_upcoming_byes(data, {}, None, None, {}), {})

    def test_owner_phone_roster_to_prepared_bye_and_future_matchups(self):
        fixture, data, service, now = authenticated_prepared(
            self, empty=False, earlier_backup=True, bench_position='RB', points={'bq': 1},
        )
        client = fixture.f.f.client

        # Complete disposable schedule shape, including the named teams' byes.
        facts = []
        clubs = ['BUF', 'KC'] + [f'X{i:02}' for i in range(30)]
        for week in range(1, 19):
            for index, (home, away) in enumerate(zip(clubs[::2], clubs[1::2])):
                if week == (9 if index == 0 else ((index + 8) % 18) + 1):
                    continue
                facts.append(dict(
                    family='schedule', season=2026, provider='nflverse', week=week,
                    fingerprint=f'game-{week}-{index}',
                    values=dict(game_type='REG', home_team=home, away_team=away,
                                kickoff=(now + timedelta(days=(week - 8) * 7)).isoformat()),
                ))
        # Put the backup on a team that plays Week 9 while the starter is on bye.
        data['teams'][0]['players'][1]['team'] = 'X00'
        data['players']['1-bq']['team'] = 'X00'
        with patch('services.global_evidence.retained_global_evidence') as store:
            store.return_value.read.return_value = facts
            prepared = prepare_for_data(service, data)
        self.assertEqual(prepared['upcoming_byes']['1'][0]['week'], 9)
        with patch('src.core.intelligence.upcoming_byes._fit', side_effect=AssertionError('page used solver')):
            with sync_playwright() as pw:
                browser = launch_chromium(pw, headless=True)
                try:
                    page = browser.new_page(viewport={'width': 390, 'height': 844}, has_touch=True)

                    def transport(route):
                        path = urlsplit(route.request.url)
                        if path.hostname != 'dtos.test':
                            return route.fulfill(status=200, body='')
                        response = client.get(path.path + (f'?{path.query}' if path.query else ''))
                        if response.status_code == 404 and path.path.startswith('/static/'):
                            response = fixture.f.static.get(path.path)
                        route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.content)

                    page.route('**/*', transport)
                    self.assertEqual(page.goto('https://dtos.test/teams/1').status, 200)
                    first = page.locator('#full-roster .thq-player').first
                    self.assertTrue(first.is_visible())
                    before = first.evaluate('e => e.getBoundingClientRect().top + scrollY')
                    # Compare the same prepared state with the new section absent.
                    # The standing phone journey retains its independent 600px check.
                    with patch('src.ui.upcoming_byes.upcoming_byes_panel', return_value=''):
                        page.reload()
                        self.assertEqual(before, first.evaluate('e => e.getBoundingClientRect().top + scrollY'))
                    page.reload()
                    summary = page.get_by_text('See weeks and possible moves', exact=True)
                    summary.focus()
                    summary.press('Enter')
                    panel = page.locator('#upcoming-byes')
                    self.assertIn('Week 9', panel.inner_text())
                    self.assertIn('Week 10', panel.inner_text())
                    self.assertIn('cannot fill every starting spot', panel.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                    if directory := os.environ.get('DTOS_BYE_SCREENSHOTS'):
                        Path(directory).mkdir(parents=True, exist_ok=True)
                        panel.screenshot(path=str(Path(directory) / 'my-team-upcoming-byes-390.png'))
                    panel.get_by_role('link', name='View Week 9 Matchups').tap()
                    page.wait_for_url('https://dtos.test/matchups?week=9')
                    self.assertEqual(page.locator('#lineup-recheck').count(), 0)
                    page.go_back()
                    self.assertEqual(page.locator('#upcoming-byes').count(), 1)
                finally:
                    browser.close()
