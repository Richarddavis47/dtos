"""Click through released history/dossier routes with real scoped Back navigation."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit
import unittest

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_history_followthrough as fixtures


class HistoryFollowThroughBrowserTests(unittest.TestCase):
    def test_chain_conversion_origin_and_paginated_return_at_four_sizes(self):
        f=fixtures.FollowThroughFixture(self)
        requests=[]
        errors=[]
        client,static=f.client,f.static
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass
            def do_GET(self):
                response=client.get(self.path,follow_redirects=False)
                if response.status_code==404 and self.path.startswith('/static/'):
                    response=static.get(self.path)
                requests.append({'path':self.path,'status':response.status_code})
                self.send_response(response.status_code)
                for key,value in response.headers.items():
                    if key.lower() in {'content-type','location','cache-control'}:
                        self.send_header(key,value)
                self.end_headers()
                try:
                    self.wfile.write(response.content)
                except (BrokenPipeError,ConnectionResetError):
                    pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        root='/trades/history/'+fixtures.ROOT
        pick='/picks/'+fixtures.PICK+'?from_trade='+fixtures.ROOT
        player='/players/13346?from_trade='+fixtures.ROOT
        later='/trades/history/'+fixtures.LATER+'?from_trade='+fixtures.ROOT
        history='/history/team/'+fixtures.source.DAY+':franchise:4'
        records=[]
        target=os.getenv('DTOS_FOLLOWTHROUGH_EVIDENCE')
        if not target and os.getenv('DTOS_PHASE2_EVIDENCE'):
            target=str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'history-followthrough')
        destination=Path(target) if target else None
        if destination:
            destination.mkdir(parents=True,exist_ok=True)
        before=deepcopy(f.data)
        try:
            with sync_playwright() as engine:
                browser=launch_chromium(engine,headless=True)
                try:
                    for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                        with self.subTest(width=width):
                            f.accounts.activate('account-a',fixtures.source.DAY)
                            p=browser.new_page(viewport={'width':width,'height':height})
                            p.on('pageerror',lambda error:errors.append(str(error)))
                            p.set_default_timeout(9000)
                            trace=[]
                            def checked(path):
                                p.wait_for_url('**'+path)
                                p.wait_for_load_state('networkidle')
                                self.assertLessEqual(p.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                                trace.append(urlsplit(p.url).path+('?' + urlsplit(p.url).query if urlsplit(p.url).query else ''))
                            try:
                                response=p.goto(origin+history)
                                self.assertEqual(response.status,200)
                                checked(history)
                                p.locator('a[href="'+history+'?events_page=2"]').click()
                                checked(history+'?events_page=2')
                                self.assertIn('page 2 of',p.locator('.franchise-timeline').inner_text())
                                p.locator('.franchise-timeline a[href="'+root+'"]').click()
                                checked(root)
                                self.assertIn('Original completed trade',p.locator('.trade-timeline').inner_text())
                                self.assertIn('Current roster observations and last transfers are separate',p.locator('.trade-timeline').inner_text())
                                self.assertGreater(p.locator('.timeline-sides li').count(),2)
                                p.locator('.timeline-sides a[href="'+pick+'"]').first.click()
                                checked(pick)
                                self.assertIn('Consumed by verified draft conversion',p.locator('body').inner_text())
                                p.locator('a[href="'+player+'"]').first.click()
                                checked(player)
                                self.assertIn('Current values are never backdated',p.locator('body').inner_text())
                                p.locator('a[href="'+later+'"]').first.click()
                                checked(later)
                                self.assertIn('Back to original trade timeline',p.locator('.trade-timeline').inner_text())
                                p.locator('.trade-timeline a.back[href="'+root+'"]').click()
                                checked(root)
                                disclosure=p.locator('.timeline-asset').first
                                summary=disclosure.locator('summary')
                                summary.scroll_into_view_if_needed()
                                summary.focus()
                                self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                                count=len(requests)
                                summary.press('Enter')
                                self.assertTrue(disclosure.evaluate('e=>e.open'))
                                self.assertEqual(len(requests),count)
                                if width<500:
                                    touch=p.context.new_cdp_session(p)
                                    touch.send('Emulation.setTouchEmulationEnabled',{'enabled':True})
                                    box=summary.bounding_box()
                                    touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}]})
                                    touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                                    self.assertFalse(disclosure.evaluate('e=>e.open'))
                                if destination:
                                    p.screenshot(path=str(destination/f'Day-chain-{width}.png'))
                                for path in [later,player,pick,root,history+'?events_page=2',history]:
                                    p.locator('#dtos-back').click()
                                    checked(path)
                                self.assertIn('page 1 of',p.locator('.franchise-timeline').inner_text())
                                # Native Forward and reload preserve the same page identity.
                                p.go_forward()
                                checked(history+'?events_page=2')
                                p.reload()
                                checked(history+'?events_page=2')
                                self.assertEqual(p.locator('#dtos-back').get_attribute('href'),history)
                                records.append(dict(control='Day retained chain plus disposable pagination',width=width,height=height,
                                    chain=trace,original=fixtures.ROOT,pick=fixtures.PICK,later=fixtures.LATER,
                                    keyboard=True,touch_emulated=width<500,overflow=False,extra_disclosure_requests=0,
                                    pagination_return=True,forward_reload=True))
                                # A genuine selected-membership change cannot replay Day history.
                                old_scope=p.locator('meta[name="dtos-navigation-scope"]').get_attribute('content')
                                f.accounts.activate('account-a',fixtures.source.ARK)
                                arc='/history/team/'+fixtures.source.ARK+':franchise:1'
                                response=p.goto(origin+arc)
                                self.assertEqual(response.status,200)
                                checked(arc)
                                self.assertNotEqual(old_scope,p.locator('meta[name="dtos-navigation-scope"]').get_attribute('content'))
                                self.assertNotIn(fixtures.source.DAY,p.locator('#dtos-back').get_attribute('href'))
                                self.assertIn('RETAINED / NOT REVALIDATED',p.locator('.franchise-timeline').inner_text())
                                self.assertIn('Missing',p.locator('.franchise-timeline').inner_text().replace('missing','Missing'))
                                self.assertTrue(all(e['url'].startswith(arc) for e in p.evaluate("JSON.parse(sessionStorage.getItem('dtos-contextual-navigation:v1')).entries")))
                                if destination:
                                    p.screenshot(path=str(destination/f'Arkham-history-{width}.png'))
                                records.append(dict(control='Arkham retained history and scope reset',width=width,height=height,
                                    overflow=False,source_qualified=True,old_league_replay=False))
                            finally:
                                p.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual(f.data,before)
        self.assertFalse(any('/sync' in r['path'] or '/trades/recommended' in r['path'] for r in requests))
        if destination:
            report=dict(scope='Retained source replay plus disposable pagination/account fixtures; not authenticated live acceptance',
                head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
                records=records,requests=requests,errors=errors,server_thread_reaped=not thread.is_alive())
            (destination/'browser.json').write_text(json.dumps(report,indent=2)+'\n')
