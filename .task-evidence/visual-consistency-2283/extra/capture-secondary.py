"""Gather same-fixture baseline and candidate captures through the actual HTTP routes."""
from pathlib import Path
from unittest.mock import AsyncMock
import hashlib
import json
import os
import subprocess

from playwright.sync_api import sync_playwright

from dtos_app import page as render_page
from routes.draft import create_draft_router
from routes.public_entry import create_public_entry_router
from tests.test_contextual_back import ContextualBackTests
from tools.validation.browser_runtime import launch_chromium

out=Path('/output')
out.mkdir(exist_ok=True)
helper=ContextualBackTests()
fixture=helper.fixture()
e=fixture.editor
core=dict(ensure_fresh=AsyncMock(),require_data=lambda: e.data,page=render_page)
e.app.include_router(create_draft_router(**core))
e.app.include_router(create_public_entry_router())
e.data["traded_picks"] = [
    dict(season="2028", round=1, roster_id=1, owner_id=2),
    dict(season="2028", round=1, roster_id=2, owner_id=1),
    dict(season="2029", round=2, roster_id=2, owner_id=1),
]
e.data["pick_ledger"] = e.data["traded_picks"]

paths=(('welcome','/welcome'),('picks-grouped','/picks'))
records=[]
try:
    with sync_playwright() as engine:
        browser=launch_chromium(engine,headless=True)
        try:
            for width,height in ((320,432),(390,844),(1280,900)):
                p,requests,_,_,errors=helper.page(browser,fixture,width,height)
                for label,path in paths:
                    response=p.goto(helper.origin+path)
                    if not response.ok:
                        raise RuntimeError(f'{path} {response.status} {p.url}')
                    if label == 'welcome':
                        for demo in ('demo-roster','demo-trade','demo-values'):
                            disclosure=p.locator(f'#{demo} > summary')
                            disclosure.press('Enter')
                            assert p.locator(f'#{demo}').evaluate('node => node.open')
                    else:
                        assert p.locator('.pick-asset-card').count() == 3
                        assert p.locator('.pick-owner').count() == 6
                        p.locator('.pick-asset-card details > summary').first.press('Enter')
                    p.evaluate('document.fonts.ready')
                    filename=f'{label}-{width}.png'
                    p.screenshot(path=str(out/filename),full_page=True)
                    records.append(dict(label=label,url=path,viewport=p.viewport_size,
                        scroll_width=p.evaluate('document.documentElement.scrollWidth'),
                        filename=filename,sha256=hashlib.sha256((out/filename).read_bytes()).hexdigest()))
                p.close()
                assert not errors,errors
                assert not any(method=='POST' for method,_,_ in requests)
        finally:
            browser.close()
finally:
    helper.doCleanups()
git=lambda *a:subprocess.check_output(['git',*a],text=True).strip()
assert git('rev-parse','HEAD')==os.environ['DTOS_EXPECTED_HEAD']
assert not git('status','--porcelain')
(out/'capture.json').write_text(json.dumps(dict(head=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'),
  scope='Disposable prepared authenticated fixture and public sign-in. Viewport screenshots in Chromium.',screenshots=records),indent=2)+'\n')
