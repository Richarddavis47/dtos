"""Four exact-source disposable captures; no live owner workflow or search."""
from pathlib import Path
import sys
sys.path.insert(0,'/app')
from tests.test_team_trade_need_browser import TeamTradeNeedBrowserTests
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
import json,subprocess
case=TeamTradeNeedBrowserTests()
try:
 helper,f=case.fixture()
 rows=[]
 with sync_playwright() as pw:
  browser=launch_chromium(pw,headless=True)
  try:
   for w,h in ((320,432),(375,667),(390,844),(1280,900)):
    page,requests,*_=helper.page(browser,f,w,h)
    try:
     page.goto(helper.origin+'/teams/1',wait_until='networkidle')
     page.locator('#my-team-trade-need').click()
     page.wait_for_function("document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')")
     assert page.locator('#recommendation-position').input_value()=='RB'
     assert not [r for r in requests if r[0]=='POST']
     out=Path('/evidence/position-filter-layout');out.mkdir(exist_ok=True)
     page.screenshot(path=str(out/f'entry-{w}.png'))
     geometry=page.locator('.tw-position-filter').evaluate('e=>{let r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}}')
     page.locator('#recommendation-position').scroll_into_view_if_needed()
     page.screenshot(path=str(out/f'filter-{w}.png'))
     rows.append({'width':w,'height':h,'position':'RB','geometry_on_entry':geometry,'overflow':page.evaluate('document.documentElement.scrollWidth-innerWidth'),'posts':[]})
    finally:page.close()
  finally:browser.close()
 (out/'layout.json').write_text(json.dumps({'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'scope':'Source-pinned disposable authenticated visual capture; not additional mandatory test executions or live acceptance','rows':rows},indent=2)+'\n')
 print(json.dumps(rows))
finally:case.doCleanups()
