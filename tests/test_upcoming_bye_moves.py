"""Rendered coverage from prepared submitted slots and retained schedule facts."""
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from src.core.intelligence.team_strength import prepare_for_data
from tests.lineup_review_fixture import authenticated_prepared
from tools.validation.browser_runtime import launch_chromium


def install_schedule(service, data, now, *, byes, missing=()):
    # A complete schedule establishes byes. Removing a single game invalidates
    # inferred byes for this revision, while present games are still known.
    clubs = ['BUF', 'KC'] + [f'X{i:02}' for i in range(30)]
    facts = [
        dict(family='schedule', season=2026, provider='nflverse', week=week,
             fingerprint=f'bye-moves-{week}-{idx}',
             values=dict(game_type='REG', home_team=home, away_team=away,
                         kickoff=(now + timedelta(days=7 * (week - 8))).isoformat()))
        for week in range(1, 19)
        for idx, (home, away) in enumerate(zip(clubs[::2], clubs[1::2]))
        if week != (9 if idx == 0 else (idx + 8) % 18 + 1)
        and (week, idx) not in missing
    ]
    data.setdefault('players_fetched_at', now.isoformat())
    team = data['teams'][0]
    for row in team['players']:
        club = 'BUF' if row['id'] in byes else 'X02'
        row['team'] = data['players'][row['id']]['team'] = club
    with patch('services.global_evidence.retained_global_evidence') as store:
        store.return_value.read.return_value = facts
        return prepare_for_data(service, data)


@contextmanager
def phone(fixture):
    client = fixture.f.f.client
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
            yield page
        finally:
            browser.close()


class UpcomingByeMovesTests(unittest.TestCase):
    def _owner_fixture(self, **kwargs):
        return authenticated_prepared(self, empty=False, points={'bq': 1}, **kwargs)

    def _render_week(self, page):
        self.assertEqual(page.goto('https://dtos.test/teams/1').status, 200)
        disclosure = page.get_by_text('See weeks and possible moves', exact=True)
        disclosure.focus()
        disclosure.press('Enter')
        return page.locator('[data-bye-week="9"]')

    def _verify_moves(self, row, data, bye_ids, expected):
        # Apply the rendered changes together to the original recorded slots.
        # Check expected eligible positions independently of the matching engine.
        slots = [slot for slot in data['league']['roster_positions'] if slot != 'BN']
        assigned = {p['starter_index']: p['id'] for p in data['teams'][0]['players']
                    if p['roster_slot'] == 'Starter'}
        bench = {p['id'] for p in data['teams'][0]['players'] if p['roster_slot'] == 'Bench'}
        absent = row.locator('[data-bye-starter]').evaluate_all(
            "(nodes) => nodes.map(n => [Number(n.dataset.slotIndex), n.dataset.byeStarter])")
        self.assertEqual({pid for _, pid in absent}, bye_ids)
        for index, pid in absent:
            self.assertEqual(assigned[index], pid)
        moves = dict(row.locator('[data-bye-move]').evaluate_all(
            "(nodes) => nodes.map(n => [Number(n.dataset.slotIndex), n.dataset.byeMove])"))
        self.assertEqual(moves, expected)
        self.assertLessEqual(set(moves.values()), set(assigned.values()) | bench)
        assigned.update(moves)
        self.assertEqual(set(assigned), set(range(len(slots))))
        self.assertEqual(len(set(assigned.values())), len(slots))
        self.assertTrue(bye_ids.isdisjoint(assigned.values()))
        extras = {'FLEX': {'RB', 'WR', 'TE'}, 'SUPER_FLEX': {'QB', 'RB', 'WR', 'TE'}}
        for index, pid in assigned.items():
            positions = set(data['players'][pid]['fantasy_positions'])
            self.assertTrue(positions.intersection(extras.get(slots[index], {slots[index]})))

    def test_rendered_wr_flex_bye_and_moves_are_roster_order_independent(self):
        fixture, data, service, now = self._owner_fixture(
            bench_position='RB', slots=['QB', 'RB', 'FLEX', 'RB', 'BN'],
        )
        players = data['teams'][0]['players']
        order = ['1-q', '1-r', '1-s', '1-w', '1-bq']
        players.sort(key=lambda row: order.index(row['id']))
        with phone(fixture) as page:
            prior = None
            for arrangement in (players[:], players[::-1], players[2:] + players[:2]):
                players[:] = arrangement
                install_schedule(service, data, now, byes={'1-w'})
                row = self._render_week(page)
                self.assertEqual(row.get_attribute('data-bye-state'), 'covered')
                self.assertIn('Example W 1 is on bye in FLEX.', row.inner_text())
                self.assertIn('Start Example BQ 1 at FLEX.', row.inner_text())
                self._verify_moves(row, data, {'1-w'}, {2: '1-bq'})
                text = row.inner_text()
                if prior is not None:
                    self.assertEqual(text, prior)
                prior = text
            self.assertEqual(page.locator('[data-bye-week="10"]').get_attribute('data-bye-state'), 'no_gap')
            panel = page.locator('#upcoming-byes')
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            if directory := os.environ.get('DTOS_BYE_SCREENSHOTS'):
                Path(directory).mkdir(parents=True, exist_ok=True)
                panel.screenshot(path=str(Path(directory, 'my-team-upcoming-bye-moves-390.png')))
            row.get_by_role('link', name='View Week 9 Matchups').tap()
            page.wait_for_url('https://dtos.test/matchups?week=9')
            page.go_back()
            self.assertEqual(page.locator('#upcoming-byes').count(), 1)

    def test_rendered_superflex_chain_preserves_legal_slots(self):
        fixture, data, service, now = self._owner_fixture()
        install_schedule(service, data, now, byes={'1-r'})
        with phone(fixture) as page:
            row = self._render_week(page)
            self.assertEqual(row.get_attribute('data-bye-state'), 'covered')
            self.assertIn('Move Example S 1 from Superflex to RB.', row.inner_text())
            self.assertIn('Start Example BQ 1 at Superflex.', row.inner_text())
            self._verify_moves(row, data, {'1-r'}, {1: '1-s', 3: '1-bq'})

    def test_rendered_competing_replacement_shortfall_and_incomplete_eligibility(self):
        fixture, data, service, now = self._owner_fixture(bench_position='RB')
        install_schedule(service, data, now, byes={'1-r', '1-s'})
        with phone(fixture) as page:
            row = self._render_week(page)
            self.assertEqual(row.get_attribute('data-bye-state'), 'shortfall')
            self.assertIn('Example R 1 is on bye in RB.', row.inner_text())
            self.assertIn('Example S 1 is on bye in Superflex.', row.inner_text())
            self.assertEqual(row.locator('[data-bye-move]').count(), 0)
            self.assertIn('leaves Superflex unfilled', row.inner_text())
            extra = dict(id='1-x', player_id='1-x', name='Example X 1', position=None,
                         fantasy_positions=[], roster_slot='Bench', status='Active')
            data['teams'][0]['players'].append(extra)
            data['players']['1-x'] = dict(extra)
            install_schedule(service, data, now, byes={'1-r', '1-s'})
            row = self._render_week(page)
            self.assertEqual(row.get_attribute('data-bye-state'), 'unknown')
            self.assertEqual(row.locator('[data-bye-starter]').count(), 2)
            self.assertEqual(row.locator('[data-bye-move]').count(), 0)
            self.assertNotIn('unfilled', row.inner_text())
            data['players']['1-x'].update(position='QB', fantasy_positions=['QB'])
            install_schedule(service, data, now, byes={'1-r', '1-s'})
            row = self._render_week(page)
            self.assertEqual(row.get_attribute('data-bye-state'), 'covered')
            self._verify_moves(row, data, {'1-r', '1-s'}, {1: '1-bq', 3: '1-x'})
            install_schedule(service, data, now, byes={'1-r', '1-s'}, missing={(9, 2)})
            row = self._render_week(page)
            self.assertEqual(row.get_attribute('data-bye-state'), 'unknown')
            self.assertEqual(row.locator('[data-bye-move]').count(), 0)

    def test_rendered_changed_slots_and_legacy_read_models_are_withheld(self):
        fixture, data, service, now = self._owner_fixture(bench_position='RB')
        profile = install_schedule(service, data, now, byes={'1-w'})
        with phone(fixture) as page:
            row = self._render_week(page)
            self.assertIn('Example W 1 is on bye in FLEX.', row.inner_text())
            current = profile['upcoming_byes']['1']
            profile['upcoming_byes']['1'] = current['weeks']
            page.reload()
            self.assertIn('coverage is unavailable', page.locator('#upcoming-byes').inner_text())
            profile['upcoming_byes']['1'] = current
            by_id = {p['id']: p for p in data['teams'][0]['players']}
            by_id['1-w']['starter_index'], by_id['1-s']['starter_index'] = 3, 2
            page.reload()
            self.assertIn('coverage is unavailable', page.locator('#upcoming-byes').inner_text())
            install_schedule(service, data, now, byes={'1-w'})
            row = self._render_week(page)
            self.assertIn('Example W 1 is on bye in Superflex.', row.inner_text())
            self._verify_moves(row, data, {'1-w'}, {3: '1-bq'})
