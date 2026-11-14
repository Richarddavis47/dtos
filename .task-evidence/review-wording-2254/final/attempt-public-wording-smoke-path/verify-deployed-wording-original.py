from pathlib import Path
from urllib.request import Request,urlopen
from html.parser import HTMLParser
import json,hashlib,datetime
B=Path(__file__).resolve().parent;p=json.loads((B/'production-verified.json').read_text());s=json.loads((B/'source.json').read_text());assert p['passed'] and p['tree']==s['tree']
with urlopen(Request('https://dtos.onrender.com/welcome',headers={'Cache-Control':'no-cache'}),timeout=20) as r:assert r.status==200;raw=r.read(1024*1024+1)
assert len(raw)<=1024*1024;t=raw.decode();assert 'Backup quarterbacks for the flexible starting spot.' in t and 'Superflex replacement cover' not in t and 'Trading a backup quarterback can leave less cover.' in t and 'In Superflex, the flexible starting spot can use a quarterback' in t
class P(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.hrefs=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='details' and a.get('class')=='pw-demo':self.ids.append(a.get('id'))
  if tag=='a':self.hrefs.append(a.get('href'))
d=P();d.feed(t);assert d.ids==['demo-team','demo-trade','demo-values'];assert '/account/register' in d.hrefs
(B/'production-wording-verified.json').write_text(json.dumps(dict(passed=True,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),version=p['version'],build=p['build'],commit=p['commit'],tree=p['tree'],welcome_sha256=hashlib.sha256(raw).hexdigest(),public_team_headline=True,superflex_backup_definition=True,three_read_only_demos=True,registration_link=True,trade_js_verified_in_production_smoke=True,trade_authenticated_owner_acceptance=False,physical_safari=False,scope='One bounded publicWelcomeHTML GET plus independently verified served TradeJS; no new evaluation, leagueentry, sync, savedstatewrite or ownerauthenticatedReview claim.'),indent=2)+'\n');print('Deployed public Team wording, three demos and registration verified; Trade source parity separately verified.')
