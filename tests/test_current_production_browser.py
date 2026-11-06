"""Pinned production through real Market/dossier/theme at four sizes."""
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_current_production_coverage import ProductionViewFixture


class CurrentProductionBrowserTests(unittest.TestCase):
    def test_complete_partial_and_retained_failure_at_four_sizes(self):
        import dtos_app
        from src.platform.lifecycle import memory_snapshot
        target=os.environ.get('DTOS_PRODUCTION_COVERAGE_EVIDENCE')
        if not target and os.environ.get('DTOS_PHASE2_EVIDENCE'):
            target=str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'production-coverage')
        dest=Path(target) if target else None
        if dest:
            dest.mkdir(exist_ok=True,parents=True)
        records,errors,requests=[],[],[]
        before_memory=memory_snapshot()
        with sync_playwright() as pw:
            browser=launch_chromium(pw,headless=True)
            try:
                for league in ('1314695233040052224','1319750579458686976'):
                    for w,h in ((320,432),(375,667),(390,844),(1280,900)):
                        f=ProductionViewFixture(self,league=league,page=dtos_app.page)
                        context=browser.new_context(viewport={'width':w,'height':h},has_touch=w<1000)
                        page=context.new_page()
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        def transport(route):
                            url=urlsplit(route.request.url)
                            if url.netloc!='fixture':
                                route.fulfill(status=404)
                                return
                            response=f.f.client.request(route.request.method,url.path+('?' + url.query if url.query else ''))
                            requests.append(dict(path=url.path,status=response.status_code))
                            route.fulfill(status=response.status_code,body=response.content,headers=dict(response.headers))
                        page.route('**/*',transport)
                        def inspect(expected):
                            panel=page.locator('.canonical-production')
                            panel.evaluate("e=>{for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true}")
                            self.assertIn(expected,panel.inner_text())
                            table=panel.locator('table').first
                            self.assertGreaterEqual(table.evaluate('e=>e.getBoundingClientRect().width'),672)
                            self.assertEqual(table.evaluate('e=>getComputedStyle(e).overflowWrap'),'normal')
                            region=panel.get_by_role('region',name='Sleeper result windows')
                            region.focus()
                            self.assertNotEqual(region.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                            return panel
                        try:
                            with patch.dict(dtos_app.STATE,{'data':f.f.data}):
                                response=page.goto('http://fixture/market?selected=player%3A1')
                                self.assertEqual(response.status,200)
                                inspect('8 of 8 completed-week score observations')
                                self.assertIn('18.00 fantasy points',page.locator('.canonical-production').inner_text())
                                canonical=f.api()['windows'][3]
                                if dest:
                                    page.screenshot(path=str(dest/f'complete-market-{league}-{w}.png'))
                                response=page.goto('http://fixture/players/1?front_office=4')
                                self.assertEqual(response.status,200)
                                inspect('8 of 8 completed-week score observations')
                                self.assertNotIn('This player context does not include a season production summary',page.locator('body').inner_text())
                                if dest:
                                    page.screenshot(path=str(dest/f'complete-dossier-{league}-{w}.png'))
                                # A real source-field conflict, not missing NFLverse
                                # statistics, blocks dependent Sleeper windows.
                                f.f.data['season_matchups']['weeks']['1']['rows'][0]['starters_points']=[999]
                                f.republish_actuals()
                                page.reload()
                                panel=inspect('7 of 8 completed-week score observations')
                                self.assertIn('missing or contradictory',panel.inner_text())
                                self.assertIn('are withheld',panel.inner_text())
                                self.assertIsNone(f.api()['windows'][3]['fantasy_points'])
                                response=page.goto('http://fixture/market?selected=player%3A1')
                                self.assertEqual(response.status,200)
                                inspect('7 of 8 completed-week score observations')
                                f.f.state['last_error']='Disposable league refresh failure'
                                page.reload()
                                panel=inspect('league refresh did not complete')
                                self.assertIn('7 of 8 completed-week score observations',panel.inner_text())
                                if dest:
                                    page.screenshot(path=str(dest/f'partial-retained-{league}-{w}.png'))
                                panel.get_by_text('Weekly Sleeper scores and coverage',exact=True).click()
                                self.assertIn('Sleeper score records disagree',panel.inner_text())
                                count=len(requests)
                                for details in page.locator('details').all():
                                    details.evaluate('e=>e.open=!e.open')
                                self.assertEqual(len(requests),count)
                                records.append(dict(league=league,viewport=[w,h],complete=canonical,
                                    partial=f.api()['windows'][3],retained_failure=True,keyboard=True,
                                    overflow=False,extra_disclosure_requests=0,touch_emulated=w<1000))
                        finally:
                            context.close()
            finally:
                browser.close()
        self.assertEqual(errors,[])
        self.assertFalse(any(r['path'].startswith(('/sync','/trades/recommended')) for r in requests))
        if dest:
            (dest/'browser.json').write_text(json.dumps(dict(head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                working_tree_clean=not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
                scope='Disposable source/store and rendered routes, not authenticated live league production or physical Safari.',
                records=records,errors=errors,requests=requests,before_memory=before_memory,
                after_memory=memory_snapshot(),browser_closed=True),indent=2)+'\n')
