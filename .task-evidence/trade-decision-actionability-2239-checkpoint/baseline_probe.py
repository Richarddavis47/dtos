import sys
sys.path.insert(0,"/app")
from pathlib import Path
import json,unittest
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
from tests.test_trade_workflow_experience import TradeWorkflowExperienceTests
from services.trade_intelligence import evaluate_trade_request

root=Path('/evidence/baseline');root.mkdir(exist_ok=True)
h=TradeWorkflowExperienceTests();f=h.fixture()
try:
 with sync_playwright() as pw:
  browser=launch_chromium(pw,headless=True)
  try:
   page,records,_,errors,_=h.page(browser,f,375,667);h.ready(page)
   page.select_option('#trade-strategy','REBUILD');page.locator('#trade-find').click();h.complete(page)
   result=records[-1]['body'];(root/'search-original.json').write_text(json.dumps(result,indent=2))
   rows=result.get('results') or result.get('exploratory_results') or []
   report={'results':len(result.get('results',[])),'exploratory':len(result.get('exploratory_results',[])),'state':result.get('result_state'),'errors':errors,'cards':[]}
   for i,row in enumerate(rows[:2]):
    e=row['evaluation'];payload={**row['proposal'],'strategy':'REBUILD'}
    second=evaluate_trade_request(f.f.data,payload,projection_reader=f.source.reader)['evaluation']
    fields=['recommendation','generated_trade_eligible','market_evidence','multi_horizon_impact']
    report['cards'].append({'proposal':row['proposal'],'verdict':e['decision_context']['final_decision'],'same_offer_equal':{k:json.loads(json.dumps(e.get(k)))==json.loads(json.dumps(second.get(k))) for k in fields}})
   card=page.locator('.tw-offer').first
   if card.count():
    text=card.inner_text();(root/'primary-card-original.txt').write_text(text)
    report['card_geometry']=card.evaluate('e=>({height:e.getBoundingClientRect().height,paragraphs:e.querySelectorAll(":scope > p").length,action:e.querySelector(".tw-next-action")?.getBoundingClientRect().top-e.getBoundingClientRect().top,details:Array.from(e.querySelectorAll(":scope > details > summary")).map(x=>({label:x.textContent,y:x.getBoundingClientRect().top-e.getBoundingClientRect().top}))})')
    page.screenshot(path=str(root/'recommended-375.png'),full_page=True)
    (root/'report-before-preview.json').write_text(json.dumps(report,indent=2));card.get_by_role('button',name='Open editable offer: preview',exact=True).click()
    report['preview_buttons']=page.locator('#trade-result > button').all_text_contents()
    (root/'preview-original.txt').write_text(page.locator('#trade-result').inner_text())
   print(json.dumps(report,indent=2));(root/'report.json').write_text(json.dumps(report,indent=2));assert not errors
  finally:browser.close()
finally:h.doCleanups()
