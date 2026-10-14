"""Released routers/scripts with authenticated disposable state and real Chromium."""
import json
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright
from fastapi.testclient import TestClient

from routes.home import create_home_router
from routes.teams import create_teams_router
from routes.transactions import create_transactions_router
from tools.validation.browser_runtime import launch_chromium
from tests import test_trade_workspace_batch1 as boundary


class BeginnerBrowserTests(unittest.TestCase):
    def setUp(self):
        Path('.validation/beginner-navigation').mkdir(parents=True, exist_ok=True)

    def test_visible_roster_picker_full_reset_and_two_league_intent(self):
        import dtos_app
        f = boundary.AuthenticatedTradeBoundaryTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        app = f.client.app
        common = dict(ensure_fresh=AsyncMock(), require_data=lambda: f.data, page=dtos_app.page)
        app.include_router(create_home_router(**common))
        app.include_router(create_teams_router(**common, state={'data': f.data}))
        app.include_router(create_transactions_router(**common, refresh_transactions=AsyncMock(), state={'data': f.data}))
        static = TestClient(dtos_app.app)
        measurements = []
        with patch.object(dtos_app, 'account_store', f.store), sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in [(320, 432), (375, 667), (390, 844), (390, 432), (1280, 900)]:
                    page = browser.new_page(viewport={'width': width, 'height': height})
                    page.set_default_timeout(8000)
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    def transport(route):
                        url = urlsplit(route.request.url)
                        if url.netloc != 'dtos.test':
                            route.abort()
                            return
                        path = url.path + ('?' + url.query if url.query else '')
                        client = static if url.path.startswith('/static/') and not url.path.endswith(('trade_workspace.js', 'trade_workspace.css', 'strategy_session.js')) else f.client
                        response = client.request(route.request.method, path, content=route.request.post_data, headers={k:v for k,v in route.request.headers.items() if k in ('content-type','x-csrf-token')})
                        route.fulfill(status=response.status_code, content_type=response.headers.get('content-type','text/html'), body=response.content)
                    page.route('**/*', transport)
                    start = time.perf_counter()
                    self.assertEqual(page.goto('https://dtos.test/').status, 200)
                    home_link = page.locator('.ux-action[href$="#full-roster"]')
                    self.assertEqual(home_link.get_attribute('href'), '/teams/1#full-roster')
                    home_link.click()
                    self.assertTrue(page.locator('#my-team-roster').evaluate('e=>e.open'))
                    page.goto('https://dtos.test/teams/1')
                    first = page.locator('#full-roster .thq-player').first
                    self.assertTrue(first.is_visible())
                    roster_y = first.evaluate('e=>e.getBoundingClientRect().top + scrollY')
                    Path('.validation/beginner-navigation/roster-debug.json').write_text(json.dumps(page.locator('main > *, .thq-header, .thq-actions, #full-roster, .thq-roster, .thq-room-head, .thq-player').evaluate_all("es=>es.slice(0,30).map(e=>({cls:e.className,id:e.id,text:e.textContent.slice(0,100),y:e.getBoundingClientRect().top,height:e.getBoundingClientRect().height}))"), indent=2))
                    page.screenshot(path='.validation/beginner-navigation/roster-debug.png')
                    self.assertLess(roster_y, 600, (width, roster_y))
                    if height >= 667:
                        self.assertLess(first.bounding_box()["y"] + first.bounding_box()["height"], height, (width, first.bounding_box()))
                    self.assertEqual(page.locator('#full-roster .thq-player').count(), 10)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    player = page.locator('#full-roster a[href^="/players/"]').first
                    player.click()
                    page.get_by_role('link', name='← Back to My Team roster').click()
                    self.assertTrue(page.locator('#my-team-roster').evaluate('e=>e.open'))
                    page.goto('https://dtos.test/trades/create')
                    own = page.locator('#trade-sent-board')
                    own.get_by_role('searchbox').wait_for()
                    picker_y = own.locator('button[data-asset-id]').first.evaluate('e=>e.getBoundingClientRect().top+scrollY')
                    self.assertLess(picker_y, 900, (width, picker_y))
                    self.assertNotIn('Market evidence', own.inner_text())
                    page.locator('#trade-strategy').select_option('REBUILD')
                    page.get_by_label('Counterparty', exact=True).select_option('2')
                    own.get_by_role('button', name='Add Player 1-QB-0 — you send', exact=True).click()
                    own.get_by_role('button', name='PICKS', exact=True).click()
                    own.get_by_role('button', name='Add 2027 Round 1 (Team 1) — you send', exact=True).click()
                    page.locator('#calculator-protect').click()
                    page.locator('#trade-constraint-asset').select_option('1-QB-1')
                    page.locator('#calculator-lock').click()
                    binding = page.evaluate("Object.keys(sessionStorage).find(k=>k.startsWith('dtos-trade-workspace:'))")
                    before = page.evaluate('key=>JSON.parse(sessionStorage.getItem(key))', binding)
                    self.assertEqual(len(before['currentProposal']['sent']), 2)
                    self.assertIn('1-QB-1', before['protectedAssets'])
                    # Another supported league draft remains independent during cleanup.
                    page.evaluate("sessionStorage.setItem('dtos-trade-workspace:other-league', JSON.stringify({schema:2,currentProposal:{sent:['foreign-pick'],received:[],partner:3},savedAt:Date.now()}))")
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.locator('#trade-start-new').click()
                    own = page.locator('#trade-sent-board')
                    own.get_by_role('searchbox').wait_for()
                    page.reload()
                    own.get_by_role('searchbox').wait_for()
                    after = page.evaluate('key=>JSON.parse(sessionStorage.getItem(key))', binding)
                    self.assertEqual(after['currentProposal'], {'sent': [], 'received': [], 'partner': 0})
                    for key in ('requiredOutgoingAsset','requiredIncomingAsset','currentAssessment','previewProposal','originalProposal','adoptedProposal'):
                        self.assertIsNone(after[key])
                    self.assertEqual(after['protectedAssets'], [])
                    self.assertEqual(after['adjustmentConstraints'], {})
                    self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                    other = page.evaluate("JSON.parse(sessionStorage.getItem('dtos-trade-workspace:other-league'))")
                    self.assertEqual(other['currentProposal']['sent'], ['foreign-pick'])
                    page.goto('https://dtos.test/teams/1')
                    page.go_back()
                    own.get_by_role('searchbox').wait_for()
                    self.assertEqual(page.locator('#trade-partner').input_value(), '')
                    page.goto('https://dtos.test/trades/trade-for')
                    page.get_by_label('Counterparty', exact=True).select_option('2')
                    if width < 760:
                        self.assertTrue(page.locator('#trade-received-board').is_visible())
                    page.locator('#trade-received-board').get_by_role('searchbox').fill('2-QB-0')
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                    first_draft_after_navigation = page.evaluate('key=>JSON.parse(sessionStorage.getItem(key))', binding)
                    source_scoring = dict(f.data.get('scoring_settings') or {})
                    f.store.upsert_membership(f.account_id, {'league_id':'league-2','season':'2026','name':'Second league'}, 'fixture-user', 2, 'Team 2', 'active')
                    f.store.activate(f.account_id, 'league-2')
                    f.data['league']['league_id'] = 'league-2'
                    f.data['scoring_settings'] = {**source_scoring, 'rec': .5, 'bonus_rec_te': .5}
                    page.goto('https://dtos.test/')
                    second_home = page.locator('.ux-action[href$="#full-roster"]')
                    self.assertEqual(second_home.get_attribute('href'), '/teams/2#full-roster')
                    second_home.click()
                    self.assertTrue(page.locator('#my-team-roster').evaluate('e=>e.open'))
                    page.goto('https://dtos.test/trades/create?front_office=2')
                    page.locator('#trade-sent-board input[type=search]').wait_for()
                    page.locator('#trade-strategy').select_option('WIN NOW')
                    page.get_by_label('Counterparty', exact=True).select_option('1')
                    page.locator('#trade-sent-board').get_by_role('button', name='Add Player 2-QB-0 — you send', exact=True).click()
                    keys = page.evaluate("Object.keys(sessionStorage).filter(k=>k.startsWith('dtos-trade-workspace:') && k!=='dtos-trade-workspace:other-league')")
                    second_binding = next(k for k in keys if k != binding)
                    second_draft = page.evaluate('key=>JSON.parse(sessionStorage.getItem(key))', second_binding)
                    f.store.activate(f.account_id, 'league-1')
                    f.data['league']['league_id'] = 'league-1'
                    f.data['scoring_settings'] = source_scoring
                    page.goto('https://dtos.test/trades/create')
                    page.locator('#trade-sent-board input[type=search]').wait_for()
                    self.assertEqual(page.locator('#trade-strategy').input_value(), 'REBUILD')
                    current = page.evaluate('key=>JSON.parse(sessionStorage.getItem(key))', binding)
                    self.assertEqual(current['currentProposal'], first_draft_after_navigation['currentProposal'])
                    self.assertEqual(current['protectedAssets'], [])
                    self.assertEqual(page.evaluate('key=>JSON.parse(sessionStorage.getItem(key)).currentProposal', second_binding), second_draft['currentProposal'])
                    self.assertEqual(errors, [])
                    measurements.append({'width': width, 'height': height, 'roster_first_y': roster_y, 'picker_first_y': picker_y, 'journey_ms': round((time.perf_counter()-start)*1000,2)})
                    page.close()
            finally:
                browser.close()
        target = Path('.validation/beginner-navigation')
        target.mkdir(parents=True, exist_ok=True)
        (target/'browser-geometry.json').write_text(json.dumps(measurements, indent=2))

    def test_market_search_browse_round_and_dossier_return(self):
        import dtos_app
        from tests import test_beginner_market as market_contract
        f = market_contract.BeginnerMarketTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        fixture = f.fixture
        fixture.data.update(week=1, scoring_settings={'rec': 1}, league_settings={}, matchups={}, transactions=[], roster_positions=['QB','RB','WR','TE'])
        fixture.data['league']['season'] = '2026'
        f.client.app.include_router(create_transactions_router(ensure_fresh=AsyncMock(), require_data=lambda: fixture.data, refresh_transactions=AsyncMock(), state=fixture.state, page=lambda title,body: body))
        static_client = TestClient(dtos_app.app)
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                page = browser.new_page(viewport={'width':390,'height':844})
                def transport(route):
                    url = urlsplit(route.request.url)
                    if url.netloc != 'dtos.test':
                        route.abort()
                        return
                    response = static_client.get(url.path) if url.path.startswith('/static/') else f.get(url.path + ('?' + url.query if url.query else ''))
                    self.assertEqual(response.status_code, 200)
                    route.fulfill(status=response.status_code, content_type=response.headers.get('content-type','text/html'), body=response.content)
                page.route('**/*', transport)
                original = 'https://dtos.test/market?q=Denzel+Boston&position=WR&limit=10'
                page.goto(original)
                self.assertEqual(page.locator('.market-asset').count(), 1)
                self.assertIn('Result #1', page.locator('.market-asset').inner_text())
                self.assertEqual(page.get_by_role('link', name='Next page →').count(), 0)
                page.locator('.market-asset').click()
                page.get_by_role('link', name='Open canonical dossier').click()
                back = page.get_by_role('link', name='← Back to Market results')
                self.assertIn('q=Denzel', back.get_attribute('href'))
                self.assertIn('position=WR', back.get_attribute('href'))
                back.click()
                self.assertEqual(page.locator('.market-asset').count(), 1)
                page.get_by_role('link', name='Browse all assets', exact=True).click()
                self.assertNotIn('q=', page.url)
                page.go_back()
                self.assertIn('q=Denzel', page.url)
                page.go_forward()
                page.reload()
                page.get_by_label('Player or pick', exact=True).fill('2029 Round 2')
                page.get_by_label('Position', exact=True).select_option('PICK')
                page.get_by_role('button', name='Search market').click()
                self.assertEqual(page.locator('.market-asset').count(), 3)
                self.assertEqual(page.get_by_role('link', name='Next page →').count(), 0)
                for text in page.locator('.market-asset').all_text_contents():
                    self.assertIn('2029', text)
                    self.assertIn('Round 2', text)
            finally:
                browser.close()
