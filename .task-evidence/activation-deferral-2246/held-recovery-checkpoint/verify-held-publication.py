from pathlib import Path
from datetime import datetime,timezone
import concurrent.futures,hashlib,json,urllib.parse,urllib.request
b=Path('/workspace/2246-granite-activation');r=json.loads((b/'held-evidence-publication.json').read_text());base='https://raw.githubusercontent.com/Richarddavis47/dtos/'+r['commit']+'/'+r['prefix']+'/'
def get(name,limit):
 with urllib.request.urlopen(urllib.request.Request(base+urllib.parse.quote(name),headers={'Cache-Control':'no-cache'}),timeout=90) as response:
  assert response.status==200;raw=response.read(limit+1)
 assert len(raw)<=limit;return raw
raw=get('publication-manifest.json',4*1024**2);assert hashlib.sha256(raw).hexdigest()==r['manifest_sha256'];m=json.loads(raw);assert m['status']=='HELD' and m['candidate']==r['candidate'] and m['tree']==r['tree']
def verify(row):
 h=hashlib.sha256();size=0
 with urllib.request.urlopen(urllib.request.Request(base+urllib.parse.quote(row['name']),headers={'Cache-Control':'no-cache'}),timeout=90) as response:
  assert response.status==200
  while True:
   data=response.read(1024*1024)
   if not data:break
   size+=len(data);assert size<=row['bytes'];h.update(data)
 assert size==row['bytes'] and h.hexdigest()==row['sha256'],row['name'];return row['name']
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:checked=list(pool.map(verify,m['files']))
sums=dict(x.split('  ',1)[::-1] for x in get('PUBLIC_SHA256SUMS',4*1024**2).decode().splitlines());assert sums=={**{x['name']:x['sha256'] for x in m['files']},'publication-manifest.json':r['manifest_sha256']}
proof=dict(**r,verified_at=datetime.now(timezone.utc).isoformat(),all_public_bytes_read_back=True,verified_files=len(checked),verified_bytes=sum(x['bytes'] for x in m['files']),scope='Committed sanitized held evidence, not a published application release or independent Scout acceptance.')
(b/'held-evidence-public-readback.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
