from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess,urllib.request,urllib.parse
b=Path('/workspace/2245-recommended-protections');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/recommended-protections-2245/prior-local-80m';commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();out=repo/prefix;m=json.loads((out/'manifest.json').read_text());rows=m['files']+[dict(name=n,bytes=(out/n).stat().st_size,sha256=hashlib.sha256((out/n).read_bytes()).hexdigest()) for n in ['manifest.json','SHA256SUMS']]
def verify(r):
 url='https://raw.githubusercontent.com/Richarddavis47/dtos/'+commit+'/'+prefix+'/'+urllib.parse.quote(r['name'],safe='/')
 with urllib.request.urlopen(url,timeout=60) as f:data=f.read(r['bytes']+1)
 assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'],r['name']
 return r
with ThreadPoolExecutor(max_workers=6) as pool:checked=list(pool.map(verify,rows))
r=dict(commit=commit,prefix=prefix,all_bytes_verified=True,files=checked,total_payload_bytes=sum(x['bytes'] for x in checked),scope='Existing authorized public Git handoff; all original final-source incomplete local80min evidence read back from fixed commit. Not a passing test claim.');(b/'prior-local-public-readback.json').write_text(json.dumps(r,indent=2)+'\n');print(commit,len(checked),r['total_payload_bytes'])
