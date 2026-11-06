import unittest,json
from tests.test_current_production_coverage import ProductionViewFixture
c=unittest.TestCase();f=ProductionViewFixture(c)
try:
 r=f.f.client.get('/api/market/assets/player:1');x=r.json();print('API',r.status_code,list(x));print('nested',[(k,list(v)[:20]) for k,v in x.items() if isinstance(v,dict)])
 print('prepared',f.f.data['canonical_player_production']['players']['1']['production']['windows'][3])
 for path in ['/market?selected=player%3A1','/players/1?front_office=4']:
  try:
   r=f.f.client.get(path);print('HTML',path,r.status_code,'count', '8 of 8' in r.text,'value','18.00 fantasy points' in r.text,'panel','canonical-production' in r.text)
  except Exception as e: print('ERROR',type(e).__name__,str(e)[:300])
finally:c.doCleanups()
