"""Actual account/league routes and shared-cookie collisions, no image archives."""
import json
from urllib.parse import urlsplit
import unittest
from tests import test_product_browser_journey as journeys


class MyTeamFinalBrowserTests(journeys.ProductBrowserJourneyTests):
    viewports = ({'width': 320, 'height': 432}, {'width': 320, 'height': 844},
                 {'width': 375, 'height': 667}, {'width': 390, 'height': 844},
                 {'width': 1280, 'height': 900})

    def configure_data(self, data, league):
        if not hasattr(self, 'statuses'):
            self.statuses = {}
        expected = {'QB': 'Questionable', 'RB': 'Active', 'WR': 'IR', 'TE': None}
        for player in data['teams'][0]['players']:
            source = data['players'][player['id']]
            source.update(status=expected[player['position']], injury_status=None)
            player.pop('status', None)
            player.pop('injury_status', None)
            if player['position'] == 'QB':
                source.update(injury_status='Questionable', status='Active')
                player['status'] = 'Active'
            if player['position'] == 'TE' and player['id'].endswith('-8'):
                player['position'] = source['position'] = 'K'
                source.update(injury_status='Out')
            self.statuses[(league, player['id'])] = source.get('injury_status') or source.get('status')

    def configure_context(self, context):
        from src.core.intelligence.team_strength import prepare_for_data
        from unittest.mock import patch
        data = context.data
        data['league']['settings'] = {'leg': 1, 'playoff_week_start': 14}
        data['league']['scoring_settings'] = data['scoring_settings']
        payloads = {week: [{'player_id': pid, 'season': 2026, 'week': week,
                          'player': {'position': player['position']}, 'stats': {'rec': 5, 'pass_yd': 200}}
                         for pid, player in data['players'].items()] for week in (1, 2)}
        context.projection.publish_horizon(payloads, data=data, league_id=context.league_id, season=2026, current_week=1)
        with patch('services.global_evidence.retained_global_evidence', return_value=None):
            prepare_for_data(context.projection, data, bye_evidence={'season': 2026, 'reference': 'controlled schedule', 'player_weeks': {'1-QB-0': 2}})

    def audit_page(self, page, path, viewport):
        origin = f'{urlsplit(page.url).scheme}://{urlsplit(page.url).netloc}'
        if path == '/teams/1':
            page.get_by_role('link', name='View full roster', exact=True).click()
            cards = page.locator('#full-roster .thq-player')
            self.assertEqual(cards.count(), 10)
            for card in cards.all():
                identity = urlsplit(card.locator('a[href^="/players/"]').get_attribute('href')).path.split('/')[-1]
                league = json.loads(page.locator('[data-my-team-context]').get_attribute('data-my-team-context'))['league_id']
                status = self.statuses[(league, identity)]
                if status:
                    self.assertIn(status, card.inner_text())
                    self.assertNotIn('Status unavailable', card.inner_text())
                else:
                    self.assertIn('Status unavailable', card.inner_text())
            page.locator('#my-team-advanced').evaluate('e=>e.open=true')
            page.locator('.thq-starters').locator('xpath=..').evaluate('e=>e.open=true')
            starter = page.locator('.thq-starters a[href^="/players/"]').first
            self.assertIn('from_section=my-team-advanced', starter.get_attribute('href'))
            starter.press('Enter')
            page.wait_for_load_state('domcontentloaded')
            page.get_by_role('link', name='← Back to My Team intelligence', exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            self.assertTrue(page.locator('#my-team-advanced').evaluate('e=>e.open'))
            for selector in ('.thq-optimal a[href^="/players/"]', '.thq-depth a[href^="/players/"]'):
                link = page.locator(selector).first
                if not link.count():
                    continue
                self.assertIn('from_section=my-team-advanced', link.get_attribute('href'))
                link.locator('xpath=ancestor::details').evaluate_all('rows=>rows.forEach(e=>e.open=true)')
                link.click()
                page.wait_for_load_state('domcontentloaded')
                page.get_by_role('link', name='← Back to My Team intelligence', exact=True).click()
                page.wait_for_load_state('domcontentloaded')
                self.assertTrue(page.locator('#my-team-advanced').evaluate('e=>e.open'))

        elif path == '/trades/create':
            page.locator('#trade-sent-board input[type=search]').wait_for()
            for old, new in (('REBUILD', 'WIN NOW'), ('WIN NOW', 'REBUILD')):
                page.locator('#trade-strategy').select_option(old)
                second = page.context.new_page()
                try:
                    second.goto(origin + '/teams/1', wait_until='domcontentloaded')
                    second.locator('#my-team-strategy').select_option(new)
                    shared = second.evaluate('document.cookie')
                    # Do not rely on focus delivery: ordinary edits must reconcile too.
                    page.locator('#trade-partner').select_option('2')
                    self.assertEqual(page.evaluate('document.cookie'), shared)
                    self.assertEqual(page.locator('#trade-strategy').input_value(), new)
                    button = page.locator('#trade-sent-board button[data-asset-id]').first
                    button.click()
                    self.assertEqual(page.evaluate('document.cookie'), shared)
                    page.reload(wait_until='domcontentloaded')
                    page.locator('#trade-sent-board input[type=search]').wait_for()
                    self.assertEqual(page.locator('#trade-strategy').input_value(), new)
                    second.reload(wait_until='domcontentloaded')
                    self.assertEqual(second.locator('#my-team-strategy').input_value(), new)
                    key = page.evaluate("Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))")
                    saved = json.loads(page.evaluate('(k)=>sessionStorage.getItem(k)', key))
                    self.assertEqual(saved['strategy'], new)
                    self.assertEqual(saved['protectedAssets'], [])
                finally:
                    second.close()
            page.goto(origin + path, wait_until='domcontentloaded')


class RetainedStrategyBrowserTests(unittest.TestCase):
    def test_new_intent_qualifies_assessment_without_overwriting_package_or_cookie(self):
        from tests.test_trade_calculator_browser import CalculatorBrowserTests
        fixture = CalculatorBrowserTests()
        fixture.setUp()
        fixture.data['workspace_context'].update(league_id='fixture', roster_id=1, strategy_scope='fixture-session')
        with fixture.fixture.page(workspace=fixture.data, api=fixture.balancing) as (page, requests):
            fixture.build(page)
            page.locator('#trade-strategy').locator('xpath=ancestor::details').evaluate_all('rows=>rows.forEach(e=>e.open=true)')
            page.select_option('#trade-strategy', 'REBUILD')
            page.click('#trade-run')
            page.locator('#trade-result [data-reevaluate]').wait_for() if page.locator('#trade-result [data-reevaluate]').count() else page.get_by_text('This spends depth.', exact=False).first.wait_for()
            original = fixture.state(page)['currentProposal']
            second = page.context.new_page()
            try:
                second.goto('https://dtos.test/trades/create', wait_until='domcontentloaded')
                second.locator('#trade-partner option[value="2"]').wait_for(state='attached')
                second.select_option('#trade-strategy', 'WIN NOW')
                shared = second.evaluate('document.cookie')
                page.evaluate("window.dispatchEvent(new Event('focus'))")
                self.assertEqual(page.input_value('#trade-strategy'), 'WIN NOW')
                self.assertIn('strategy changed', page.locator('#trade-result').inner_text().lower())
                self.assertIn('This spends depth.', page.locator('#trade-result').inner_text())
                self.assertTrue(page.get_by_role('button', name='Reevaluate Trade', exact=True).is_visible())
                self.assertEqual(fixture.state(page)['currentProposal'], original)
                self.assertEqual(page.evaluate('document.cookie'), shared)
                page.click('#trade-balance-offer')
                page.locator('.tw-offer button.tw-next-action').first.wait_for()
                self.assertEqual(page.evaluate('document.cookie'), shared)
                page.locator('.tw-offer button.tw-next-action').first.click()
                self.assertEqual(page.evaluate('document.cookie'), shared)
                page.get_by_role('button', name='Adopt alternative', exact=True).click()
                self.assertEqual(page.evaluate('document.cookie'), shared)
                self.assertEqual(page.input_value('#trade-strategy'), 'WIN NOW')
                self.assertEqual(requests[-1][1]['strategy'], 'WIN NOW')
            finally:
                second.close()


if __name__ == "__main__":
    unittest.main()
