"""Actual authenticated routes and tab history; disposable retained-source control."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlsplit
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from src.core.accounts import AccountStore,AccountService
from src.platform.account_context import AccountContextMiddleware
from routes.accounts import create_accounts_router
from tools.validation.browser_runtime import launch_chromium
from tests import test_historical_tracker_phase2 as fixtures

class FollowThroughProbe(unittest.TestCase):
 def setUp(self):
  import dtos_app
  self.f=fixtures.TrackerPhase2Tests();self.f.setUp();self.addCleanup(self.f.tearDown)
  self.f.page_renderer=dtos_app.page
  facts=copy.deepcopy(self.f.fixture.sources[0])
  facts['transactions']['5'].extend(dict(transaction_id='pagination-'+str(i),type='waiver',status='complete',created=1792000000000+i,roster_ids=[4],adds={str(99000+i):4},drops={},draft_picks=[]) for i in range(26))
  self.f.publish(facts)
  self.store=AccountStore(Path(self.f.fixture.temp.name)/'accounts.sqlite3');service=AccountService(self.store)
  self.store.create_account('fixture-account','fixture','Fixture','fixture-hash',[])
  self.store.link_sleeper('fixture-account',sleeper_user_id='fixture-account',username='fixture',display_name='Fixture')
  self.store.upsert_membership('fixture-account',facts['league'],'fixture-account',4,'Fixture franchise','active');self.store.activate('fixture-account',fixtures.DAY)
  app=FastAPI();app.include_router(self.f.app.router);app.include_router(create_accounts_router(service=service,runtime_manager=SimpleNamespace(get=AsyncMock())))
  app.add_middleware(AccountContextMiddleware,service=service,required=True)
  self.client=TestClient(app);self.addCleanup(self.client.close);self.client.cookies.set('dtos_session',service.new_session('fixture-account')[0])
  self.enterContext(patch.object(dtos_app,'account_store',self.store))
  self.static=TestClient(dtos_app.app);self.addCleanup(self.static.close)
 def test_pagination_return(self):
  client,static=self.client,self.static
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_GET(self):
    response=client.get(self.path,follow_redirects=False)
    if response.status_code==404 and self.path.startswith('/static/'):response=static.get(self.path)
    self.send_response(response.status_code)
    for key,value in response.headers.items():
     if key.lower() in ['content-type','location','cache-control']:self.send_header(key,value)
    self.end_headers();self.wfile.write(response.content)
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with sync_playwright() as engine:
    browser=launch_chromium(engine,headless=True)
    try:
     p=browser.new_page(viewport={'width':375,'height':667});p.set_default_timeout(5000)
     origin='http://127.0.0.1:'+str(server.server_port);history='/history/team/'+fixtures.DAY+':franchise:4'
     p.goto(origin+history);p.wait_for_load_state('networkidle')
     p.locator('a[href="'+history+'?events_page=2"]').click();p.wait_for_url('**?events_page=2');p.wait_for_load_state('networkidle')
     p.locator('.franchise-timeline a[href="/trades/history/'+fixtures.ROOT+'"]').click();p.wait_for_url('**/trades/history/'+fixtures.ROOT)
     p.locator('#dtos-back').click();p.wait_for_url('**?events_page=2');p.wait_for_load_state('networkidle')
     result={'path':urlsplit(p.url).path+'?'+urlsplit(p.url).query,'back_href':p.locator('#dtos-back').get_attribute('href'),'scope':p.locator('meta[name="dtos-navigation-scope"]').get_attribute('content'),'ledger':p.evaluate("JSON.parse(sessionStorage.getItem('dtos-contextual-navigation:v1'))")}
     Path('/evidence/baseline-pagination.json').write_text(json.dumps(result,indent=2)+'\n')
     self.assertEqual(result['back_href'],history,'Back must retain the prior meaningful Franchise History page, not skip its pagination.')
    finally:browser.close()
  finally:server.shutdown();server.server_close();thread.join(3);self.assertFalse(thread.is_alive())

if __name__=='__main__':unittest.main(verbosity=2)
