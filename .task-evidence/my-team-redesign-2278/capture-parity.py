"""Render the same disposable prepared inputs on both trees and retain semantic reads."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from services.matchup_season import METHOD
from src.core.intelligence.season_calendar import season_calendar
from src.core.player_value_projection.sleeper_actuals import scoring_identity
from src.core.intelligence import sleeper_membership_verified
from tests.lineup_review_fixture import authenticated_prepared
from tests import test_bye_pickups
from tests.test_upcoming_bye_moves import install_schedule, phone

OUTPUT = Path(os.environ['MY_TEAM_EVIDENCE'])
CANDIDATE = os.environ['MY_TEAM_TREE'] == 'candidate'
MOMENT = datetime.fromisoformat(os.environ['MY_TEAM_MOMENT'])


class FixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return MOMENT.astimezone(tz) if tz else MOMENT.replace(tzinfo=None)


def clean(value):
    value = re.sub(r'\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?', '<timestamp>', value)
    value = re.sub(r'\b(?:\d+ minutes? ago|less than a minute ago)\b', '<elapsed>', value)
    return ' '.join(value.split())


def details(page, selector):
    node = page.locator(selector)
    node.evaluate('e => { if (e.tagName === "DETAILS") e.open = true; for (const d of e.querySelectorAll("details")) d.open = true; }')
    if selector == '#my-team-outlook':
        text = node.evaluate('''element => {
            const rosterNavigation = element.querySelector('nav[aria-label="Roster sections"]');
            if (rosterNavigation) rosterNavigation.style.display = 'none';
            const text = element.innerText;
            if (rosterNavigation) rosterNavigation.style.removeProperty('display');
            return text;
        }''')
    else:
        text = node.inner_text()
    return clean(text)


def native_season(data):
    league = data['league']
    league['settings']['num_teams'] = len(data['teams'])
    history = data['season_matchups']
    history.update(
        league_id=league['league_id'], season=league['season'], methodology=METHOD,
        scoring_fingerprint=scoring_identity(league['scoring_settings']),
        calendar_reference=season_calendar(league)['reference'], observed_at=MOMENT.isoformat(),
        semantic_generation='matched-rendered-prepared-season',
    )
    for week in range(1, 8):
        history['weeks'][str(week)] = dict(availability='available', rows=[
            dict(roster_id=1, points=105 + week), dict(roster_id=2, points=106 + week)])


def show_week(page):
    if CANDIDATE:
        page.get_by_role('navigation', name='My Team sections').get_by_role('link', name='Byes').click()
        page.locator('#bye-week-9 > summary').click()
    else:
        page.locator('#bye-week-details > summary').click()
    return page.locator('[data-bye-week="9"]')


def bye_summary(week):
    evidence = week.evaluate(r'''el => ({
      state: el.dataset.byeState,
      moves: [...el.querySelectorAll('[data-bye-move]')].map(x => [x.dataset.slotIndex, x.dataset.byeMove]),
      absent: [...el.querySelectorAll('[data-bye-starter]')].map(x => [x.dataset.slotIndex,x.dataset.byeStarter]),
      qualification: el.innerText.split('\n').filter(x => /Sleeper listed|unconfirmed availability|status checked|complete projected|unfilled|only if all/.test(x))
    })''')
    evidence['qualification'] = [clean(line) for line in evidence['qualification']]
    return evidence


class Capture(unittest.TestCase):
    def test_matched_views(self):
        self.enterContext(patch('tests.lineup_review_fixture.datetime', FixtureClock))
        fixture, data, service, now = authenticated_prepared(self, empty=False)
        now = MOMENT
        native_season(data)
        data['transactions'] = [
            dict(transaction_id='my-team-proof-waiver', type='waiver', status='complete',
                 roster_ids=[1], created=1790000000000, adds={'1-q': 1}, settings={'waiver_bid': 0}),
            dict(transaction_id='my-team-proof-failed', type='drop', status='failed',
                 roster_ids=[1], created=1790000000001, drops={'1-r': 1}),
        ]
        active = data['teams'][0]
        active['picks_owned'] = [
            dict(season=2027, year=2027, round=1, original_roster_id=1, owner_roster_id=1),
            dict(season=2027, year=2027, round=1, original_roster_id=2, owner_roster_id=1)]
        result = {}
        with phone(fixture) as page:
            for width, height in [(320, 432), (390, 844), (1280, 900)]:
                page.set_viewport_size(dict(width=width, height=height))
                self.assertEqual(page.goto('https://dtos.test/teams/1').status, 200)
                shortcut = page.get_by_role('link', name='View full roster', exact=True)
                if CANDIDATE:
                    self.assertLess(shortcut.bounding_box()['y'], height * 1.5)
                    self.assertLess(page.locator('#full-roster .thq-player').first.bounding_box()['y'], 600)
                page.screenshot(path=str(OUTPUT / f'roster-{width}.png'))
                self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            result.update({
                'outlook': details(page, '#my-team-outlook'),
                'record': page.locator('.thq-header .thq-record-link').inner_text(),
                'depth': details(page, '#positional-depth'),
                'season_playoffs_and_coverage': details(page, '#season-so-far'),
                'roster': details(page, '#full-roster'),
            })
            page.locator('#my-team-advanced').evaluate('e=>e.open=true')
            result['franchise_activity'] = page.locator('.thq-timeline').inner_text()
            self.assertIn('1 added', result['franchise_activity'])
            self.assertIn('No completed roster move verified', result['franchise_activity'])
            result['history'] = page.locator('#my-team-advanced a').evaluate_all(
                'a=>a.filter(x=>x.pathname?.startsWith("/history")||x.pathname==="/front-offices").map(x=>[x.pathname,x.innerText])')
            if CANDIDATE:
                page.locator('.thq-tabs a[href="#team-lineup"]').click()
            page.locator('.thq-starters').locator('..').evaluate('d=>d.open=true')
            result['submitted_lineup'] = details(page, '.thq-starters')
            result['lineup'] = details(page, '[aria-label="Lineup review"]')
            result['lineup'] = re.sub(r'First affected game locks .*?\. ', '', result['lineup'])
            result['lineup_recheck'] = clean(page.locator('#lineup-recheck').inner_text())
            page.screenshot(path=str(OUTPUT / 'lineup-1280.png'), full_page=False)
            if CANDIDATE:
                page.locator('.thq-tabs a[href="#team-picks"]').click()
            result['draft_capital'] = details(page, '#draft-capital')

            install_schedule(service, data, now, byes={'1-r'})
            for width, height in [(320, 432), (390, 844), (1280, 900)]:
                page.set_viewport_size(dict(width=width, height=height))
                page.goto('https://dtos.test/teams/1')
                week = show_week(page)
                self.assertTrue(week.is_visible())
                page.evaluate("scrollTo(0,0)")
                page.screenshot(path=str(OUTPUT / f'byes-{width}.png'))
                week.screenshot(path=str(OUTPUT / f'bye-details-{width}.png'))
                self.assertEqual(page.evaluate('document.documentElement.scrollWidth'), width)
            result['covered_chain'] = bye_summary(week)
            data['players']['1-bq']['injury_status'] = 'IR'
            install_schedule(service, data, now, byes={'1-r'})
            page.goto('https://dtos.test/teams/1')
            week = show_week(page)
            result['conditional_chain'] = bye_summary(week)
            week.screenshot(path=str(OUTPUT / 'conditional-bye.png'))

        example = test_bye_pickups.ByePickupTests()
        self.addCleanup(example.doCleanups)
        pickup_fixture, pickup_data, pickup_service, _ = example.setup_league(
            slots=['QB', 'RB', 'FLEX', 'RB', 'BN'], bench_position='QB')
        example.add_players(pickup_data, pickup_service, now)
        team = pickup_data['teams'][0]
        team['sleeper_membership_verified'] = sleeper_membership_verified(
            dict(players=[p['id'] for p in team['players']], reserve=None, taxi=None))
        install_schedule(pickup_service, pickup_data, now, byes={'1-r'}, unknown_clubs={'1-bq'})
        active_market = Mock(league_id='league-1')
        active_market.compatible_prepared_inputs.return_value = True
        active_market.by_id = {'player:1-r': {'values': {'market_value': 0}}}
        example.market_cache.current.return_value = active_market
        with phone(pickup_fixture) as page:
            page.goto('https://dtos.test/teams/1')
            week = show_week(page)
            result['shortfall'] = bye_summary(week)
            page.get_by_role('link', name='Find Week 9', exact=False).click()
            result['pickups'] = details(page, '#bye-pickup-results')
            runner = page.locator('#bye-pickup-results article').filter(has_text='Free Runner')
            runner.get_by_role('link', name='Compare a drop').click()
            runner.get_by_label('Player to drop').select_option('1-r')
            runner.get_by_role('button', name='Preview add and drop').click()
            result['add_drop'] = details(page, '#bye-drop-comparison')
            self.assertIn('0 / 1,000', result['add_drop'])
        (OUTPUT / 'semantic-outputs.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
