from pathlib import Path
import sys,json,subprocess
sys.path.insert(0,'/app')
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_contextual_back as back
case=back.ContextualBackTests();f=case.fixture()
try:
 with sync_playwright() as pw:
  browser=launch_chromium(pw,headless=True)
  try:
   page,requests,*_=case.page(browser,f,width=320,height=432);case.ready(page,'/trades/recommended')
   report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),source='Actual authenticated baseline renderer; disposable prepared Sleeper fixture; no search',recommended_protection_picker=page.locator('#recommendation-protection-asset').count(),calculator_protect=page.locator('#calculator-protect').count(),shop_protected=page.locator('#shop-protected').count(),posts=[x for x in requests if x[0]=='POST'])
   assert report['recommended_protection_picker']==report['calculator_protect']==report['shop_protected']==0;assert not report['posts'];Path('/evidence/baseline-reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print('Confirmed baseline has no pre-search protection picker in Recommended Trades; no operation ran')
  finally:browser.close()
finally:case.doCleanups()
