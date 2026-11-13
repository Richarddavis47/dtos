"""Supplemental normal authenticated HTTP/real evaluator/real page-theme control.

All accounts, players and source publications are disposable repository fixtures.
This is not live owner or physical Safari acceptance. Run after full validation
container cleanup so source/cgroup/scratch ownership remains separate.
"""
import os,sys,json,subprocess,tempfile,unittest,copy,datetime,hashlib,sqlite3
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='source-screen-fixture-'))
for k,n in {'CACHE':'cache.json','PROJECTION_DB':'projections.sqlite3','METADATA_DB':'metadata.sqlite3','INTELLIGENCE_CHECKPOINT':'intelligence.sqlite3','FOIS_DB':'fois.sqlite3','HISTORY_DB':'history.sqlite3','ACCOUNT_DB':'accounts.sqlite3'}.items():os.environ['DTOS_'+k+'_FILE']=str(root/n)
os.environ.update(DTOS_DURABLE_HISTORY_REQUIRED='0',SLEEPER_BASE_URL='http://127.0.0.1:9/v1',DTOS_FIXTURE_ROOT=str(root),DTOS_HISTORY_STORAGE_ROOT=str(root),DTOS_SLEEPER_SEASON_CACHE_ROOT=str(root/'seasons'))
sys.path.insert(0,'/app')
from tests import test_contextual_back as back
from tests import test_trade_discovery_repair as discovery
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
OUT=Path('/output');SOURCE=json.loads(Path('/evidence/source.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==SOURCE['candidate']
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip()==SOURCE['tree']
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()

class StyledSourceScreen(unittest.TestCase):
 def test_native_target_cost_fit_comparison_and_return(self):
  helper=back.ContextualBackTests();f=helper.fixture();native=discovery.DiscoveryRepairTests();native.setUp()
  try:
   f.editor.data.clear();f.editor.data.update(copy.deepcopy(native.data));f.capital.reader=native.fixture.reader
   # Replacing the native fixture source legitimately invalidates the earlier
   # Custom baseline. Keep that guard; verify saved intent independently of
   # unavailable derived Custom values. Only the two scoped preference tables
   # are read, through a read-only SQLite connection, never sessions/tokens.
   def preferences_snapshot():
    scope=(f.editor.account,f.editor.data['league']['league_id'],1)
    with sqlite3.connect('file:'+str(f.editor.store.path)+'?mode=ro',uri=True) as db:
     return {table:db.execute('SELECT * FROM '+table+' WHERE account_id=? AND league_id=? AND roster_id=? ORDER BY account_id,league_id,roster_id',scope).fetchall()
       for table in ('account_personal_rankings','account_franchise_goals')}
   original=preferences_snapshot();unavailable=f.editor.client.get('/api/my-dtos')
   self.assertEqual(unavailable.status_code,409)
   self.assertEqual(unavailable.json()['status'],'market_source_changed')
   self.assertEqual(preferences_snapshot(),original);records=[]
   with sync_playwright() as engine:
    browser=launch_chromium(engine,headless=True)
    try:
     for width,height in [(320,432),(375,667),(390,844),(1280,900)]:
      page,requests,_,_,errors=helper.page(browser,f,width,height)
      try:
       helper.ready(page,'/trades/trade-for?asset_id=2w')
       page.wait_for_function('document.querySelector("#trade-builder").getAttribute("aria-busy")==="false"')
       page.select_option('#trade-strategy','RETOOL')
       page.select_option('#trade-valuation-mode','neutral')
       with page.expect_response(lambda r:r.url.endswith('/api/trades/generate') and r.request.method=='POST') as response:
        page.locator('#trade-find').focus();page.locator('#trade-find').press('Enter')
       self.assertEqual(response.value.status,200)
       body=response.value.json();self.assertGreaterEqual(len(body['results']),2)
       page.locator('.tw-acquisition-role').first.wait_for()
       cards=page.locator('.tw-offer');self.assertEqual(cards.count(),body['count'])
       leader=next(r for r in body['results'] if 'best_fit' in r['acquisition_comparison']['roles'])
       cheapest=next(r for r in body['results'] if 'lowest_cost' in r['acquisition_comparison']['roles'])
       self.assertTrue(all('2w' in r['proposal']['assets_received'] for r in body['results']))
       self.assertEqual(cheapest['acquisition_comparison']['cost']['outgoing'],min(r['evaluation']['market_evidence']['sent']['total'] for r in body['results']))
       self.assertEqual(preferences_snapshot(),original)
       before=list(requests);draft=helper.draft(page)
       page.screenshot(path=str(OUT/f'native-cost-fit-{width}.png'),full_page=True)
       cards.nth(0).get_by_role('button',name='Add to comparison',exact=True).click()
       cards.nth(1).get_by_role('button',name='Add to comparison',exact=True).click()
       page.get_by_role('button',name='Compare selected offers',exact=True).click()
       panel=page.locator('#trade-comparison');panel.get_by_text('Best-supported fit found',exact=False).first.wait_for()
       self.assertIn('Gross outgoing Neutral Market cost',panel.inner_text())
       self.assertEqual(requests,before)
       page.screenshot(path=str(OUT/f'native-comparison-{width}.png'),full_page=True)
       page.get_by_role('button',name='Return to my offer or draft',exact=True).press('Enter')
       self.assertEqual(helper.draft(page)['currentProposal'],draft['currentProposal'])
       self.assertEqual(requests,before)
       cards=page.locator('.tw-offer');cards.nth(0).get_by_role('button',name='Open editable offer:',exact=False).click()
       self.assertIn('Best-supported fit found',page.locator('#trade-result').inner_text())
       page.get_by_role('button',name='Keep original',exact=True).click()
       self.assertEqual(helper.draft(page)['currentProposal'],draft['currentProposal'])
       self.assertEqual(requests,before)
       self.assertFalse(errors,errors);self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),width+1)
       records.append(dict(width=width,height=height,source='Actual authenticated fixture HTTP and canonical evaluator; normal dtos_app.page theme',results=body['results'],search_evidence=body['search_evidence'],explicit_generate=True,comparison_preview_return_no_http=True,preferences_unchanged=True,preference_snapshot_basis="Read-only account/league/franchise-scoped persisted rankings and goals; source-bound Custom API remains correctly409 after fixture source replacement",physical_safari=False,background=page.locator('body').evaluate('e=>getComputedStyle(e).backgroundColor'),operations=requests))
      finally:page.close()
    finally:browser.close()
   (OUT/'source-screen.json').write_text(json.dumps(dict(source=SOURCE,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),records=records,scope='Source-compatible disposable fixtures only; no live owner claim'),indent=2)+'\n')
  finally:
   helper.doCleanups();native.doCleanups()

result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StyledSourceScreen))
cg=Path('/sys/fs/cgroup');report=dict(source=SOURCE,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),limit=int((cg/'memory.max').read_text()),peak=int((cg/'memory.peak').read_text()),events=dict(x.split() for x in (cg/'memory.events').read_text().splitlines()))
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));raise SystemExit(not result.wasSuccessful())
