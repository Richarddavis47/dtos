"""Existing completed-trade disclosure, actual routes and narrow Chromium."""
from pathlib import Path
import json
import os
import subprocess
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_trade_time_market_evidence as fixture


class TradeTimeMarketEvidenceBrowserTests(unittest.TestCase):
    def test_partial_quotes_source_age_and_keyboard_disclosure(self):
        h = fixture.TradeTimeMarketEvidenceTests()
        h.setUp()
        self.addCleanup(h.doCleanups)
        h.capture(value=321)
        import dtos_app
        h.f.page_renderer = dtos_app.page
        target = os.getenv('DTOS_TRADE_TIME_MARKET_EVIDENCE')
        if not target and os.getenv('DTOS_PHASE2_EVIDENCE'):
            target = str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'trade-time-market')
        output = Path(target) if target else None
        if output:
            output.mkdir(parents=True,exist_ok=True)
        records = []
        with sync_playwright() as pw:
            browser = launch_chromium(pw,headless=True)
            try:
                for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                    page = browser.new_page(viewport={'width':width,'height':height})
                    requests=[]
                    errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    def respond(route):
                        requests.append(route.request.url)
                        r=h.f.client.get(route.request.url.replace('http://fixture',''))
                        route.fulfill(status=r.status_code,body=r.content,
                                      content_type=r.headers.get('content-type','text/html'))
                    page.route('http://fixture/**',respond)
                    r=page.goto('http://fixture/trades/history/'+fixture.fixtures.ROOT)
                    self.assertEqual(r.status,200)
                    section=page.locator('section.card').filter(has=page.get_by_role('heading',name='At the time: Market evidence',exact=True))
                    disclosure=section.locator(':scope > details')
                    summary=disclosure.locator(':scope > summary')
                    summary.scroll_into_view_if_needed()
                    summary.focus()
                    self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                    count=len(requests)
                    summary.press('Enter')
                    self.assertTrue(disclosure.evaluate('e=>e.open'))
                    row=section.locator('.timeline-quote').first
                    self.assertIn('321.0',row.inner_text())
                    self.assertIn('FantasyCalc',row.inner_text())
                    self.assertIn('1 hour before the trade',row.inner_text())
                    self.assertIn('Dated estimate',row.inner_text())
                    self.assertIn('Package totals are not shown',section.inner_text())
                    self.assertIn('Value withheld',section.inner_text())
                    self.assertFalse(row.locator(':scope > details').evaluate('e=>e.open'))
                    self.assertEqual(len(requests),count)
                    self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width)
                    self.assertGreaterEqual(summary.bounding_box()['height'],44)
                    if width<500:
                        session=page.context.new_cdp_session(page)
                        session.send('Emulation.setTouchEmulationEnabled',{'enabled':True})
                        summary.scroll_into_view_if_needed()
                        box=summary.bounding_box()
                        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}]})
                        session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                        self.assertFalse(disclosure.evaluate('e=>e.open'))
                        summary.press('Enter')
                    if output:
                        section.screenshot(path=str(output/f'quotes-{width}.png'))
                    records.append({'width':width,'height':height,'source_value':321,'age_seconds':3600,
                        'overflow':False,'keyboard':True,'touch_emulated':width<500,
                        'extra_disclosure_requests':len(requests)-count,'errors':errors})
                    self.assertFalse(errors)
                    page.close()
            finally:
                browser.close()
        if output:
            def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
            (output/'browser.json').write_text(json.dumps({'head':git('rev-parse','HEAD'),
                'tree':git('rev-parse','HEAD^{tree}'),'working_tree_clean':not git('status','--porcelain'),
                'scope':'Disposable route fixture; prices are not historical real coverage or live acceptance',
                'records':records},indent=2)+'\n')
