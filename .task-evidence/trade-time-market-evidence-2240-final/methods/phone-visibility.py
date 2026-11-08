"""Independent viewport evidence: age readable after normal disclosure/scroll."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,'/app')
from tests import test_trade_time_market_evidence as fixtures
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium
import dtos_app

h=fixtures.TradeTimeMarketEvidenceTests();h.setUp()
out=Path('/evidence/phone-visibility');out.mkdir(exist_ok=True)
rows=[]
try:
    h.capture(value=321);h.f.page_renderer=dtos_app.page
    with sync_playwright() as pw:
        browser=launch_chromium(pw,headless=True)
        try:
            for w,ht in [(320,432),(375,667),(390,844),(1280,900)]:
                page=browser.new_page(viewport={'width':w,'height':ht})
                def respond(route):
                    r=h.f.client.get(route.request.url.replace('http://fixture',''))
                    route.fulfill(status=r.status_code,body=r.content,content_type=r.headers.get('content-type','text/html'))
                page.route('http://fixture/**',respond)
                assert page.goto('http://fixture/trades/history/'+fixtures.fixtures.ROOT).status==200
                section=page.locator('section.card').filter(has=page.get_by_role('heading',name='At the time: Market evidence',exact=True))
                summary=section.locator(':scope > details > summary');summary.scroll_into_view_if_needed();summary.press('Enter')
                age=section.locator('.timeline-quote').first.locator(':scope > p').filter(has_text='Quote age:')
                age.evaluate('e=>e.scrollIntoView({block:"center"})')
                proof=age.evaluate('''e=>{const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;const hit=document.elementFromPoint(x,y);return {text:e.textContent,top:r.top,bottom:r.bottom,viewport:innerHeight,unobstructed:e===hit||e.contains(hit)}}''')
                assert proof['unobstructed'] and proof['top']>=0 and proof['bottom']<=ht
                assert '1 hour before the trade' in proof['text']
                assert page.evaluate('document.documentElement.scrollWidth')<=w
                page.screenshot(path=str(out/f'age-visible-{w}.png'))
                rows.append(dict(width=w,height=ht,**proof));page.close()
        finally:browser.close()
finally:h.doCleanups()
git=lambda *a:subprocess.check_output(['git',*a],text=True).strip()
report=dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),working_tree_clean=not git('status','--porcelain'),records=rows,
    scope='Disposable Chromium viewport/click/scroll control; fixed bottom navigation preserved. Whole-element screenshots can capture a fixed bar over offscreen rows; these viewport screenshots prove age can be brought into view. No physical Safari claim.')
(out/'visibility.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
