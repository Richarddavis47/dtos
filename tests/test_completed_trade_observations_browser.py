"""Prepared retained replay, real account routes and contextual Back; not live."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from threading import Thread
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_history_followthrough as fixtures


class CompletedTradeObservationBrowserTests(unittest.TestCase):
    def test_retained_counts_links_back_and_four_viewports(self):
        from src.core.historical_memory.read_model import HistoricalReadModelCache
        self.enterContext(patch('src.core.historical_memory.read_model.historical_read_model_cache', HistoricalReadModelCache()))
        f = fixtures.FollowThroughFixture(self)
        requests, records, errors = [], [], []
        before = deepcopy(f.data)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                response = f.client.get(self.path, follow_redirects=False)
                if response.status_code == 404 and self.path.startswith('/static/'):
                    response = f.static.get(self.path)
                requests.append(self.path)
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    if key.lower() in {'content-type', 'location', 'cache-control'}:
                        self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(response.content)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        output = os.getenv('DTOS_COMPLETED_TRADE_OBSERVATIONS_EVIDENCE')
        if not output and os.getenv('DTOS_PHASE2_EVIDENCE'):
            output = str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'completed-trade-observations')
        target = Path(output) if output else None
        if target:
            target.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as pw:
                browser = launch_chromium(pw, headless=True)
                try:
                    for league, roster, control in ((fixtures.source.DAY, '4', 'Day retained trades; disposable waiver pagination'),
                                                   (fixtures.source.ARK, '1', 'Arkham sparse retained source')):
                        f.accounts.activate('account-a', league)
                        history = '/history/team/' + league + ':franchise:' + roster
                        for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900)):
                            page = browser.new_page(viewport={'width': width, 'height': height})
                            page.on('pageerror', lambda error: errors.append(str(error)))
                            try:
                                response = page.goto(origin + history)
                                self.assertEqual(response.status, 200)
                                page.wait_for_load_state('networkidle')
                                section = page.locator('.franchise-trades')
                                body = section.inner_text()
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                                if league == fixtures.source.DAY:
                                    self.assertIn('2 completed trades observed', body)
                                    self.assertIn('Player transfers: 1 acquired · 3 sent', body)
                                    self.assertIn('Draft-pick transfers: 5 acquired · 2 sent', body)
                                    self.assertIn('2026-03-01', body)
                                    self.assertIn('2026-10-11', body)
                                    self.assertIn('Coverage: partial', body)
                                    self.assertIn('Franchise history', body)
                                    summary = section.locator('summary')
                                    summary.scroll_into_view_if_needed()
                                    summary.evaluate('e=>e.scrollIntoView({block:"center"})')
                                    summary.focus()
                                    count = len(requests)
                                    page.keyboard.press('Enter')
                                    self.assertTrue(section.locator('details').evaluate('e=>e.open'))
                                    self.assertIn('3 pick transfers across 1 completed trade', section.inner_text())
                                    self.assertIn('1 pick transfer across 1 completed trade', section.inner_text())
                                    self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'), 'none')
                                    box = summary.bounding_box()
                                    self.assertGreaterEqual(box['height'], 44)
                                    self.assertTrue(summary.evaluate('(e)=>{const r=e.getBoundingClientRect();return e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2))}'))
                                    if width < 1000:
                                        touch = page.context.new_cdp_session(page)
                                        touch.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                                        touch.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x']+box['width']/2, 'y': box['y']+box['height']/2}]})
                                        touch.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                                        self.assertFalse(section.locator('details').evaluate('e=>e.open'))
                                        summary.press('Enter')
                                    self.assertEqual(len(requests), count)
                                    self.assertIn('PICK-2027-R1-ORIG7', section.inner_text())
                                    root = '/trades/history/' + fixtures.ROOT
                                    section.locator('a[href="'+root+'"]').first.click()
                                    page.wait_for_url('**'+root)
                                    self.assertIn('Original completed trade', page.locator('.trade-timeline').inner_text())
                                    page.locator('#dtos-back').click()
                                    page.wait_for_url('**'+history)
                                    self.assertIn('2 completed trades observed', page.locator('.franchise-trades').inner_text())
                                    page.locator('#fh-season').select_option('2026')
                                    page.get_by_role('button', name='Show period', exact=True).click()
                                    page.wait_for_url('**'+history+'?season=2026')
                                    page.locator('a[href="'+history+'?events_page=2&season=2026"]').click()
                                    filtered = history+'?events_page=2&season=2026'
                                    page.wait_for_url('**'+filtered)
                                    self.assertIn('page 2 of', page.locator('.franchise-timeline').inner_text())
                                    section = page.locator('.franchise-trades')
                                    section.locator('summary').press('Enter')
                                    section.locator('a[href="'+root+'"]').first.click()
                                    page.wait_for_url('**'+root)
                                    pick = '/picks/'+fixtures.PICK+'?from_trade='+fixtures.ROOT
                                    player = '/players/13346?from_trade='+fixtures.ROOT
                                    later = '/trades/history/'+fixtures.LATER+'?from_trade='+fixtures.ROOT
                                    page.locator('.timeline-sides a[href="'+pick+'"]').first.click()
                                    page.wait_for_url('**'+pick)
                                    self.assertIn('Consumed by verified draft conversion', page.locator('body').inner_text())
                                    page.locator('a[href="'+player+'"]').first.click()
                                    page.wait_for_url('**'+player)
                                    page.locator('a[href="'+later+'"]').first.click()
                                    page.wait_for_url('**'+later)
                                    page.locator('.trade-timeline a.back[href="'+root+'"]').click()
                                    page.wait_for_url('**'+root)
                                    for path in [later, player, pick, root, filtered]:
                                        page.locator('#dtos-back').click()
                                        page.wait_for_url('**'+path)
                                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                                    page.reload()
                                    page.wait_for_url('**'+filtered)
                                    self.assertEqual(page.locator('#fh-season').input_value(), '2026')
                                    self.assertIn('2 completed trades observed', page.locator('.franchise-trades').inner_text())
                                else:
                                    self.assertIn('totals are unknown', body)
                                    self.assertNotIn('0 completed trades observed', body)
                                self.assertEqual(errors, [])
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'), 0)
                                records.append(dict(control=control, width=width, height=height,
                                    supported_trades=2 if league == fixtures.source.DAY else None,
                                    firsts_received=3 if league == fixtures.source.DAY else None,
                                    firsts_sent=1 if league == fixtures.source.DAY else None,
                                    keyboard=league == fixtures.source.DAY, touch_emulated=width < 1000 and league == fixtures.source.DAY,
                                    contextual_back=league == fixtures.source.DAY, season_filter=2026 if league == fixtures.source.DAY else None,
                                    gross_player_transfers=[1,3] if league == fixtures.source.DAY else None,
                                    gross_pick_transfers=[5,2] if league == fixtures.source.DAY else None,
                                    filtered_pagination_conversion_return=league == fixtures.source.DAY, overflow=False))
                                if target:
                                    page.locator('.franchise-trades').scroll_into_view_if_needed()
                                    page.screenshot(path=str(target/(('Day' if league == fixtures.source.DAY else 'Arkham')+'-'+str(width)+'.png')))
                            finally:
                                page.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(before, f.data)
        if target:
            report = dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(),
                working_tree_clean=not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip(),
                records=records, errors=errors, server_thread_reaped=True,
                scope='Retained source replay with disposable account sessions and waiver-only pagination; no fresh production observation or manager-intent claim.')
            (target/'browser.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
