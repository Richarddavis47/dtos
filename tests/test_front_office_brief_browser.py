"""Rendered authenticated Chromium; no physical-device or human-study claim."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_roster_diagnostic_http as fixtures


class FrontOfficeBriefBrowserTests(unittest.TestCase):
    def test_phone_brief_prepared_offer_disclosure_keyboard_and_trade_return(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        f.f.seed()
        self.assertEqual(f.f.f.client.get('/teams/1').status_code, 200)
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                    page = f.f.browser_page(browser,width,height)
                    try:
                        requests, errors = [], []
                        page.on('request', lambda r: requests.append(r.url))
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        page.goto('https://dtos.test/')
                        page.locator('.home-opportunity').wait_for()
                        self.assertEqual(page.get_by_role('heading',name='Front Office Brief').count(), 1)
                        self.assertEqual(page.get_by_role('heading',name='Attention',exact=True).count(), 0)
                        self.assertEqual(page.get_by_role('heading',name='Trade Opportunities',exact=True).count(), 0)
                        self.assertIn('2028', page.locator('#home-opportunity-cards').inner_text())
                        self.assertIn('You send:', page.locator('.home-opportunity').inner_text())
                        self.assertIn('You receive:', page.locator('.home-opportunity').inner_text())
                        self.assertIn('Cost and uncertainty:', page.locator('.home-opportunity').inner_text())
                        self.assertFalse(any('/api/trades/generate' in r for r in requests))
                        row = page.evaluate('''() => {
                          const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {y:r.y,height:r.height,width:r.width};};
                          return {brief:rect('#home-opportunities'),news:rect('.league-trade-news'),
                            firstInsight:rect('#home-opportunity-cards article'),find:rect('#home-find-ideas'),
                            title:rect('#home-opportunity-cards article h3'),reason:rect('#home-opportunity-cards article p'),
                            drawback:rect('#home-opportunity-cards article p:nth-of-type(2)'),action:rect('#home-opportunity-cards article a'),
                            nav:rect('.manager-nav'),
                            overflow:document.documentElement.scrollWidth-innerWidth,
                            visibleText:document.querySelector('#home-opportunity-cards').innerText,
                            font:getComputedStyle(document.querySelector('#home-opportunity-cards p')).fontSize};}''')
                        row.update(width=width,height=height)
                        row['initialVisibility'] = {key: row[key]['y'] >= 0 and row[key]['y'] + row[key]['height'] <= min(height, row['nav']['y'] if width < 761 else height) for key in ('title', 'reason', 'drawback', 'action')}
                        self.assertLess(row['brief']['y'],row['news']['y'])
                        self.assertLessEqual(row['overflow'],0)
                        self.assertLess(row['firstInsight']['y'], 550 if width < 761 else 600)
                        if width in (375, 390):
                            self.assertLessEqual(row['title']['y'] + row['title']['height'], row['nav']['y'])
                        self.assertGreaterEqual(row['find']['height'],44)
                        first_action = page.locator('#home-opportunity-cards article a').first
                        first_action.scroll_into_view_if_needed()
                        self.assertTrue(first_action.evaluate('e=>{const r=e.getBoundingClientRect();const h=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return h===e||e.contains(h)}'))
                        more = page.locator('#home-brief-more')
                        self.assertEqual(more.count(),1)
                        self.assertEqual(page.locator('#home-opportunity-cards > article').count(),2)
                        self.assertFalse(more.evaluate('e=>e.open'))
                        summary = more.locator('summary').first
                        summary.focus()
                        self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                        summary.press('Enter')
                        self.assertTrue(more.evaluate('e=>e.open'))
                        summary.click()
                        self.assertFalse(more.evaluate('e=>e.open'))
                        link = page.locator('.home-opportunity').get_by_role('link',name='Explore / Edit')
                        link.click()
                        page.get_by_text('Alternative preview',exact=True).wait_for()
                        page.get_by_role('button',name='Keep original',exact=True).click()
                        page.goto('https://dtos.test/')
                        page.locator('.home-opportunity').wait_for()
                        page.locator('.home-opportunity').get_by_role('link',name='Explore / Edit').click()
                        page.get_by_role('button',name='Adopt alternative',exact=True).click()
                        self.assertIn('2028', page.locator('#trade-received-chips').inner_text())
                        self.assertFalse(errors,errors)
                        measurements.append(row)
                        if os.environ.get('DTOS_BRIEF_EVIDENCE'):
                            page.goto('https://dtos.test/')
                            page.locator('.home-opportunity').wait_for()
                            page.screenshot(path=str(Path(os.environ['DTOS_BRIEF_EVIDENCE'])/f'home-{width}.png'),full_page=True)
                    finally:
                        page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_BRIEF_EVIDENCE'):
            (Path(os.environ['DTOS_BRIEF_EVIDENCE'])/'phone-measurements.json').write_text(json.dumps(measurements,indent=2))

    def test_missing_trade_evidence_preserves_capital_and_late_source_response_is_ignored(self):
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        f.f.seed()
        f.f.f.client.get('/teams/1')
        with sync_playwright() as pw:
            browser=launch_chromium(pw,headless=True)
            try:
                page=f.f.browser_page(browser,390,844)
                with patch('services.home_trade_opportunities.source_identity',return_value=None):
                    page.goto('https://dtos.test/')
                    page.get_by_text('Trade pricing is unavailable or changing.',exact=False).wait_for()
                    self.assertIn('owned future first-round',page.locator('#home-opportunity-cards').inner_text())
                    self.assertEqual(page.locator('.home-opportunity').count(),0)
                page.reload()
                page.locator('.home-opportunity').wait_for()
                pending=[]
                def hold(route):
                    if pending:
                        return route.fallback()
                    u=urlsplit(route.request.url)
                    r=f.f.f.client.get(u.path+'?'+u.query)
                    pending.append((route,r))
                page.route('**/api/trades/home-opportunities?*',hold)
                with page.expect_request('**/api/trades/home-opportunities?*'):
                    page.evaluate("dispatchEvent(new Event('focus'))")
                # Pump the transport until the explicit held-response barrier.
                for _ in range(20):
                    if pending:
                        break
                    page.wait_for_timeout(10)
                self.assertEqual(len(pending),1)
                f.f.f.data['week']=3
                page.evaluate("dispatchEvent(new Event('focus'))")
                page.wait_for_function("document.querySelector('#home-opportunities').dataset.state==='STALE SOURCE OR INTENT'")
                route,response=pending[0]
                route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
                page.wait_for_load_state('networkidle')
                self.assertEqual(page.locator('.home-opportunity').count(),0)
                self.assertNotIn('CURRENT',page.locator('#home-opportunity-cards').inner_text())
                page.close()
            finally:
                browser.close()

    def test_phone_loading_expired_empty_error_and_existing_capital_return(self):
        """Transport failures are controlled; expiry uses the real bounded cache."""
        from services import home_trade_opportunities as ideas
        f = fixtures.DiagnosticHTTPTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.publish(datetime.now(timezone.utc).isoformat())
        f.f.seed()
        f.f.f.client.get('/teams/1')
        measurements = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw, headless=True)
            try:
                for width, height in ((320,432),(375,667),(390,844),(1280,900)):
                    for state in ('loading', 'expired', 'empty', 'error'):
                        page = f.f.browser_page(browser, width, height)
                        generated = []
                        page.on('request', lambda r: generated.append(r.url) if '/api/trades/generate' in r.url else None)
                        def controlled(route):
                            if state == 'loading':
                                return  # Hold the actual read at a deterministic transport barrier.
                            if state == 'error':
                                return route.fulfill(status=503, content_type='application/json', body='{}')
                            return route.fallback()
                        page.route('**/api/trades/home-opportunities?*', controlled)
                        if state == 'expired':
                            with ideas._lock:
                                for key, (_, payload) in list(ideas._entries.items()):
                                    ideas._entries[key] = (ideas.monotonic() - ideas.MAX_AGE - 1, payload)
                        # No prepared team facts and no saved search: actual empty API selector.
                        from contextlib import ExitStack
                        with ExitStack() as stack:
                            if state == 'empty':
                                with ideas._lock:
                                    ideas._entries.clear()
                                stack.enter_context(patch('services.front_office_brief.prepared_diagnostics', return_value=None))
                                stack.enter_context(patch('src.core.intelligence.cache.IntelligenceCache.peek', return_value=None))
                            page.goto('https://dtos.test/', wait_until='domcontentloaded')
                            if state != 'loading':
                                page.wait_for_function("document.querySelector('#home-opportunities').dataset.presentation !== 'loading'")
                            text = page.locator('#home-opportunity-status').inner_text()
                            if state == 'loading':
                                self.assertIn('Reading prepared evidence', text)
                            elif state == 'error':
                                self.assertIn('unavailable', text)
                                self.assertEqual(page.locator('#home-opportunity-cards article').count(), 0)
                            elif state == 'empty':
                                self.assertIn('No actionable insight qualifies', text)
                                self.assertEqual(page.locator('#home-opportunity-cards article').count(), 0)
                            elif state == 'expired':
                                self.assertEqual(page.locator('.home-opportunity').count(), 0)
                                self.assertIn('Find Trade Ideas', text)
                            self.assertFalse(generated)
                            self.assertTrue(page.get_by_role('button', name='Find Trade Ideas', exact=True).is_enabled())
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                            page.get_by_role('button', name='Find Trade Ideas', exact=True).focus()
                            self.assertNotEqual(page.locator('#home-find-ideas').evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                            measurements.append({'width':width,'height':height,'state':state,'status':text,'automatic_discovery_calls':len(generated)})
                            if os.environ.get('DTOS_BRIEF_EVIDENCE'):
                                page.screenshot(path=str(Path(os.environ['DTOS_BRIEF_EVIDENCE'])/f'{state}-{width}.png'), full_page=True)
                        page.close()
                # Exact capital action and existing My Team return use the real authenticated routes.
                page = f.f.browser_page(browser, 390, 844)
                page.goto('https://dtos.test/')
                page.get_by_role('link', name='Review exact draft capital').click()
                self.assertIn('/teams/1#draft-capital', page.url)
                self.assertTrue(page.locator('#draft-capital').is_visible())
                page.go_back()
                page.get_by_role('heading', name='Front Office Brief').wait_for()
                page.close()
                # Real prepared RB replacement concern links into existing Depth and back.
                import base64
                data = f.f.f.data
                data['league']['roster_positions'] = ['RB'] + ['BN'] * 4
                for team in data['teams']:
                    for player in team['players']:
                        player['position'] = 'RB'
                        data['players'][player['id']]['position'] = 'RB'
                f.f.source.points.update(a=40, b=1, e=1, c=30, d=20, f=20)
                ctx = f.f.workspace['workspace_context']
                f.f.cookie = base64.urlsafe_b64encode(json.dumps({'scope':ctx['strategy_scope'], 'rows':[['league-1:1','WIN NOW']]}).encode()).decode().rstrip('=')
                f.f.f.client.cookies.set('dtos_strategy', f.f.cookie)
                f.publish(datetime.now(timezone.utc).isoformat())
                f.f.f.client.get('/teams/1')
                page = f.f.browser_page(browser, 375, 667)
                page.goto('https://dtos.test/')
                page.get_by_role('link', name='Review replacement depth').click()
                self.assertIn('/teams/1#positional-depth', page.url)
                self.assertTrue(page.locator('#positional-depth').is_visible())
                page.go_back()
                page.get_by_role('heading', name='Front Office Brief').wait_for()
                page.close()
            finally:
                browser.close()
        if os.environ.get('DTOS_BRIEF_EVIDENCE'):
            (Path(os.environ['DTOS_BRIEF_EVIDENCE'])/'state-measurements.json').write_text(json.dumps(measurements, indent=2))
