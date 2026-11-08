"""Existing rendered-route assertions at the requested sizes; no live coverage."""
import sys,json
from pathlib import Path
sys.path.insert(0,'/app')
from tests.test_trade_timeline_browser import TradeTimelineBrowserTests,DAY,ARK
sizes=[(320,432),(375,667),(390,844),(1280,900)]
results=[]
for league in [DAY,ARK]:
    h=TradeTimelineBrowserTests();h.setUp()
    try:
        h.run_routes(league,sizes)
        results.append({'league_control':'Day retained timeline' if league==DAY else 'Arkham retained history; no completed trade in capture',
            'viewports':sizes,'existing_route_assertions':'PASS','live':False})
    finally:h.tearDown()
Path('/evidence/phone.json').write_text(json.dumps({'scope':'Actual existing routes and Chromium interception fixtures; no live session or physical Safari',
    'results':results,'limitation':'Arkham history is a layout/isolation control, not a completed trade/Market coverage case.'},indent=2)+'\n')
print('PASS existing phone disclosures, keyboard focus, pick return links and no overflow at four requested sizes',flush=True)
