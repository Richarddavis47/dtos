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
from src.core.intelligence import pickup_roster_space, sleeper_membership_verified
from tests.lineup_review_fixture import authenticated_prepared
from tests.test_upcoming_bye_moves import install_schedule, phone


class ByePickupTests(unittest.TestCase):
    def setup_league(self, *, roster_age=timedelta(), **options):
        import dtos_app

        fixture, data, service, now = authenticated_prepared(self, empty=False, **options)
        state = {'data': data, 'last_sync': (now - roster_age).isoformat()}
        cache = Mock()
        cache.current.return_value = None
        self.market_cache = cache
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
            page.goto('https://dtos.test/teams/1#team-byes')
            page.locator('#bye-week-9 > summary').press('Enter')
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
            page.wait_for_url('**/teams/1#team-byes')
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
            page.goto('https://dtos.test/teams/1#team-byes')
            details = page.locator('#bye-week-9')
            details.locator('summary').click()
            self.assertTrue(details.locator('.thq-bye-content').is_visible())
            page.get_by_role('link', name='Find Week 9 RB cover').tap()
            page.wait_for_url('**/market?**')
            card = page.locator('#bye-pickup-results article').filter(has_text='Free Receiver')
            copy = card.inner_text()
            self.assertIn('Conditional cover for one RB opening', copy)
            self.assertIn('Move Example W 1 from FLEX to RB.', copy)
            self.assertIn('Start Free Receiver at FLEX.', copy)
            self.assertIn('Sleeper listed Example W 1 as on injured reserve', copy)
            page.locator('#dtos-back').click()
            page.wait_for_url('**/teams/1#team-byes')
            page.locator('#bye-week-9[open] > .thq-bye-content').wait_for()
            page.reload()
            self.assertFalse(details.locator('.thq-bye-content').is_visible())
            details.locator('summary').press('Enter')
            self.assertTrue(details.locator('.thq-bye-content').is_visible())

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

    def test_roster_space_preserves_native_membership_uncertainty(self):
        observed = dict(players=['1', '2'], reserve=None, taxi=['2'], starters=['1'])
        self.assertTrue(sleeper_membership_verified(observed))
        self.assertTrue(sleeper_membership_verified(dict(players=[], reserve=None, taxi=None)))
        for bad in (
            {key: value for key, value in observed.items() if key != 'taxi'},
            dict(observed, players=None),
            dict(observed, players=['1', 1, '2']),
            dict(observed, reserve=['2']),
            dict(observed, taxi=['3']),
            dict(observed, starters=['2']),
        ):
            with self.subTest(bad=bad):
                self.assertFalse(sleeper_membership_verified(bad))
        team = dict(sleeper_membership_verified=True, players=[dict(id='1', roster_slot='Starter')])
        self.assertIn('roster limit', pickup_roster_space({'roster_positions': ['QB', 'new slot']}, team)['reason'])
        self.assertIn('occupy', pickup_roster_space({'roster_positions': ['QB', 'BN']},
                                                    dict(team, players=[{'id': '1'}]))['reason'])

    def test_roster_space_and_return_on_phone(self):
        cases = (
            ('open', ['QB', 'RB', 'FLEX', 'RB', 'BN', 'BN'], True, 'Open active spot · 5 of 6'),
            ('full', ['QB', 'RB', 'FLEX', 'SUPER_FLEX', 'BN'], True, 'Make room before adding · 5 of 5'),
            ('unknown', ['QB', 'RB', 'FLEX', 'RB', 'BN'], False, 'Could not confirm an open spot'),
        )
        for label, slots, verified, expected in cases:
            with self.subTest(state=label):
                fixture, data, service, now = self.setup_league(slots=slots, bench_position='RB')
                team = data['teams'][0]
                data['league']['settings'].update(reserve_slots=2, taxi_slots=2)
                extra = dict(id='1-ir', name='Injured Reserve Fixture', position='RB',
                             fantasy_positions=['RB'], roster_slot='IR')
                team['players'].append(extra)
                data['players'][extra['id']] = dict(extra)
                # One IR and two taxi vacancies are listed by the league. The
                # occupied IR spot is excluded, and the vacancies add no space.
                native = dict(players=[row['id'] for row in team['players']], reserve=[extra['id']])
                if verified:
                    native['taxi'] = None
                team['sleeper_membership_verified'] = sleeper_membership_verified(native)
                self.add_players(data, service, now)
                install_schedule(service, data, now, byes={'1-r', '1-w'})
                with phone(fixture) as page:
                    page.goto('https://dtos.test/teams/1#team-byes')
                    details = page.locator('#bye-week-9')
                    details.locator('summary').press('Enter')
                    page.get_by_role('link', name='Find Week 9', exact=False).tap()
                    page.wait_for_url('**/market?**')
                    results = page.locator('#bye-pickup-results')
                    runner = results.locator('article').filter(has_text='Free Runner')
                    copy = runner.inner_text()
                    self.assertIn(expected, copy)
                    self.assertIn('Unrostered in this league', copy)
                    self.assertIn('Sleeper projection: 3.50 pts.', copy)
                    if verified:
                        self.assertIn('IR and taxi vacancies do not count as active spots.', results.inner_text())
                    else:
                        self.assertIn('could not confirm which players occupy', results.inner_text())
                    self.assertIn('waivers or locks', results.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                    if directory := os.environ.get('DTOS_BYE_PICKUP_SCREENSHOTS'):
                        destination = Path(directory)
                        destination.mkdir(parents=True, exist_ok=True)
                        results.screenshot(path=str(destination / f'roster-space-{label}-390.png'))
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**/teams/1#team-byes')
                    details.locator('.thq-bye-content').wait_for()

    def test_ir_blockers_and_active_space_on_phone(self):
        cases = (
            ('last-spot', 1, 'Active', None, 1, timedelta(), 'last open active spot'),
            ('room-left', 2, 'Active', 'Out', 0, timedelta(), '1 active spot would remain'),
            ('out-allowed', 1, 'Active', 'Out', 1, timedelta(), None),
            ('pup', 1, 'Inactive', 'PUP', 0, timedelta(), None),
            ('stale', 1, 'Active', None, 1, timedelta(hours=8), 'player status check is stale'),
            ('stale-roster', 1, 'Active', None, 1, timedelta(), 'roster check is stale'),
            ('missing', 1, None, None, 1, timedelta(), 'could not confirm the Sleeper status for Example IR 1'),
            ('missing-rule', 1, 'Active', 'Out', None, timedelta(), 'could not confirm the league’s IR rule for Example IR 1'),
            ('conflicting', 1, 'IR', 'Out', 0, timedelta(), 'could not confirm the Sleeper status for Example IR 1'),
        )
        for label, open_spots, status, injury, allow_out, age, expected in cases:
            with self.subTest(case=label):
                fixture, data, service, now = self.setup_league(
                    slots=['QB', 'RB', 'FLEX', 'RB'] + ['BN'] * (open_spots + 1),
                    bench_position='RB',
                    roster_age=timedelta(hours=8) if label == 'stale-roster' else timedelta(),
                )
                settings = data['league']['settings']
                settings['reserve_slots'] = 1
                if allow_out is not None:
                    settings['reserve_allow_out'] = allow_out
                team = data['teams'][0]
                team['players'].append(dict(id='1-ir', name='Example IR 1', position='RB', roster_slot='IR'))
                team['sleeper_membership_verified'] = sleeper_membership_verified(dict(
                    players=[row['id'] for row in team['players']], reserve=['1-ir'], taxi=None))
                data['players']['1-ir'] = dict(
                    player_id='1-ir', full_name='Example IR 1', status=status, injury_status=injury)
                self.add_players(data, service, now)
                data['players_fetched_at'] = (now - age).isoformat()
                install_schedule(service, data, now, byes={'1-r', '1-w'})
                with phone(fixture) as page:
                    page.goto('https://dtos.test/teams/1#team-byes')
                    page.locator('#bye-week-9 > summary').press('Enter')
                    page.get_by_role('link', name='Find Week 9', exact=False).tap()
                    page.wait_for_url('**/market?**')
                    results = page.locator('#bye-pickup-results')
                    card = results.locator('article').filter(has_text='Free Runner')
                    copy = card.inner_text()
                    if directory := os.environ.get('DTOS_BYE_PICKUP_SCREENSHOTS'):
                        destination = Path(directory)
                        destination.mkdir(parents=True, exist_ok=True)
                        results.screenshot(path=str(destination / f'ir-{label}-390.png'))
                    self.assertIn(f'Open active spot · 5 of {5 + open_spots} active spots used.', copy)
                    self.assertIn('Unrostered in this league', copy)
                    self.assertEqual('Sleeper IR blocker' in copy, label in ('last-spot', 'room-left'))
                    if expected:
                        self.assertIn(expected, copy)
                    if label == 'last-spot':
                        self.assertIn('make room for this pickup', copy)
                    self.assertIn('waivers or locks', results.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                    page.locator('#dtos-back').click()
                    page.wait_for_url('**/teams/1#team-byes')
                    page.locator('#bye-week-9[open] > .thq-bye-content').wait_for()

    def test_compare_drop_rechecks_the_target_week_lineup_on_phone(self):
        fixture, data, service, now = self.setup_league(
            slots=['QB', 'RB', 'FLEX', 'RB', 'BN'], bench_position='QB')
        self.add_players(data, service, now)
        league, team = data['league'], data['teams'][0]
        league['settings']['reserve_slots'] = 1
        team['players'].append(dict(id='1-ir', name='Example IR', position='RB', roster_slot='IR'))
        team['sleeper_membership_verified'] = sleeper_membership_verified(dict(
            players=[p['id'] for p in team['players']], reserve=['1-ir'], taxi=None))
        data['players']['1-ir'] = dict(player_id='1-ir', full_name='Example IR', status='Active', injury_status=None)
        data['players']['1-s']['injury_status'] = 'Questionable'
        install_schedule(service, data, now, byes={'1-r'}, unknown_clubs={'1-bq'})
        active_market = Mock(league_id='league-1')
        active_market.compatible_prepared_inputs.return_value = True
        active_market.by_id = {'player:1-r': {'values': {'market_value': 0}}}
        self.market_cache.current.return_value = active_market

        with phone(fixture) as page:
            page.goto('https://dtos.test/teams/1#team-byes')
            page.locator('#bye-week-9 > summary').press('Enter')
            page.get_by_role('link', name='Find Week 9', exact=False).tap()
            runner = page.locator('#bye-pickup-results article').filter(has_text='Free Runner')
            runner.get_by_role('link', name='Compare a drop').tap()
            comparison = runner.locator('#bye-drop-comparison')
            choice = comparison.get_by_label('Player to drop')
            choice.wait_for()
            self.assertEqual(set(choice.locator('option').evaluate_all('(rows) => rows.map(row => row.value)')),
                             {'', '1-q', '1-r', '1-w', '1-s', '1-bq'})
            self.market_cache.current.assert_not_called()

            for outgoing, expected in (
                ('1-r', ('RB 1 gap filled', 'All starting slots covered', '0 / 1,000')),
                ('1-w', ('RB 1 gap filled', 'Newly uncovered · FLEX', 'compatible prepared price is unavailable')),
                ('1-q', ('RB 1 gap filled', 'Could not confirm cover for previously filled slots · QB',
                         'Missing schedule or eligibility information')),
            ):
                with self.subTest(outgoing=outgoing):
                    choice.select_option(outgoing)
                    comparison.get_by_role('button', name='Preview add and drop').tap()
                    page.wait_for_url(f'**compare_drop={outgoing}#bye-drop-comparison')
                    comparison.get_by_text('Outgoing player’s Market value', exact=True).wait_for()
                    copy = comparison.inner_text()
                    for text in expected:
                        self.assertIn(text, copy)
                    self.assertIn('After the swap · 5 of 5 active spots used', copy)
                    self.assertIn('The IR blocker still needs to be resolved in Sleeper.', copy)
                    self.assertIn('would still require 1 more active spot', copy)
                    self.assertIn('Sleeper listed Example S 1 as questionable', copy)
                    self.assertIn('Sleeper IR blocker', runner.inner_text())
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
                    comparison.locator('summary').press('Enter')
                    self.assertIn('RB 1 · Free Runner', comparison.locator('details').inner_text())
                    if directory := os.environ.get('DTOS_BYE_PICKUP_SCREENSHOTS'):
                        comparison.screenshot(path=str(Path(directory, f'drop-{outgoing}-390.png')))
            page.locator('#dtos-back').click()
            page.wait_for_url('**/teams/1#team-byes')
            page.locator('#bye-week-9[open] > .thq-bye-content').wait_for()

        client = fixture.f.f.client
        preview = '/market?bye_week=9&market_league=league-1&season=2026&from_team=1&compare_pickup=free-rb'
        forged = client.get(preview + '&compare_drop=1-ir').text
        self.assertIn('Choose a confirmed player from an active roster spot.', forged)
        self.assertNotIn('Outgoing player’s Market value', forged)
        active_market.compatible_prepared_inputs.return_value = False
        self.assertIn('A compatible prepared price is unavailable',
                      client.get(preview + '&compare_drop=1-r').text)

    def test_compare_drop_can_remove_the_only_superflex_chain(self):
        fixture, data, service, now = self.setup_league(bench_position='QB')
        self.add_players(data, service, now)
        for pid, pos in (('1-w', 'RB'), ('1-s', 'QB')):
            row = next(p for p in data['teams'][0]['players'] if p['id'] == pid)
            row.update(position=pos, fantasy_positions=[pos])
            data['players'][pid].update(position=pos, fantasy_positions=[pos])
        data['teams'][0]['sleeper_membership_verified'] = True
        data['players']['free-wr'] = dict(player_id='free-wr', full_name='Free Receiver', team='X02',
                                         position='WR', fantasy_positions=['WR'], status='Active')
        install_schedule(service, data, now, byes={'1-r'})
        client = fixture.f.f.client
        response = client.get('/market?bye_week=9&market_league=league-1&season=2026&from_team=1'
                              '&compare_pickup=free-wr&compare_drop=1-w')
        self.assertEqual(response.status_code, 200)
        self.assertIn('This drop removes a player from the pickup-only plan.', response.text)
        self.assertIn('Original RB gap stays open.', response.text)
        self.assertIn('FLEX · Free Receiver', response.text)
