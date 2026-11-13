"""Current-season cached-runtime publication, real route and phone disclosures."""
import asyncio
from copy import deepcopy
import json
import os
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from src.core.league_runtime import LeagueRuntime
from tests import test_current_season_franchise_history as fixtures
from tools.validation.browser_runtime import launch_chromium


class CurrentSeasonHistoryBrowserTests(unittest.TestCase):
    setUp = fixtures.CurrentSeasonRuntimeHistoryTests.setUp

    def test_current_periods_and_gaps_at_four_sizes_without_source_work(self):
        from src.core.history_context.transaction_periods import current_period_metadata
        records=[]
        root=os.getenv('DTOS_CURRENT_HISTORY_EVIDENCE')
        if not root and os.getenv('DTOS_PHASE2_EVIDENCE'):
            root=str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'current-season-history')
        self.renderer=self.app_module.page
        owned=[]
        for i,name in enumerate(('Granite-shaped','Day-shaped','Arkham-shaped'),1):
            self.data=fixtures.publication('230000000000000000'+str(i),2030+i,8)
            slots = (['QB','RB','RB','WR','WR','TE','FLEX','FLEX','K','DEF'] if i==1
                     else ['QB','RB','WR','TE','FLEX','SUPER_FLEX'] if i==2
                     else ['QB','RB','WR','FLEX','SUPER_FLEX'])
            scoring = {'rec':0.5 if i==2 else 1,'pass_td':6 if i==3 else 4}
            self.data['league'].update(roster_positions=slots,scoring_settings=scoring)
            self.data.update(roster_positions=slots,scoring_settings=scoring)
            self.data['season_transactions']['4']=None
            meta=current_period_metadata(self.data,4,None,f'{2030+i}-10-20T12:00:00+00:00')
            meta['periods']['4']['state']='failed'
            self.data['transaction_acquisition']=meta
            self.runtime=LeagueRuntime(self.data['league']['league_id'])
            asyncio.run(fixtures.CurrentSeasonRuntimeHistoryTests.restore(self))
            owned.append((name,self.runtime))
        with sync_playwright() as engine:
            browser=launch_chromium(engine,headless=True)
            try:
                for name,runtime in owned:
                    self.runtime=runtime
                    before=deepcopy(self.runtime.state['data'])
                    for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                        page=browser.new_page(viewport={'width':width,'height':height})
                        requests=[]
                        def transport(route):
                            request=route.request
                            requests.append(request.url)
                            from urllib.parse import urlsplit
                            u=urlsplit(request.url)
                            if u.netloc!='dtos.test':
                                return route.abort()
                            response=self.client.get(u.path+('?' + u.query if u.query else ''))
                            route.fulfill(status=response.status_code,
                                content_type=response.headers.get('content-type','text/html'),body=response.content)
                        page.route('**/*',transport)
                        try:
                            with patch('services.sleeper.sleeper_get',side_effect=AssertionError('No provider reads on history page')):
                                response=page.goto('http://dtos.test/history/team/'+self.runtime.league_id+':franchise:1')
                                self.assertEqual(response.status,200)
                                page.wait_for_load_state('networkidle')
                                timeline=page.locator('.franchise-timeline')
                                text=timeline.inner_text()
                                self.assertNotIn('Retrieved weeks:', text)
                                coverage=timeline.locator('.fh-season .cx-evidence').first
                                coverage.locator('summary').first.click()
                                self.assertTrue(coverage.evaluate('e=>e.open'))
                                text=timeline.inner_text()
                                self.assertIn('Retrieved weeks: 1, 2, 3, 5, 6, 7, 8',text)
                                self.assertIn('Refresh failed: weeks 4',text)
                                self.assertIn('Observed-empty retrieved weeks: 1, 3, 5, 6, 7, 8',text)
                                self.assertIn('Partial transaction coverage',text)
                                self.assertIn('RETAINED / NOT REVALIDATED',text)
                                summary=timeline.locator('summary').filter(has_text='Period freshness').first
                                summary.scroll_into_view_if_needed()
                                summary.focus()
                                self.assertTrue(summary.evaluate('e=>e===document.activeElement'))
                                self.assertNotEqual(summary.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                                count=len(requests)
                                summary.press('Enter')
                                self.assertTrue(summary.locator('..').evaluate('e=>e.open'))
                                self.assertIn('retrieved at an unrecorded time',timeline.inner_text())
                                self.assertIn('no compatible retrieved bucket retained',timeline.inner_text())
                                box=summary.bounding_box()
                                self.assertGreaterEqual(box['height'],44)
                                if width<500:
                                    touch=page.context.new_cdp_session(page)
                                    touch.send('Emulation.setTouchEmulationEnabled',{'enabled':True})
                                    point={'x':box['x']+box['width']/2,'y':box['y']+box['height']/2}
                                    touch.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[point]})
                                    touch.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
                                    self.assertFalse(summary.locator('..').evaluate('e=>e.open'))
                                self.assertEqual(len(requests),count)
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                                self.assertEqual(self.runtime.state['data'],before)
                                self.sync.assert_not_called()
                                records.append(dict(league_control=name,width=width,height=height,
                                    scope='Disposable current-season source; not authenticated live acceptance',
                                    retrieved=[1,2,3,5,6,7,8],failed=[4],keyboard=True,
                                    touch_emulated=width<500,overflow=False,extra_disclosure_requests=0))
                                if root:
                                    path=Path(root)
                                    path.mkdir(exist_ok=True,parents=True)
                                    timeline.scroll_into_view_if_needed()
                                    page.screenshot(path=str(path/f'{name}-{width}.png'))
                        finally:
                            page.close()
            finally:
                browser.close()
        for _,runtime in owned:
            asyncio.run(runtime.close())
        if root:
            report={'scope':'Disposable source-compatible current-season controls; not authenticated live acceptance',
                'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                'working_tree_clean':not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
                'records':records}
            (Path(root)/'browser.json').write_text(json.dumps(report,indent=2)+'\n')
