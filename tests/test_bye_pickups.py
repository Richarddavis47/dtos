"""Prepared bye gaps through the authenticated My Team and Market routes."""

from datetime import timedelta
from types import SimpleNamespace
from pathlib import Path
import os
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
import unittest

from routes.market import create_market_router
from routes.navigation import create_navigation_router
from services.market_navigation import market_return
from tests.lineup_review_fixture import authenticated_prepared
from tests.test_upcoming_bye_moves import install_schedule, phone


class ByePickupTests(unittest.TestCase):
    def setup_league(self, **options):
        import dtos_app

        fixture, data, service, now = authenticated_prepared(self, empty=False, **options)
        state = {'data': data}
        cache = Mock()
        context = SimpleNamespace(state=state, league_id='league-1', projection=service, market=cache)
        fixture.f.f.client.app.include_router(create_navigation_router())
        fixture.f.f.client.app.include_router(create_market_router(
            require_data=lambda: data, state=state, league_id='league-1', page=dtos_app.page,
            context_resolver=lambda: context,
        ))
        self.addCleanup(cache.get.assert_not_called)
        return fixture, data, service, now

    def add_players(self, data, service, now):
        def add(pid, name, pos, *, team='X02', status='Active'):
            data['players'][pid] = dict(id=pid, player_id=pid, full_name=name, name=name, team=team,
                                        position=pos, fantasy_positions=[pos], status=status)

        add('free-rb', 'Free Runner', 'RB')
        add('free-qb', 'Free Quarterback', 'QB')
        add('free-te', 'Unprojected Tight End', 'TE')
        add('bye-te', 'Off This Week', 'TE', team='BUF')
        add('out-rb', 'Currently Out', 'RB', status='Out')
        def points(week, yards):
            return dict(player_id='free-rb', week=week, season=2026, team='X02', opponent='BUF',
                        player=dict(position='RB', fantasy_positions=['RB']), updated_at=now.isoformat(),
                        stats={'rush_yd': yards})

        service.publish_horizon({8: [points(8, 120)], 9: [points(9, 35)]}, data=data,
                                league_id='league-1', season=2026, current_week=8)

    def test_phone_flex_gap_target_week_and_back(self):
        fixture, data, service, now = self.setup_league(slots=['QB', 'RB', 'FLEX', 'RB', 'BN'])
        self.add_players(data, service, now)
        install_schedule(service, data, now, byes={'1-w'})
        with phone(fixture) as page:
            page.goto('https://dtos.test/teams/1')
            action = page.get_by_role('link', name='Find Week 9 FLEX cover')
            href = action.get_attribute('href')
            self.assertEqual(parse_qs(urlsplit(href).query)['availability'], ['day_traders_free_agent'])
            self.assertEqual(market_return(href, 'league-1', 'league-1'), href)
            self.assertIsNone(market_return(href, 'league-1', 'other-league'))
            directory = os.environ.get('DTOS_BYE_PICKUP_SCREENSHOTS')
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)
                page.locator('#upcoming-byes').screenshot(path=str(Path(directory, 'my-team-390.png')))
            with patch.object(service, 'week_snapshot', side_effect=AssertionError('Market must use the prepared shortlist')):
                action.tap()
                page.wait_for_url('**/market?**')
            results = page.locator('#bye-pickup-results')
            copy = results.inner_text()
            self.assertIn('Free Runner', copy)
            self.assertIn('Sleeper projection: 3.50 pts.', copy)
            self.assertNotIn('12.00 pts', copy)
            self.assertIn('Unprojected Tight End', copy)
            self.assertIn('Sleeper projection unavailable.', copy)
            self.assertIn('waivers or locks', copy)
            self.assertNotIn('Free Quarterback', copy)
            self.assertNotIn('Off This Week', copy)
            self.assertNotIn('Currently Out', copy)
            self.assertNotIn('Example', copy)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            if directory:
                results.screenshot(path=str(Path(directory, 'market-390.png')))
            page.locator('#dtos-back').click()
            page.wait_for_url('**/teams/1')
            action.wait_for()

    def test_superflex_plan_each_unrostered_candidate_fills_only_one_of_two_openings(self):
        fixture, data, service, now = self.setup_league(bench_position='RB')
        self.add_players(data, service, now)
        install_schedule(service, data, now, byes={'1-q', '1-s', '1-w'})
        client = fixture.f.f.client
        response = client.get('/market?bye_week=9&market_league=league-1&season=2026&from_team=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('one pickup cannot fill them all', response.text)
        self.assertIn('Free Quarterback', response.text)
        self.assertIn('Can fill one Superflex opening', response.text)
        row = data['team_strength']['upcoming_byes']['1']['weeks'][0]
        self.assertEqual(len(row['unfilled']), 2)
        self.assertLessEqual(len(row['pickups']['candidates']), 6)

    def test_withholds_incomplete_ownership_stale_link_and_unknown_gap(self):
        fixture, data, service, now = self.setup_league(slots=['QB', 'RB', 'FLEX', 'RB', 'BN'])
        self.add_players(data, service, now)
        data['league']['total_rosters'] = 3
        install_schedule(service, data, now, byes={'1-w'})
        client = fixture.f.f.client
        url = '/market?bye_week=9&market_league=league-1&season=2026&from_team=1'
        self.assertIn('League ownership is incomplete', client.get(url).text)
        self.assertNotIn('Free Runner', client.get(url).text)
        self.assertIn('does not match a confirmed', client.get(url.replace('league-1', 'league-2')).text)
        self.assertIn('does not match a confirmed', client.get(url.replace('2026', '2025')).text)
        self.assertIn('does not match a confirmed', client.get(url.replace('from_team=1', 'from_team=2')).text)
        install_schedule(service, data, now, byes={'1-w'}, missing={(9, 1)})
        self.assertNotIn('Find Week 9', client.get('/teams/1').text)
        self.assertIn('does not match a confirmed', client.get(url).text)

    def chained_gap(self, *, injury=None, check_time=None, status='Active'):
        fixture, data, service, now = self.setup_league(bench_position='QB')
        self.add_players(data, service, now)
        for pid, position in [('1-w', 'RB'), ('1-s', 'QB')]:
            starter = next(player for player in data['teams'][0]['players'] if player['id'] == pid)
            starter.update(position=position, fantasy_positions=[position])
            data['players'][pid].update(position=position, fantasy_positions=[position])
        data['players']['1-w'].update(injury_status=injury, status=status)
        data['players']['free-wr'] = dict(id='free-wr', player_id='free-wr', full_name='Free Receiver',
                                         team='X02', position='WR', fantasy_positions=['WR'], status='Active')
        if check_time is not None:
            data['players_fetched_at'] = (now - check_time).isoformat()
        install_schedule(service, data, now, byes={'1-r'})
        return fixture

    def test_chained_pickup_names_injured_starter_and_back_preserves_week_details(self):
        fixture = self.chained_gap(injury='IR')
        with phone(fixture) as page:
            page.goto('https://dtos.test/teams/1')
            details = page.locator('#bye-week-details')
            details.locator('summary').click()
            self.assertTrue(details.locator('[data-bye-week="9"]').is_visible())
            page.get_by_role('link', name='Find Week 9 RB cover').tap()
            page.wait_for_url('**/market?**')
            card = page.locator('#bye-pickup-results article').filter(has_text='Free Receiver')
            copy = card.inner_text()
            self.assertIn('Conditional cover for one RB opening', copy)
            self.assertIn('Move Example W 1 from FLEX to RB.', copy)
            self.assertIn('Start Free Receiver at FLEX.', copy)
            self.assertIn('Sleeper listed Example W 1 as on injured reserve', copy)
            page.locator('#dtos-back').click()
            page.wait_for_url('**/teams/1')
            page.locator('#bye-week-details[open] [data-bye-week="9"]').wait_for()
            page.reload()
            self.assertFalse(details.locator('[data-bye-week="9"]').is_visible())
            details.locator('summary').press('Enter')
            self.assertTrue(details.locator('[data-bye-week="9"]').is_visible())

    def test_chained_pickup_support_tracks_fresh_stale_and_missing_status(self):
        cases = [
            ('Active', None, 'Can fill one RB opening by starting at FLEX'),
            ('Active', timedelta(hours=8), 'Player status check is stale'),
            (None, None, 'Example W 1 has unconfirmed availability.'),
        ]
        for status, check_time, expected in cases:
            with self.subTest(status=status, check_time=check_time):
                fixture = self.chained_gap(status=status, check_time=check_time)
                client = fixture.f.f.client
                response = client.get('/market?bye_week=9&market_league=league-1&season=2026&from_team=1')
                self.assertEqual(response.status_code, 200)
                receiver = response.text.split('>Free Receiver</a>', 1)[1].split('</article>', 1)[0]
                self.assertIn(expected, receiver)
                self.assertIn('Move Example W 1 from FLEX to RB.', receiver)
                self.assertIn('Start Free Receiver at FLEX.', receiver)
                self.assertEqual('Conditional cover' in receiver, status is None or check_time is not None)
