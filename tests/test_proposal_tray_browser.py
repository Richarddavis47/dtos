"""Actual authenticated Trade routes: proposal controls cannot intercept actions.

Responsive Chromium, not physical iPhone/Safari. API search outcomes are bounded
fixtures; router, theme, navigation, persistence and interactions are real.
"""
import copy
import unittest
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from playwright.sync_api import sync_playwright

from routes.trades import create_trades_router
from tests import test_trade_workspace_batch1 as boundary
from tools.validation.browser_runtime import launch_chromium


class ProposalTrayBrowserTests(unittest.TestCase):
    def setUp(self):
        import dtos_app
        self.fixture = boundary.AuthenticatedTradeBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.client.close)
        data = self.fixture.data
        for index, name in enumerate(('Bo Nix', 'Joe Burrow')):
            data['teams'][index]['players'][0]['name'] = name
            data['players'][f'{index + 1}-QB-0']['full_name'] = name
        data['market_data']['providers']['FantasyCalc']['2-QB-0']['value'] = 9000
        self.offer = self.fixture._post().json()
        self.fixture.client.app.router.routes.clear()
        self.fixture.client.app.include_router(create_trades_router(
            ensure_fresh=AsyncMock(), require_data=lambda: data, page=dtos_app.page,
        ))
        self.account_patch = patch.object(dtos_app, 'account_store', self.fixture.store)
        self.account_patch.start()
        self.addCleanup(self.account_patch.stop)
        self.requests = []
        self.pending = []
        self.hold = False
        self.outcome = 'offers'

    def response(self, request):
        payload = request.post_data_json
        row = copy.deepcopy(self.offer)
        row['proposal'].update(partner_roster_id=payload.get('partner_roster_id') or 2,
                               assets_sent=payload['assets_sent'] or ['1-QB-0'],
                               assets_received=payload['assets_received'] or ['2-QB-0'])
        row['family_id'] = 'one-fixture-family'
        if request.url.endswith('/balance'):
            row['balance_adjustment'] = {
                'change': 'ADD_PICK', 'market_generation': payload['market_generation'],
                'original': {'sent': {'total': 600}, 'received': {'total': 900}, 'absolute_gap': 300},
                'suggested': {'sent': {'total': 780}, 'received': {'total': 900}, 'absolute_gap': 120},
                'reason': 'Controlled owned-pick adjustment.', 'meaning': 'Market only.',
                'strategic_caution': True,
            }
            row['proposal']['assets_sent'] = [*payload['assets_sent'], '2027-R4-1']
        rows = [row] if self.outcome == 'offers' else []
        return {'workflow': payload.get('workflow'), 'results': rows, 'count': len(rows),
                'has_more': True, 'evaluation': row['evaluation'],
                'quiet_state': 'No credible options in this controlled search.',
                'requested_mode': payload.get('repair_mode'),
                'returned_modes': [payload['repair_mode']] if payload.get('repair_mode') else [],
                'target_preserved': True,
                'markets': [{'counterparty_roster_id': 2, 'returns': rows}] if rows else []}

    def transport(self, route):
        request = route.request
        url = urlsplit(request.url)
        if url.netloc != 'dtos.test':
            return route.abort()
        if request.method == 'POST' and url.path.startswith('/api/trades/'):
            self.requests.append(url.path)
            if self.hold:
                self.pending.append(route)
                return
            if self.outcome == 'error':
                return route.fulfill(status=503, json={'detail': {'message': 'Search unavailable. Your offer stays intact.'}})
            return route.fulfill(json=self.response(request))
        response = self.fixture.client.request(
            request.method, url.path + ('?' + url.query if url.query else ''),
            content=request.post_data,
            headers={k: v for k, v in request.headers.items() if k in ('content-type', 'x-csrf-token')},
        )
        route.fulfill(status=response.status_code,
                      content_type=response.headers.get('content-type', 'text/html'), body=response.content)

    def ready(self, page, path):
        page.goto('https://dtos.test/trades/' + path)
        page.wait_for_function('document.querySelector("#trade-context").textContent.includes("Active league")')

    def state(self, page):
        return page.evaluate('Object.entries(sessionStorage).filter(([k])=>k.startsWith("dtos-trade-workspace:" )).map(([,v])=>JSON.parse(v))[0]')

    def reachable(self, page, locator, *, scroll=True):
        locator = page.locator(locator) if isinstance(locator, str) else locator
        if scroll:
            locator.evaluate('e=>e.scrollIntoView({block:"center",behavior:"instant"})')
        self.assertTrue(locator.is_visible())
        measurement = locator.evaluate('''e=>{const r=e.getBoundingClientRect(), n=document.querySelector('.manager-nav'),nr=n.getBoundingClientRect();
            const points=[[r.x+4,r.y+4],[r.right-4,r.bottom-4],[r.x+r.width/2,r.y+r.height/2]];
            return {box:{top:r.top,bottom:r.bottom},limit:getComputedStyle(n).position==='fixed'?nr.top:innerHeight,
                hit:points.every(([x,y])=>e.contains(document.elementFromPoint(x,y))),
                overflow:document.documentElement.scrollWidth>innerWidth+1};}''')
        self.assertGreaterEqual(measurement['box']['top'], 0, measurement)
        self.assertLessEqual(measurement['box']['bottom'], measurement['limit'], measurement)
        self.assertTrue(measurement['hit'], measurement)
        self.assertFalse(measurement['overflow'], measurement)
        return locator

    def click(self, page, locator):
        target = self.reachable(page, locator)
        box = target.bounding_box()
        # Real pointer coordinates, without Playwright's obstruction retries.
        page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)

    def build(self, page):
        self.ready(page, 'create')
        page.select_option('#trade-partner', '2')
        self.click(page, '#trade-sent-board button[data-asset-id="1-QB-0"]')
        if page.locator('[data-side=received]').is_visible():
            self.click(page, '[data-side=received]')
        self.click(page, '#trade-received-board button[data-asset-id="2-QB-0"]')

    def test_retained_recommended_pointer_loading_tray_and_next_five(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width, height in [(320, 483), (320, 844), (375, 483), (375, 677), (375, 844),
                                      (390, 483), (390, 677), (390, 844), (400, 677), (1280, 900)]:
                    with self.subTest(width=width, height=height):
                        page = browser.new_page(viewport={'width': width, 'height': height})
                        page.route('**/*', self.transport)
                        self.build(page)
                        original = self.state(page)['currentProposal']
                        self.ready(page, 'recommended')
                        self.assertIn('Send 1 / Receive 1', page.locator('#trade-tray-text').inner_text())
                        # The exact original obstructed position, before auto scrolling.
                        if height == 677:
                            self.reachable(page, '#trade-find', scroll=False)
                        self.hold = True
                        before = len(self.requests)
                        self.click(page, '#trade-find')
                        page.wait_for_function('document.querySelector("#trade-find").disabled')
                        self.reachable(page, '#trade-find', scroll=False)
                        status = page.locator('#recommendation-status')
                        self.assertIn('Searching', status.inner_text())
                        self.assertLess(status.bounding_box()['y'], height - 67 if width < 760 else height)
                        for _ in range(50):  # dispatch the deliberately held fixture request
                            if self.pending:
                                break
                            page.wait_for_timeout(20)
                        self.assertEqual(len(self.pending), 1)
                        self.assertEqual(len(self.requests), before + 1)
                        self.hold = False
                        held = self.pending.pop()
                        held.fulfill(json=self.response(held.request))
                        page.get_by_role('button', name='Open editable offer: preview', exact=True).wait_for()
                        self.assertEqual(self.state(page)['currentProposal'], original)
                        self.click(page, '#trade-tray-view')
                        self.assertTrue(page.locator('#trade-review').is_visible())
                        self.reachable(page, '#trade-edit')
                        with page.expect_response('**/api/trades/generate'):
                            self.click(page, '#recommendation-refresh')
                        page.wait_for_function('!document.querySelector("#trade-find").disabled')
                        self.assertEqual(self.state(page)['currentProposal'], original)
                        page.reload()
                        page.locator('#trade-tray:not([hidden])').wait_for()
                        self.assertEqual(self.state(page)['currentProposal'], original)
                        self.reachable(page, '#trade-find')
                        self.ready(page, 'calculator')
                        page.go_back()
                        page.locator('#trade-tray:not([hidden])').wait_for()
                        self.reachable(page, '#trade-find')
                        page.go_forward()
                        page.locator('#trade-balance-offer').wait_for()
                        self.reachable(page, '#trade-balance-offer')
                        page.close()
            finally:
                browser.close()

    def test_cross_workflow_actions_dynamic_states_keyboard_and_resize(self):
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (320, 375, 390, 1280):
                    with self.subTest(width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 677 if width < 760 else 900})
                        page.route('**/*', self.transport)
                        self.ready(page, 'create')
                        self.assertTrue(page.locator('#trade-tray').is_hidden())
                        page.select_option('#trade-partner', '2')
                        self.click(page, '#trade-sent-board button[data-asset-id="1-QB-0"]')
                        self.assertIn('1 assets', page.locator('#trade-tray-text').inner_text())
                        if width < 760:
                            self.click(page, '[data-side=received]')
                        self.click(page, '#trade-received-board button[data-asset-id="2-QB-0"]')
                        self.click(page, '#trade-tray-view')
                        self.click(page, '#trade-run')
                        page.locator('#trade-result .dtos-explanation').wait_for()
                        self.click(page, '#trade-adjust')
                        self.click(page, page.get_by_text('More adjustment options', exact=True))
                        self.click(page, '[data-adjust="make it cheaper"]')
                        self.click(page, '#trade-apply-adjust')
                        preview = page.get_by_role('button', name='Open editable offer: preview', exact=True)
                        preview.wait_for()
                        self.click(page, preview)
                        self.click(page, page.get_by_role('button', name='Keep original', exact=True))
                        self.click(page, preview)
                        self.click(page, page.get_by_role('button', name='Adopt alternative', exact=True))
                        self.assertEqual(self.state(page)['currentProposal']['sent'], ['1-QB-0'])
                        for path in ('shop?asset_id=1-QB-0', 'trade-for?asset_id=2-QB-0'):
                            self.ready(page, path)
                            self.click(page, '#trade-find')
                            preview.wait_for()
                            self.click(page, '#trade-tray-view')
                            self.reachable(page, '#trade-find')
                        self.ready(page, 'calculator')
                        # Target preservation leaves the incoming side; add an owned outgoing.
                        self.click(page, '#trade-sent-board button[data-asset-id="1-QB-0"]')
                        self.click(page, '#trade-balance-offer')
                        page.get_by_role('button', name='Preview adjustment', exact=True).wait_for()
                        self.reachable(page, '#trade-balance-offer')
                        self.click(page, '#trade-run')
                        page.locator('#trade-result .dtos-explanation').wait_for()
                        self.ready(page, 'recommended')
                        for outcome in ('empty', 'error'):
                            self.outcome = outcome
                            with page.expect_response('**/api/trades/generate'):
                                self.click(page, '#trade-find')
                            page.wait_for_function('!document.querySelector("#trade-find").disabled')
                            self.reachable(page, '#trade-find')
                        self.outcome = 'offers'
                        # Native keyboard focus and activation, not forced JS click.
                        page.locator('#trade-tray-view').focus()
                        self.reachable(page, '#trade-tray-view', scroll=False)
                        page.keyboard.press('Enter')
                        self.assertTrue(page.locator('#trade-review').is_visible())
                        page.set_viewport_size({'width': 320, 'height': 483})
                        self.reachable(page, '#trade-find')
                        page.set_viewport_size({'width': 1280, 'height': 900})
                        self.reachable(page, '#trade-tray-view')
                        page.close()
            finally:
                browser.close()

    def test_long_exact_pick_multi_asset_proposal_and_expanded_evidence(self):
        self.fixture.data['teams'][0]['team_name'] = 'A realistic very long original franchise and current owner name'
        with sync_playwright() as engine:
            browser = launch_chromium(engine, headless=True)
            try:
                for width in (320, 375, 390):
                    page = browser.new_page(viewport={'width': width, 'height': 483})
                    page.route('**/*', self.transport)
                    self.build(page)
                    if page.locator('[data-side=sent]').is_visible():
                        self.click(page, '[data-side=sent]')
                    self.click(page, '#trade-sent-board button[data-asset-id="2027-R4-1"]')
                    self.click(page, '#trade-sent-board button[data-asset-id="2027-R3-1"]')
                    original = self.state(page)['currentProposal']
                    self.ready(page, 'recommended')
                    self.assertIn('4 assets', page.locator('#trade-tray-text').inner_text())
                    self.assertIn('Send 3 / Receive 1', page.locator('#trade-tray-text').inner_text())
                    self.click(page, '#trade-find')
                    preview = page.get_by_role('button', name='Open editable offer: preview', exact=True)
                    preview.wait_for()
                    detail = page.get_by_text('Why this offer · evidence and risks', exact=True)
                    self.click(page, detail)
                    self.reachable(page, preview)
                    self.click(page, '#trade-tray-view')
                    self.assertIn('2027-R4-1', self.state(page)['currentProposal']['sent'])
                    self.assertEqual(self.state(page)['currentProposal'], original)
                    page.reload()
                    page.locator('#trade-tray:not([hidden])').wait_for()
                    self.reachable(page, '#trade-find')
                    self.assertEqual(self.state(page)['currentProposal'], original)
                    page.close()
            finally:
                browser.close()
