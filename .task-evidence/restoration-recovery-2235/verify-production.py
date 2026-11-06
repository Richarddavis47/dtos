from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from html.parser import HTMLParser
from datetime import datetime,timezone
import json,subprocess,re
b=Path('/workspace/2235-restoration');repo='repos/Richarddavis47/dtos';expected=json.loads((b/'merged-source.json').read_text())['merge_commit'];tree=json.loads((b/'source.json').read_text())['tree']
def api(path):return json.loads(subprocess.check_output(['gh','api',repo+path],text=True))
run=api('/actions/runs/'+str(json.loads((b/'publication-run.json').read_text())['id']));assert run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==json.loads((b/'merged-source.json').read_text())['publisher']
release=api('/releases/'+str(json.loads((b/'draft-created.json').read_text())['id']));assert not release['draft'] and release['immutable'] and release['tag_name']=='v1.22.20' and release['target_commitish']==expected and len(release['assets'])==21
assert all(a['state']=='uploaded' and a['digest'].startswith('sha256:') for a in release['assets'])
ref=api('/git/ref/tags/v1.22.20')['object'];target=api('/git/tags/'+ref['sha'])['object']['sha'] if ref['type']=='tag' else ref['sha'];assert target==expected
assert api('/git/commits/'+expected)['tree']['sha']==tree
with urlopen(Request('https://dtos.onrender.com/health/ready',headers={'Cache-Control':'no-cache'}),timeout=20) as r:ready=json.load(r)
assert ready['status']=='ready' and ready['version']=='1.22.20' and ready['build']==2235 and ready['deployment']['commit']==expected
reads=[]
for path,code in [('/health/live',200),('/static/js/contextual_navigation.js',200),('/welcome',200),('/account/sign-in',200),('/api/my-dtos',401),('/api/inspect/live/teams',401)]:
 try:
  with urlopen(Request('https://dtos.onrender.com'+path,headers={'Cache-Control':'no-cache'}),timeout=20) as response:
   status=response.status;body=response.read(2*1024*1024).decode()
 except HTTPError as exc:status=exc.code;body=''
 assert status==code,(path,status)
 if path=='/welcome':
  class Text(HTMLParser):
   def __init__(self):super().__init__();self.parts=[];self.hidden=0
   def handle_starttag(self,tag,attrs):
    if tag in ('script','style'):self.hidden+=1
   def handle_endtag(self,tag):
    if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
   def handle_data(self,data):
    if not self.hidden:self.parts.append(data)
  parser=Text();parser.feed(body);assert not re.search(r'\b(?:beta|prerelease|pre-release)\b',' '.join(parser.parts),re.I)
 item={'path':path,'status':status,'guest_read_only':True}
 if path=='/static/js/contextual_navigation.js':
  import hashlib
  candidate=json.loads((b/'source.json').read_text())['candidate']
  original=subprocess.check_output(['git','-C','/workspace/dtos','show',candidate+':static/js/contextual_navigation.js'])
  assert body.encode()==original, 'Deployed navigation asset differs from validated source'
  item['sha256']=hashlib.sha256(original).hexdigest()
  item['bytes']=len(original)
 reads.append(item)
# Authentication wraps league hydration; guest history checks cannot acquire a league.
from urllib.request import build_opener, HTTPRedirectHandler
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self, req, fp, code, msg, headers, newurl): return None
opener=build_opener(NoRedirect)
for path in ['/market','/players/1']:
 try:
  with opener.open(Request('https://dtos.onrender.com'+path,headers={'Cache-Control':'no-cache'}),timeout=20) as response:
   status=response.status;location=response.headers.get('Location','')
 except HTTPError as exc:
  status=exc.code;location=exc.headers.get('Location','')
 assert status==303 and location.startswith('/account/sign-in'),(path,status,location)
 reads.append({'path':path,'status':status,'guest_read_only':True,'scope':'Authentication boundary only; no private Market content or league hydration'})
report={'observed_at':datetime.now(timezone.utc).isoformat(),'production_ready':ready,'reads':reads,'customer_prerelease_wording_matches':[],'scope':'Bounded public unauthenticated reads only. No authenticated league entry, search, synchronization, FOIS rebuild, account login or saved user-data mutation.'}
(b/'production-readonly-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
(b/'publication-verified.json').write_text(json.dumps({'run':run,'release':release,'tag_target':target,'tree':tree,'verification':'Native guarded publisher independently retrieved and verified all attachment bytes before and after immutable publication; Cloud confirms successful exact-source publisher run and matching release digests.'},indent=2)+'\n')
print('Production ready:',ready['version'],ready['build'],ready['deployment']['commit'],'immutable release assets:',len(release['assets']),'guest smoke checks:',len(reads))
