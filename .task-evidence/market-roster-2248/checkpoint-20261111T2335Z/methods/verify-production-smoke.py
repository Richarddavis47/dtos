from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import json,subprocess,hashlib,time,datetime
B=Path('/workspace/2248-market-needs-final');source=json.loads((B/'source.json').read_text()); receipt=json.loads((B/'merge-verified.json').read_text()); sha=receipt['merge_commit'];tree=source['tree'];origin='https://dtos.onrender.com';reads=[];ready=None
for path,expected in [('/health/ready',200),('/health/live',200),('/welcome',200),('/account/sign-in',200),('/api/my-dtos',401),('/static/js/trade_comparison.js',200),('/static/js/trade_workspace.js',200)]:
    began=time.monotonic();observed=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with urlopen(Request(origin+path,headers={'Cache-Control':'no-cache'}),timeout=20) as response:code=response.status;body=response.read(4*1024*1024+1)
    except HTTPError as error:code=error.code;body=error.read(4*1024*1024+1)
    assert code==expected and len(body)<=4*1024*1024,(path,code)
    record=dict(path=path,status=code,observed_at=observed,elapsed_network_seconds=time.monotonic()-began,bytes=len(body))
    if path=='/health/ready':
        ready=json.loads(body);assert ready['status']=='ready' and ready['version']==source['version'] and ready['build']==2248 and ready['deployment']['commit']==sha and ready['deployment']['branch']=='main';record['readiness']=ready
    if path.startswith('/static/'):
        original=subprocess.run(['git','show',sha+':'+path.lstrip('/')],cwd='/workspace/dtos-market-needs-2248',capture_output=True,check=True).stdout
        assert body==original,(path,'served bytes differ');record.update(sha256=hashlib.sha256(body).hexdigest(),matches_exact_merged_source=True)
    reads.append(record)
(B/'production-smoke-original.json').write_text(json.dumps(dict(reads=reads,readiness=ready,scope='Seven bounded public read-only requests; no owner authentication, heavy work or data mutations. Timing includes network and is not isolated server liveness latency.'),indent=2)+'\n')
(B/'production-verified.json').write_text(json.dumps(dict(passed=True,version=ready['version'],build=ready['build'],commit=sha,tree=tree,ready=True,static_files_equal_validated_source=True,ordinary_public_smoke_passed=True,authenticated_owner_acceptance=False,authenticated_limitation='Supported owner-browser control and Render Shell session not exposed; no unchanged external inspection401 retry.',scope='Public HTTP and independently verified Git tree; fixtures/live owner evidence remain distinct.',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat()),indent=2)+'\n')
print(json.dumps(dict(passed=True,version=ready['version'],build=ready['build'],commit=sha,reads=len(reads),static_source_parity=True,owner_live=False)))
