"""Actual authenticated routers, session intent and phone geometry; no captures."""
import json
from pathlib import Path
from starlette.staticfiles import StaticFiles
from routes.navigation import create_navigation_router
import unittest
from urllib.parse import urlsplit

from routes.historical_assets import create_historical_assets_router
from src.platform.league_context import current_league_context
from tests import test_product_browser_journey as journeys


class MyTeamIntelligenceBrowserTests(journeys.ProductBrowserJourneyTests):
    viewports = ({'width': 320, 'height': 432}, {'width': 320, 'height': 844},
                 {'width': 375, 'height': 667}, {'width': 390, 'height': 844},
                 {'width': 1280, 'height': 900})

    def configure_app(self, app, common):
        # Match deployed navigation readiness and static assets, not only page HTML.
        app.include_router(create_navigation_router())
        app.mount('/static', StaticFiles(directory=Path(__file__).resolve().parents[1] / 'static'))
        app.include_router(create_historical_assets_router(
            require_data=common['require_data'], page=common['page'], league_id='100',
            league_resolver=lambda: current_league_context().league_id))

    def configure_data(self, data, league):
        first, second = data['teams'][:2]
        first['picks_owned'] = [p for p in first['picks_owned'] if p['round'] != 1]
        acquired = next(p for p in second['picks_owned'] if p['round'] == 4)
        second['picks_owned'].remove(acquired)
        first['picks_owned'].append(dict(acquired, current_owner_id=1, is_traded=True))
        data['traded_picks'].append({'season': '2027', 'round': 4, 'roster_id': 2, 'owner_id': 1, 'previous_owner_id': 2})

    def audit_page(self, page, path, viewport):
        origin = page.url.split(path)[0] if path != '/' else page.url.rstrip('/')
        if path == '/teams/1':
            root = page.locator('[data-my-team-context]')
            context = json.loads(root.get_attribute('data-my-team-context'))
            self.assertIn(context['league_id'], ('100', '200', '300'))
            self.assertEqual(page.locator('#my-team-strategy').count(), 1)
            lead = page.locator('#my-team-outlook-lead').inner_text()
            self.assertNotIn('Biggest depth risk', lead)
            detail = page.locator('#my-team-outlook-evidence')
            summary = detail.locator('summary')
            page.keyboard.press('Tab')
            summary.focus()
            self.assertNotEqual(summary.evaluate('e => getComputedStyle(e).outlineStyle'), 'none')
            summary.press('Enter')
            self.assertIn('Depth and uncertainty', detail.inner_text())
            summary.press('Enter')
            self.assertIn('Surplus not established', page.locator('#positional-depth').text_content())
            roster = page.get_by_role('navigation', name='Roster sections').get_by_role('link', name='View full roster', exact=True)
            roster.focus()
            self.assertNotEqual(roster.evaluate('e => getComputedStyle(e).outlineStyle'), 'none')
            roster.press('Enter')
            self.assertTrue(page.locator('#my-team-roster').evaluate('e => e.open'))
            player = page.locator('#full-roster a[href^="/players/"]').first
            self.assertEqual(page.locator('#full-roster .thq-player a[href^="/players/"]').count(), 10)
            self.assertEqual(page.locator('#full-roster a[href^="/trades/shop"]').count(), 10)
            overlaps = page.locator('#full-roster .thq-player').evaluate_all('''rows => rows.filter(row => {
                const p=row.querySelector('.player-portrait'), t=row.querySelector('.player-summary-copy');
                if (!p || !t) return false;
                return p.getBoundingClientRect().right > t.getBoundingClientRect().left + .5;
            }).map(row => row.innerText)''')
            self.assertEqual(overlaps, [])
            player.press('Enter')
            page.wait_for_load_state('domcontentloaded')
            back = page.get_by_role('link', name='← Back to My Team roster', exact=True)
            self.assertEqual(back.get_attribute('href'), '/teams/1#full-roster')
            # Explicit return intent must override a closed saved disclosure,
            # including an old/missed asynchronous toggle publication.
            page.evaluate('''key => {
                const saved = JSON.parse(sessionStorage.getItem(key) || '{}');
                saved['my-team-roster'] = false;
                sessionStorage.setItem(key, JSON.stringify(saved));
            }''', 'dtos-my-team:' + context['binding'])
            back.click()
            page.wait_for_load_state('domcontentloaded')
            self.assertTrue(page.locator('#my-team-roster').evaluate('e => e.open'))
            pick = page.locator('#draft-capital a[href^="/picks/"]').first
            pick.click()
            page.wait_for_load_state('domcontentloaded')
            page.get_by_role('link', name='← Back to My Team draft capital', exact=True).click()
            page.wait_for_load_state('domcontentloaded')
            shop = page.locator('#draft-capital a[href*="asset_id=2027-R4-2"]')
            href = shop.get_attribute('href')
            self.assertIn('asset_id=2027-R4-2', href)
            shop.click()
            page.locator('#trade-sent-board input[type=search]').wait_for()
            page.wait_for_function("Object.keys(sessionStorage).some(k => k.startsWith('dtos-trade-workspace:') && JSON.parse(sessionStorage.getItem(k)).requiredOutgoingAsset === '2027-R4-2')")
            self.assertTrue(page.locator('#trade-target').is_visible())
            self.assertIn('Asset you are shopping', page.locator('#trade-target').inner_text())
            page.goto(origin + '/teams/1', wait_until='domcontentloaded')
        elif path == '/trades/create':
            ctx = page.evaluate("fetch('/api/trades/workspace').then(r => r.json())")
            # Use the server-authorized current workspace binding, never source list order.
            binding = ctx['workspace_context']
            expected = page.evaluate("key=>JSON.parse(sessionStorage.getItem(key)||'{}').strategy", "dtos-trade-workspace:" + binding['binding']) or ''
            self.assertEqual(page.locator('#trade-strategy').input_value(), expected)
            goal = 'WIN NOW' if binding['league_id'] == '200' else 'REBUILD'
            page.locator('#trade-strategy').select_option(goal)
            page.reload(wait_until='domcontentloaded')
            page.locator('#trade-sent-board input[type=search]').wait_for()
            self.assertEqual(page.locator('#trade-strategy').input_value(), goal)
            # Actual fresh primary entry clears both draft and contextual return state.
            page.locator('.manager-nav a[href="/trades"]').click()
            page.wait_for_url('**/trades')
            page.goto(origin + '/trades/create', wait_until='domcontentloaded')
            page.locator('#trade-sent-board input[type=search]').wait_for()
            self.assertEqual(page.locator('#trade-strategy').input_value(), '')
            fresh = page.context.new_page()
            try:
                fresh.goto(page.url, wait_until='domcontentloaded')
                fresh.locator('#trade-sent-board input[type=search]').wait_for()
                self.assertEqual(fresh.locator('#trade-strategy').input_value(), '')
            finally:
                fresh.close()
            page.locator('#trade-strategy').select_option(goal)
            page.goto(origin + '/teams/1', wait_until='domcontentloaded')
            page.go_back(wait_until='domcontentloaded')
            page.locator('#trade-sent-board input[type=search]').wait_for()
            self.assertEqual(page.locator('#trade-strategy').input_value(), goal)
            page.go_forward(wait_until='domcontentloaded')
            page.go_back(wait_until='domcontentloaded')
            page.locator('#trade-sent-board input[type=search]').wait_for()
            self.assertEqual(page.locator('#trade-strategy').input_value(), goal)
            # Temporary packages from the other league are not retained.
            storage = page.evaluate("Object.keys(sessionStorage).filter(k => k.startsWith('dtos-trade-workspace:'))")
            self.assertLessEqual(len(storage), 12)
            self.assertIn("dtos-trade-workspace:" + binding["binding"], storage)
            self.assertEqual(urlsplit(page.url).path, path)


if __name__ == '__main__':
    unittest.main()
