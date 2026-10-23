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
                        self.assertIn('Drawback:', page.locator('.home-opportunity').inner_text())
                        self.assertFalse(any('/api/trades/generate' in r for r in requests))
                        row = page.evaluate('''() => {
                          const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {y:r.y,height:r.height,width:r.width};};
                          return {brief:rect('#home-opportunities'),news:rect('.league-trade-news'),
                            firstInsight:rect('#home-opportunity-cards article'),find:rect('#home-find-ideas'),
                            overflow:document.documentElement.scrollWidth-innerWidth,
                            visibleText:document.querySelector('#home-opportunity-cards').innerText,
                            font:getComputedStyle(document.querySelector('#home-opportunity-cards p')).fontSize};}''')
                        row.update(width=width,height=height)
                        self.assertLess(row['brief']['y'],row['news']['y'])
                        self.assertLessEqual(row['overflow'],0)
                        self.assertGreaterEqual(row['find']['height'],44)
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
