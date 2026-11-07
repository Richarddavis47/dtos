import sys
sys.path.insert(0,'/app')
from pathlib import Path
import json,subprocess
from playwright.sync_api import sync_playwright
from tests import test_trade_workflow_experience as fixtures
from tools.validation.browser_runtime import launch_chromium
b=Path('/evidence/phone');b.mkdir(exist_ok=True);h=fixtures.TradeWorkflowExperienceTests();f=h.fixture();rows=[]
try:
 with sync_playwright() as pw:
  browser=launch_chromium(pw,headless=True)
  try:
   for w,hh in [(320,432),(375,667),(390,844),(1280,900)]:
    page,records,_,errors,_=h.page(browser,f,w,hh);h.ready(page);page.select_option('#trade-strategy','REBUILD');page.locator('#trade-find').click();h.complete(page)
    action=page.locator('.tw-offer').first.locator(':scope > .tw-next-action');action.focus();page.keyboard.press('Enter');assert 'Alternative preview' in page.locator('#trade-result').inner_text();assert page.locator('#trade-result').evaluate('e=>e===document.activeElement')
    page.get_by_role('button',name='Keep original',exact=True).focus();page.keyboard.press('Enter');assert page.locator('#trade-strategy').input_value()=='REBUILD'
    action=page.locator('.tw-offer').first.locator(':scope > .tw-next-action');action.scroll_into_view_if_needed();rect=action.bounding_box();x=rect['x']+rect['width']/2;y=rect['y']+rect['height']/2
    assert action.evaluate('(e,p)=>e===document.elementFromPoint(p.x,p.y)',dict(x=x,y=y))
    style=action.evaluate('e=>({foreground:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,height:e.getBoundingClientRect().height})')
    assert style['height']>=44
    if w<500:
     c=page.context.new_cdp_session(page);c.send('Emulation.setTouchEmulationEnabled',dict(enabled=True,maxTouchPoints=1));c.send('Input.dispatchTouchEvent',dict(type='touchStart',touchPoints=[dict(x=x,y=y)]));c.send('Input.dispatchTouchEvent',dict(type='touchEnd',touchPoints=[]));page.get_by_role('button',name='Keep original',exact=True).wait_for();c.detach()
    assert not errors;assert page.evaluate('document.documentElement.scrollWidth')<=w
    rows.append(dict(viewport=[w,hh],keyboard_preview=True,keyboard_keep_original=True,result_focus=True,action_unobstructed=True,touch_emulated=w<500,style=style,overflow=False,extra_searches=len(records)-1,errors=errors));page.close()
  finally:browser.close()
finally:h.doCleanups()
r=dict(source=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],text=True).splitlines(),scope='Disposable actual HTTP with released JS; CDP touch and keyboard, not physical Safari or live account acceptance',records=rows);(b/'interaction.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
