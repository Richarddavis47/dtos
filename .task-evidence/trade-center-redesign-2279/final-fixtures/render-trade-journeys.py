"""Capture matching disposable, authenticated fixture journeys through the real application shell."""
from importlib import import_module
import json
from pathlib import Path
import subprocess

from playwright.sync_api import sync_playwright

from tools.validation.browser_runtime import launch_chromium

root = Path('/output')
workflows = import_module('tests.test_00_trade_workflow_experience')
h = workflows.TradeWorkflowExperienceTests()
f = h.fixture()
observations = []

def take(page, key, width, target):
    locator = page.locator(target).first
    locator.wait_for()
    locator.evaluate("e=>e.scrollIntoView({block:'start'})")
    page.screenshot(path=str(root/f'{key}-{width}.png'))
    if page.evaluate('document.documentElement.scrollWidth') > width:
        raise AssertionError(f'{key} overflows at {width}px')

def result_fields(row):
    return {key: row['evaluation'].get(key) for key in (
        'recommendation','generated_trade_eligible','market_evidence','multi_horizon_impact',
        'personal_value_evidence','draft_capital_record','recommendation_trace',
    )}

try:
    with sync_playwright() as engine:
        browser = launch_chromium(engine, headless=True)
        for width, height in ((320, 640), (390, 844), (1280, 900)):
            page, requests, _, errors, _ = h.page(browser, f, width, height)
            h.ready(page)
            assert requests == []
            page.select_option('#trade-strategy', 'REBUILD')
            page.locator('#trade-find').click()
            h.complete(page)
            outcome = requests[-1]['body']
            row = next(r for r in outcome['results'] if r['evaluation']['generated_trade_eligible'])
            take(page,'recommended',width, '#trade-result .tw-offer-summary')
            page.locator('#trade-result .tw-offer-summary .tw-next-action').first.click()
            if page.locator('.tw-projected-points > summary').count():
                page.locator('.tw-projected-points > summary').press('Enter')
            take(page,'review',width,'#trade-result .tw-offer-review')
            page.get_by_role('button', name='Back to offers').click()
            assert len(requests)==1
            h.ready(page,'create')
            page.select_option('#trade-strategy','REBUILD')
            proposal=row['proposal']
            page.select_option('#trade-partner',str(proposal['partner_roster_id']))
            for side, ids in (('sent',proposal['assets_sent']),('received',proposal['assets_received'])):
                add=page.locator(f'[data-add-side="{side}"]')
                if add.count():
                    add.click()
                elif page.locator(f'[data-side="{side}"]').is_visible():
                    page.locator(f'[data-side="{side}"]').click()
                for asset in ids:
                    page.locator(f'#trade-{side}-board button[data-asset-id="{asset}"]').click()
            take(page,'build',width,'.tw-calculator')
            page.locator('#trade-run').click()
            page.locator('#trade-result[data-assessment=true]').wait_for()
            evaluated=requests[-1]['body']
            if page.locator('.tw-projected-points > summary').count():
                page.locator('.tw-projected-points > summary').press('Enter')
            take(page,'evaluated',width,'#trade-result')
            page.locator('#trade-edit').click()
            assert page.locator('#trade-board').is_visible()
            assert requests[-1]['payload']['assets_sent']==proposal['assets_sent']
            assert requests[-1]['payload']['assets_received']==proposal['assets_received']
            assert not errors,errors
            observations.append(dict(width=width,proposal=proposal,review=result_fields(row),evaluated=result_fields(evaluated)))
            page.close()
        browser.close()
finally:
    h.doCleanups()
identity = subprocess.check_output(['git','log','-1','--format=%H %T'],text=True).split()
(root/'semantic.json').write_text(json.dumps(dict(commit=identity[0],tree=identity[1],scope='Identical disposable prepared facts and business routes', observations=observations),indent=2)+'\n')
