from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,zipfile,io
b=Path('/workspace/2237-cache-duplication');p=json.loads((b/'reconciliation-publication.json').read_text());commit=p['evidence_commit'];relative='.task-evidence/cache-string-sharing-2237-reconciliation';root=Path('/workspace/cache-sharing-handoff')/relative;base='https://raw.githubusercontent.com/Richarddavis47/dtos/'+commit+'/'+relative+'/'
def read(name,expected):
 with urlopen(Request(base+name,headers={'User-Agent':'DTOS-evidence-verification'}),timeout=30) as response:data=response.read(len(expected)+1)
 assert data==expected,name
 return data
archive=read('study-evidence.zip',(root/'study-evidence.zip').read_bytes());assert len(archive)==p['bytes'] and hashlib.sha256(archive).hexdigest()==p['sha256']
with zipfile.ZipFile(io.BytesIO(archive)) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('manifest.json'));rows=manifest['files'];assert len(rows)==108 and manifest['application_changes'] is False
 assert hashlib.sha256(z.read('manifest.json')).hexdigest()==p['manifest_sha256']
 sums=dict(line.split('  ',1)[::-1] for line in z.read('SHA256SUMS').decode().splitlines());assert set(sums)=={x['name'] for x in rows}|{'manifest.json'}
 for x in rows:
  assert not x['name'].startswith('/') and '..' not in Path(x['name']).parts
  data=z.read(x['name']);assert len(data)==x['bytes'] and hashlib.sha256(data).hexdigest()==x['sha256']==sums[x['name']]
 assert sums['manifest.json']==p['manifest_sha256']
files=rows+[{'name':n,'bytes':(root/n).stat().st_size,'sha256':hashlib.sha256((root/n).read_bytes()).hexdigest()} for n in ['manifest.json','SHA256SUMS','study-evidence.zip','DOWNLOADS.json','DOWNLOADS.SHA256SUMS']]
def check(x):
 data=read(x['name'],(root/x['name']).read_bytes());assert len(data)==x['bytes'] and hashlib.sha256(data).hexdigest()==x['sha256'];return x
with ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(check,files))
result=dict(observed_at=datetime.now(timezone.utc).isoformat(),evidence_commit=commit,baseline=manifest['baseline'],tree=manifest['tree'],status=manifest['status'],archive_url=base+'study-evidence.zip',archive_bytes=len(archive),archive_sha256=p['sha256'],manifest_sha256=p['manifest_sha256'],verified_files=len(verified),all_archive_payloads_and_raw_published_files_matched=True,files=verified,scope='Actual public archive and individual raw file downloads. No production private access or new release.')
(b/'reconciliation-public-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
