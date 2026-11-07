import sys
sys.path.insert(0,'/app')
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests import test_trade_workflow_experience as fixtures
b=Path('/evidence/zero-result');b.mkdir(exist_ok=True);h=fixtures.TradeWorkflowExperienceTests();f=h.fixture()
try:
 with sync_playwright() as pw:
  browser=launch_chromium(pw,headless=True)
  try:
   page,records,_,errors,_=h.page(browser,f);h.ready(page);page.select_option('#trade-strategy','RETOOL');page.locator('#trade-find').click();h.complete(page);r=records[-1];body=r['body'];assert r['status']==200 and not any(x['evaluation']['generated_trade_eligible'] for x in body['results']);assert body['zero_result_guidance']['message']==body['quiet_state'];assert 'Main limit:' in body['quiet_state'];text=page.locator('#trade-result').inner_text();assert body['quiet_state'] in text;assert not errors
   (b/'response.json').write_text(json.dumps({'source':subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],text=True).splitlines(),'request':r['payload'],'status':r['status'],'response':body,'scope':'Disposable real HTTP and released JS; completed search, not a live zero result or capacity deferral'},indent=2)+'\n');(b/'rendered.txt').write_text(text);page.screenshot(path=str(b/'zero-qualified-375.png'),full_page=True);print(json.dumps({'qualified':0,'optional':len(body['results']),'exploratory':len(body['exploratory_results']),'guidance':body['quiet_state'],'search_state':page.locator('#recommendation-status').get_attribute('data-state'),'errors':errors}))
  finally:browser.close()
finally:h.doCleanups()
