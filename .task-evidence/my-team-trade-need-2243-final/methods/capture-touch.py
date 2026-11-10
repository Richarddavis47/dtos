"""Supplemental real CDP touch control, not physical Safari or a test-count claim."""
from pathlib import Path
import json
import subprocess
import sys
sys.path.insert(0, '/app')
from tests.test_team_trade_need_browser import TeamTradeNeedBrowserTests
from playwright.sync_api import sync_playwright
from tools.validation.browser_runtime import launch_chromium

case = TeamTradeNeedBrowserTests()
rows = []
try:
    helper, fixture = case.fixture()
    with sync_playwright() as engine:
        browser = launch_chromium(engine, headless=True)
        try:
            for width, height in [(320, 432), (375, 667), (390, 844)]:
                page, requests, _, _, errors = helper.page(browser, fixture, width, height)
                try:
                    helper.ready(page)
                    helper.choose(page)
                    page.locator('#trade-valuation-mode').select_option('custom')
                    before = helper.draft(page)
                    page.goto(helper.origin + '/teams/1', wait_until='networkidle')
                    cdp = page.context.new_cdp_session(page)
                    cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True})
                    def tap(selector):
                        item = page.locator(selector)
                        item.scroll_into_view_if_needed()
                        box = item.bounding_box()
                        assert box['height'] >= 44
                        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2}]})
                        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                    tap('#my-team-trade-need')
                    page.wait_for_function("document.querySelector('#trade-context') && !document.querySelector('#trade-context').textContent.includes('Loading')")
                    assert page.locator('#recommendation-position').input_value() == 'RB'
                    tap('#recommendation-position-clear')
                    assert page.locator('#recommendation-position').input_value() == ''
                    assert helper.draft(page)['currentProposal'] == before['currentProposal']
                    assert helper.draft(page)['valuationMode'] == 'custom'
                    assert not [row for row in requests if row[0] == 'POST']
                    helper.back(page, '/teams/1')
                    assert page.locator('#my-team-trade-need').inner_text() == 'Explore RB trades'
                    assert not errors
                    cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': False})
                    cdp.detach()
                    rows.append(dict(width=width, height=height, action_touch=True, clear_touch=True, back=True, draft_custom_preserved=True, automatic_posts=0, errors=errors))
                finally:
                    page.close()
        finally:
            browser.close()
    output = Path('/evidence/position-filter-layout/touch.json')
    output.write_text(json.dumps(dict(candidate=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], text=True).strip(), scope='Source-pinned disposable authenticated Chromium CDP touch; no physical iPhone/Safari acceptance; supplemental control not added to unittest counts', rows=rows), indent=2) + '\n')
    print(json.dumps(rows))
finally:
    case.doCleanups()
