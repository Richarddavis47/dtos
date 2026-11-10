from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures,hashlib,json,urllib.parse,urllib.request
b=Path('/workspace/2244-trade-comparison');r=json.loads((b/'final-evidence-publication.json').read_text());base='https://raw.githubusercontent.com/Richarddavis47/dtos/'+r['evidence_commit']+'/'+r['prefix']+'/'
def get(name,limit):
 with urllib.request.urlopen(urllib.request.Request(base+urllib.parse.quote(name),headers={'Cache-Control':'no-cache'}),timeout=90) as response:
  assert response.status==200;data=response.read(limit+1)
 assert len(data)<=limit;return data
raw=get('manifest.json',4*1024**2);assert hashlib.sha256(raw).hexdigest()==r['manifest_sha256'];m=json.loads(raw)
def verify(row):
 data=get(row['name'],row['bytes']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['name'];return row['name']
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:checked=list(pool.map(verify,m['files']))
sums=dict(x.split('  ',1)[::-1] for x in get('SHA256SUMS',4*1024**2).decode().splitlines());assert sums=={**{x['name']:x['sha256'] for x in m['files']},'manifest.json':r['manifest_sha256']}
r.update(verified_at=datetime.now(timezone.utc).isoformat(),published_bytes_readback=True,verified_files=len(checked),candidate=m['candidate'],tree=m['tree'],deployed_commit=m['deployed_commit'],scope='All delivered public bytes fetched and matched; independent Scout review and authenticated My Team/Trade handoff acceptance remain separate.')
(b/'final-evidence-public-readback.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
