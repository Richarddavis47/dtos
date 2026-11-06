"""Actual Market routes/theme at four sizes; disposable evidence, not live."""
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from tests.test_market_history_coverage import MarketHistoryFixture
from tools.validation.browser_runtime import launch_chromium


class MarketHistoryCoverageBrowserTests(unittest.TestCase):
    def test_checkpoint_publication_and_boundary_are_coherent_at_four_sizes(self):
        import dtos_app
        from src.platform.lifecycle import memory_snapshot
        target = os.environ.get('DTOS_MARKET_HISTORY_EVIDENCE')
        if not target and os.environ.get('DTOS_PHASE2_EVIDENCE'):
            target = str(Path(os.environ['DTOS_PHASE2_EVIDENCE'])/'market-history-coverage')
        destination = Path(target) if target else None
        if destination:
            destination.mkdir(parents=True,exist_ok=True)
        records, errors, requests = [], [], []
        before_memory = memory_snapshot()
        with sync_playwright() as pw:
            browser = launch_chromium(pw,headless=True)
            try:
                for league in ('1314695233040052224','1319750579458686976'):
                    for width,height in ((320,432),(375,667),(390,844),(1280,900)):
                        with self.subTest(league=league,width=width):
                            f = MarketHistoryFixture(self,league=league,page=dtos_app.page)
                            page = browser.new_page(viewport={'width':width,'height':height})
                            page.on('pageerror',lambda error:errors.append(str(error)))
                            def transport(route):
                                url = urlsplit(route.request.url)
                                if url.netloc != 'fixture':
                                    route.fulfill(status=404)
                                    return
                                if url.path.startswith('/static/'):
                                    path = Path(url.path.lstrip('/'))
                                    if path.is_file():
                                        route.fulfill(path=str(path))
                                        return
                                response = f.client.get(url.path+('?' + url.query if url.query else ''))
                                requests.append({'path':url.path,'status':response.status_code})
                                route.fulfill(status=response.status_code,body=response.content,
                                    content_type=response.headers.get('content-type','text/html'))
                            page.route('**/*',transport)
                            def expanded():
                                page.wait_for_load_state('networkidle')
                                summary = page.get_by_text('Observed trends and comparison details',exact=True)
                                summary.focus()
                                self.assertNotEqual(summary.evaluate('(e)=>getComputedStyle(e).outlineStyle'),'none')
                                before = len(requests)
                                if not summary.evaluate('e=>e.parentElement.open'):
                                    summary.press('Enter')
                                self.assertTrue(summary.evaluate('e=>e.parentElement.open'))
                                self.assertEqual(len(requests),before)
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth-innerWidth'),0)
                                return page.locator('.market-trend-checkpoints')
                            try:
                                with patch.dict(dtos_app.STATE,{'data':f.data}):
                                    response = page.goto('http://fixture/market?selected=player%3A1')
                                    self.assertEqual(response.status,200)
                                    preview = expanded()
                                    self.assertEqual(preview.locator('tbody tr').count(),2)
                                    self.assertIn('+100.00 Market points',page.locator('body').inner_text())
                                    initial_generation = f.market.semantic_generation
                                    if destination:
                                        page.screenshot(path=str(destination/f'before-{league}-{width}.png'))
                                    f.add_point('new-retained-checkpoint',960,'2026-06-01')
                                    admitted = f.trend()
                                    page.reload()
                                    preview = expanded()
                                    self.assertEqual(preview.locator('tbody tr').count(),3)
                                    self.assertIn('+120.00 Market points',page.locator('body').inner_text())
                                    self.assertIn('Current Market price provider',page.locator('body').text_content())
                                    self.assertNotIn('Participating provider',page.locator('body').text_content())
                                    for point in admitted['checkpoints']:
                                        row = preview.locator('tr[data-observation-id="'+point['observation_id']+'"]')
                                        self.assertEqual(row.count(),1)
                                        self.assertIn(point['observed_at'],row.inner_text())
                                        self.assertIn(f'{point["value"]:,.2f}',row.inner_text())
                                    region = preview.get_by_role('region',name='Retained Market observations')
                                    region.focus()
                                    self.assertNotEqual(region.evaluate('e=>getComputedStyle(e).outlineStyle'),'none')
                                    scrollable = region.evaluate('e=>e.scrollWidth>e.clientWidth')
                                    if scrollable:
                                        region.press('ArrowRight')
                                        page.wait_for_timeout(100)
                                        self.assertGreater(region.evaluate('e=>e.scrollLeft'),0)
                                    if destination:
                                        page.screenshot(path=str(destination/f'updated-{league}-{width}.png'))
                                    f.add_point('incompatible-format',1080,'2026-05-01',
                                        semantics={'format_key':'different-reference-format'})
                                    blocked = f.trend()
                                    page.reload()
                                    preview = expanded()
                                    self.assertEqual(preview.locator('tbody tr').count(),4)
                                    self.assertIn('This is not player movement',page.locator('body').text_content())
                                    self.assertIn('Not compared across this evidence boundary',preview.inner_text())
                                    self.assertNotIn('+120.00 Market points',page.locator('body').inner_text())
                                    self.assertIsNone(blocked['magnitude'])
                                    if destination:
                                        page.screenshot(path=str(destination/f'boundary-{league}-{width}.png'))
                                    records.append({'league':league,'viewport':[width,height],
                                        'before':{'magnitude':100,'checkpoint_count':2},
                                        'updated':{k:admitted[k] for k in ('magnitude','checkpoint_count','comparison_start_at','comparison_end_at','comparison_scope','comparison_units','confidence')},
                                        'boundary':{k:blocked[k] for k in ('magnitude','checkpoint_count','direction','comparison_reasons')},
                                        'price_publication_unchanged':initial_generation==f.market.semantic_generation,
                                        'overflow':False,'keyboard':True,'table_keyboard_scroll':scrollable,
                                        'disclosure_extra_requests':0,'source_catalogue_not_participation':True})
                            finally:
                                page.close()
            finally:
                browser.close()
        self.assertEqual(errors,[])
        self.assertFalse(any(r['path'].startswith(('/sync','/trades/recommended')) for r in requests))
        if destination:
            report={'scope':'Disposable canonical source/store and rendered routes. Sample league IDs do not establish live history coverage or actual league settings.',
                'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),
                'working_tree_clean':not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),
                'records':records,'errors':errors,'requests':requests,'before_memory':before_memory,
                'after_memory':memory_snapshot(),'browser_closed':True}
            (destination/'browser.json').write_text(json.dumps(report,indent=2)+'\n')
