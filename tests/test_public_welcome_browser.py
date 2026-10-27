"""Real public HTTP rendered in controlled Chromium; no live accounts or device claim."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import uvicorn

from tests import test_public_entry as entry
from tools.validation.browser_runtime import launch_chromium


VIEWPORTS = ((320, 432), (375, 667), (390, 844), (1280, 900))
ROOT = Path(__file__).resolve().parents[1]


def _visible_geometry(page):
    return page.evaluate("""() => {
      const visible=e=>{
        if (!e.getClientRects().length || getComputedStyle(e).visibility==='hidden') return false;
        const closed=e.closest('details:not([open])');
        return !closed || closed===e || closed.querySelector(':scope>summary')?.contains(e);
      };
      const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y+scrollY,width:r.width,height:r.height};};
      const background=e=>{for(let node=e;node;node=node.parentElement){const color=getComputedStyle(node).backgroundColor;if(color!=='transparent' && color!=='rgba(0, 0, 0, 0)')return color;}return 'rgb(255, 255, 255)';};
      const focusedNote=()=>{
        const e=document.querySelector('.pw-demo[open]>summary:focus-visible');
        if(!e)return null;
        const note=e.nextElementSibling,range=document.createRange();
        range.selectNodeContents(note);
        const textTop=Math.min(...[...range.getClientRects()].filter(r=>r.width&&r.height).map(r=>r.top));
        const rect=e.getBoundingClientRect(),style=getComputedStyle(e),width=parseFloat(style.outlineWidth),offset=parseFloat(style.outlineOffset);
        const outerBottom=rect.bottom+Math.max(0,width+offset);
        return {summary: e.parentElement.id,outline_width:width,outline_offset:offset,
          summary_bottom:rect.bottom+scrollY,outline_bottom:outerBottom+scrollY,
          note_text_top:textTop+scrollY,clearance:textTop-outerBottom};
      };
      const selectors={header:'.pw-header',headline:'#welcome-title',primary:'.pw-hero>.pw-primary',
        access:'.pw-access',demo:'#demo',team:'#demo-team',trade:'#demo-trade',values:'#demo-values'};
      return {viewport:[innerWidth,innerHeight],scrollY,
        overflow:document.documentElement.scrollWidth-innerWidth,
        focused_note:focusedNote(),
        boxes:Object.fromEntries(Object.entries(selectors).map(([key,selector])=>[key,box(document.querySelector(selector))])),
        contrast:Object.fromEntries(['#welcome-title','.pw-value','.pw-access','.pw-primary'].map(selector=>{const e=document.querySelector(selector);return [selector,{foreground:getComputedStyle(e).color,background:background(e)}];})),
        components:[...document.querySelectorAll('.pw-wrap,.pw-intro,.pw-hero,.pw-demo-group,.pw-conclusion,.pw-metrics,.pw-comparison,.pw-roster,.pw-package,.pw-side,.pw-account-actions')]
          .filter(visible).map(e=>({class:e.className,...box(e),client:e.clientWidth,scroll:e.scrollWidth})),
        controls:[...document.querySelectorAll('a,summary')].filter(visible).filter(e=>!e.matches('.pw-skip'))
          .map(e=>({text:e.innerText.trim(),...box(e)})),
        clippedText:[...document.querySelectorAll('h1,h2,h3,p,li,dt,dd,small')].filter(visible)
          .filter(e=>e.innerText.trim()).map(e=>{const range=document.createRange();range.selectNodeContents(e);
            const rects=[...range.getClientRects()].filter(r=>r.width&&r.height);return {text:e.innerText.slice(0,100),rects:rects.map(r=>({left:r.left,right:r.right}))};})
          .filter(e=>e.rects.some(r=>r.left < -0.5 || r.right > innerWidth+0.5))};
    }""")


class PublicWelcomeBrowserTests(unittest.TestCase):
    def setUp(self):
        # Use the actual public/account routers and ASGI boundaries. Do not
        # inherit the fixture test class, which would rediscover its tests here.
        self.fixture = entry.PublicEntryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.requests = []
        self.external_requests = []
        self.errors = []
        self.data = json.loads((ROOT/'src/ui/public_demo_data.json').read_text())

    @contextmanager
    def browser(self, width, height, *, javascript=True, touch=False):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        self.origin = 'http://127.0.0.1:'+str(listener.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(self.fixture.app, log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic()+5
        while not server.started and time.monotonic()<deadline:
            time.sleep(.01)
        try:
            self.assertTrue(server.started, 'Public fixture HTTP server did not start')
            with sync_playwright() as playwright:
                browser = launch_chromium(playwright, headless=True)
                context = browser.new_context(viewport={'width': width, 'height': height},
                                              java_script_enabled=javascript, has_touch=touch)

                def record(request):
                    parsed = urlsplit(request.url)
                    if parsed.netloc != urlsplit(self.origin).netloc:
                        self.external_requests.append(request.url)
                    self.requests.append({'method': request.method, 'path': parsed.path,
                                          'query': parsed.query})

                # Native localhost HTTP includes ordinary redirects and browser
                # Back, unlike a fulfilled redirect into a fake external host.
                context.route(re.compile(r'https?://(?!127\.0\.0\.1(?::|/))'), lambda route: route.abort())
                context.on('request', record)
                page = context.new_page()
                page.on('pageerror', lambda error: self.errors.append(str(error)))
                try:
                    yield page
                finally:
                    context.close()
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(5)
            listener.close()
            self.assertFalse(thread.is_alive(), 'Public fixture HTTP server did not stop')

    def assert_layout(self, page):
        facts = _visible_geometry(page)
        self.assertEqual(facts['overflow'], 0)
        self.assertEqual(facts['clippedText'], [], 'Rendered text must not escape the phone')
        def luminance(value):
            channels=[float(v)/255 for v in re.findall(r'[\d.]+', value)[:3]]
            linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
            return sum(weight*value for weight,value in zip((.2126,.7152,.0722),linear,strict=True))
        for selector, colors in facts['contrast'].items():
            values=sorted(luminance(colors[key]) for key in ('foreground','background'))
            ratio=(values[1]+.05)/(values[0]+.05)
            self.assertGreaterEqual(ratio,4.5,(selector,colors,ratio))
        width = facts['viewport'][0]
        for component in facts['components']:
            self.assertLessEqual(component['scroll'], component['client']+1, component)
            self.assertGreaterEqual(component['x'], -0.5, component)
            self.assertLessEqual(component['x']+component['width'], width+0.5, component)
        for control in facts['controls']:
            self.assertGreaterEqual(control['height'], 44, control)
            self.assertGreaterEqual(control['width'], 44, control)
            self.assertGreaterEqual(control['x'], -0.5, control)
            self.assertLessEqual(control['x']+control['width'], width+0.5, control)
        return facts

    def capture(self, page, name, width, height):
        facts = self.assert_layout(page)
        facts.update(name=name, width=width, height=height,
                     collected_at=datetime.now(timezone.utc).isoformat(),
                     browser=page.context.browser.version,
                     source_head=os.getenv('DTOS_EXPECTED_HEAD', 'Uncommitted candidate; see source hashes'),
                     source_files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                   for name in ('src/ui/public_welcome.py','src/ui/public_demo_data.json',
                                                'routes/public_entry.py','src/platform/account_context.py',
                                                'src/platform/league_context.py')},
                     scope='Disposable actual-router HTTP response rendered in controlled Chromium; no external traffic or account writes.')
        output = os.getenv('DTOS_WELCOME_EVIDENCE')
        if output:
            folder = Path(output)
            folder.mkdir(parents=True, exist_ok=True)
            stem = name+'-'+str(width)
            page.screenshot(path=str(folder/(stem+'.png')), full_page=False)
            (folder/(stem+'.json')).write_text(json.dumps(facts, indent=2))
        return facts

    def tab_to(self, page, selector):
        for _ in range(80):
            page.keyboard.press('Tab')
            if page.evaluate('(selector)=>document.activeElement.matches(selector)', selector):
                focused = page.locator(selector)
                self.assertTrue(focused.evaluate("e=>e.matches(':focus-visible')"))
                self.assertEqual(focused.evaluate('e=>getComputedStyle(e).outlineStyle'), 'solid')
                self.assertGreaterEqual(focused.evaluate('e=>parseFloat(getComputedStyle(e).outlineWidth)'), 3)
                return focused
        self.fail('Keyboard did not reach '+selector)

    def assert_focus_note_clearance(self, page):
        geometry = _visible_geometry(page)['focused_note']
        self.assertIsNotNone(geometry, 'The open demo summary must retain keyboard focus')
        self.assertGreaterEqual(geometry['outline_width'], 3)
        self.assertGreaterEqual(geometry['clearance'], 0,
                                'Focus paint must not cross the fictional-data notice: '+str(geometry))

    def assert_no_work_or_writes(self):
        self.assertEqual(self.external_requests, [])
        self.assertEqual(self.errors, [])
        self.assertTrue(self.requests)
        self.assertTrue(all(row['method']=='GET' for row in self.requests), self.requests)
        self.fixture.manager.acquire_request.assert_not_awaited()
        self.fixture.manager.get.assert_not_awaited()

    def test_public_http_phone_hierarchy_keyboard_and_disclosures(self):
        for width, height in VIEWPORTS:
            with self.subTest(width=width), self.browser(width, height) as page:
                page.goto(self.origin+'/')
                self.assertEqual(urlsplit(page.url).path, '/welcome')
                self.assertEqual(page.locator('h1').count(), 1)
                self.assertEqual(page.locator('header').count(), 1)
                self.assertEqual(page.locator('main').count(), 1)
                self.assertEqual(page.locator('script,form,input,button').count(), 0)
                self.assertTrue(page.locator('#demo-team').evaluate('e=>e.open'))
                self.assertFalse(page.locator('#demo-trade').evaluate('e=>e.open'))
                self.assertFalse(page.locator('#demo-values').evaluate('e=>e.open'))
                initial = self.capture(page, 'initial', width, height)
                headline, primary = initial['boxes']['headline'], initial['boxes']['primary']
                self.assertLess(headline['y'], 170)
                self.assertLessEqual(primary['y']+primary['height'], height)
                self.assertLessEqual(initial['boxes']['access']['y']+initial['boxes']['access']['height'], height)
                if width < 760:
                    self.assertLess(initial['boxes']['demo']['y'], 500)
                skip = self.tab_to(page, '.pw-skip')
                self.assertGreaterEqual(skip.bounding_box()['y'], 0)
                page.keyboard.press('Enter')
                self.assertEqual(page.evaluate('document.activeElement.id'), 'main')
                self.tab_to(page, '#demo-team>summary')
                page.keyboard.press('Enter')
                self.assertFalse(page.locator('#demo-team').evaluate('e=>e.open'))
                page.keyboard.press('Enter')
                self.assertTrue(page.locator('#demo-team').evaluate('e=>e.open'))
                self.assert_focus_note_clearance(page)
                self.tab_to(page, '#demo-trade>summary')
                page.keyboard.press('Enter')
                self.assertTrue(page.locator('#demo-trade').evaluate('e=>e.open'))
                self.assertTrue(page.locator('#demo-trade>summary').evaluate('e=>e===document.activeElement'))
                self.assert_focus_note_clearance(page)
                self.capture(page, 'trade-keyboard', width, height)
                page.keyboard.press('Enter')
                self.assertFalse(page.locator('#demo-trade').evaluate('e=>e.open'))
                self.tab_to(page, '#demo-values>summary')
                page.keyboard.press('Space')
                self.assertTrue(page.locator('#demo-values').evaluate('e=>e.open'))
                self.assert_focus_note_clearance(page)
                self.capture(page, 'values-keyboard', width, height)
                page.locator('#demo-trade>summary').click()
                page.locator('#demo-values>summary').click()
                self.assertTrue(page.locator('#demo-trade').evaluate('e=>e.open'))
                self.assertFalse(page.locator('#demo-values').evaluate('e=>e.open'))
        self.assert_no_work_or_writes()

    def test_frozen_assets_numbers_capital_and_account_return_navigation(self):
        for width, height in VIEWPORTS:
            with self.subTest(width=width), self.browser(width, height, touch=width<760) as page:
                page.goto(self.origin+'/welcome?league=foreign&front_office=999&mode=custom')
                for fragment in ('demo-team', 'demo-trade', 'demo-values'):
                    page.locator('.pw-demo-nav a[href="#'+fragment+'"]').click()
                    self.assertEqual(urlsplit(page.url).fragment, fragment)
                    self.assertTrue(page.locator('#'+fragment+'>summary').is_visible())
                for selector in ('#demo-roster', '#demo-capital', '#demo-trade', '#demo-values', '#demo-evidence'):
                    page.locator(selector+'>summary').click()
                    self.assertTrue(page.locator(selector).evaluate('e=>e.open'))
                self.assert_layout(page)
                for section, rows in [('send', self.data['trade']['send']), ('receive', self.data['trade']['receive'])]:
                    title = 'You Send' if section=='send' else 'You Receive'
                    package = page.locator('#demo-trade .pw-package').filter(has=page.get_by_role('heading', name=title, exact=True))
                    for row in rows:
                        self.assertIn(row.get('name') or row['label'], package.inner_text())
                for row in self.data['team']['capital']:
                    capital = page.locator('#demo-capital').inner_text()
                    for key in ('label', 'original_franchise', 'current_owner'):
                        self.assertIn(row[key], capital)
                totals = [float(re.search(r'[-+]?\d[\d,]*(?:\.\d+)?', item).group().replace(',',''))
                          for item in page.locator('#demo-trade .pw-number').all_inner_texts()]
                self.assertEqual(totals, [self.data['trade']['market_sent'], self.data['trade']['market_received']])
                deltas = page.locator('#demo-trade .pw-delta').all_inner_texts()
                for text, side in zip(deltas, ('active','partner'), strict=True):
                    self.assertEqual(float(re.search(r'[-+]?\d+(?:\.\d+)?', text).group()), self.data['trade'][side]['delta'])
                personal = [float(item.replace(',','')) for item in page.locator('#demo-values dd').all_inner_texts()]
                self.assertEqual(personal, [self.data['personal'][key] for key in ('neutral_sent','neutral_received','personal_sent','personal_received')])
                self.assertIn(self.data['trade']['recommendation'], page.locator('#demo-trade .pw-assessment').inner_text())
                self.assertIn('not a prediction', page.locator('#demo-trade').inner_text())
                self.capture(page, 'expanded', width, height)
                for path in ('/account/sign-in','/account/create','/account/recover'):
                    page.locator('.pw-account-actions a[href="'+path+'"]').click()
                    self.assertEqual(urlsplit(page.url).path, path)
                    self.assertGreater(page.locator('form').count(), 0)
                    page.go_back()
                    self.assertEqual(urlsplit(page.url).path, '/welcome')
                    self.assertIn('not your league', page.locator('footer').inner_text())
                page.locator('.pw-hero>.pw-primary').click()
                self.assertEqual(urlsplit(page.url).fragment, 'demo')
        self.assert_no_work_or_writes()

    def test_native_demo_remains_usable_with_javascript_disabled(self):
        with self.browser(375, 667, javascript=False, touch=True) as page:
            page.goto(self.origin+'/welcome')
            page.locator('.pw-hero>.pw-primary').tap()
            self.assertEqual(urlsplit(page.url).fragment, 'demo')
            page.locator('#demo-trade>summary').tap()
            self.assertTrue(page.locator('#demo-trade').get_attribute('open') is not None)
            self.assertIn('You Send', page.locator('#demo-trade').inner_text())
            page.locator('#demo-values>summary').tap()
            self.assertTrue(page.locator('#demo-values').get_attribute('open') is not None)
            self.assertIn('Neutral DTOS', page.locator('#demo-values').inner_text())
            self.assertIn('Custom DTOS', page.locator('#demo-values').inner_text())
        self.assert_no_work_or_writes()
