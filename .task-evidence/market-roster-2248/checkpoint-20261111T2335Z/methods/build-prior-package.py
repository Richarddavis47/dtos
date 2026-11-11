"""Preserve original earlier attempts and the measured 4373 timeout separately."""
from pathlib import Path
import json,hashlib,zipfile,re
B=Path('/workspace/2248-market-needs-final');O=Path('/workspace/2248-market-needs');s=json.loads((B/'source.json').read_text());files={}
p=O/'prior-package.zip';raw=p.read_bytes();assert len(raw)==77815328 and hashlib.sha256(raw).hexdigest()=='b978d42b5703901c5b8dd24235b7bf8d9dea1a7fcea50c7580d50d850b460aa4'
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for n in z.namelist():
  if not n.endswith('/'):files['earlier-attempts/'+n]=z.read(n)
for folder,patterns in [('failed-final-hosted',['*.json','*.jsonl','*.log','SHA256SUMS']),('local-canonical',['canonical.log','canonical-trace.jsonl','unittest-console.log','tests.jsonl','memory.jsonl','result.json','manifest.json','SHA256SUMS']),('hosted-decoded-originals',['*.log','*-transfer.json'])]:
 for pattern in patterns:
  for p in sorted((O/folder).glob(pattern)):
   if p.is_file():files['source-4373/'+folder+'/'+p.name]=p.read_bytes()
for n in ['source.json','candidate.patch','source-transition.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','local-container-stdout-original.log','canonical-budget-reconciliation.json','focused-ready.json','focused-exact-console.log','resource-preservation-verified.json','live-access-boundary.json']:
 p=O/n
 if p.is_file():files['source-4373/'+n]=p.read_bytes()
files['source-4373/ARCHIVE_LOCATION.md']=b'''# Original timed-out native artifact\n\nRun43107670445, job130815143945, artifact13899173695: https://github.com/Richarddavis47/dtos/actions/runs/43107670445/artifacts/13899173695\n\nOriginal ZIP100,241,438bytes, SHA256 bbbeac78c407b33e906a994eeddee228b67edf044b3fc218d0a9bb6a8399aa78; API digest/CRC verified. Kept intact in the original authorized workspace. This archive remains subject to GitHub artifact retention. Original consoles, trace, result, memory measurements and complete internal checksum metadata are included here. Screenshots and other unselected members are not claimed to be reproduced by this log package. The attempt timed out after4272/4399 completions, zero recorded errors/failures/skips; finalthree gates did not execute. Cleanup stopped all descendants. No pass is claimed.\n'''
for n in ['PRIOR_ATTEMPTS.md','canonical-budget-reconciliation.json','source-transition.json']:files[n]=(B/n).read_bytes()
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
for n,r in files.items():
 if Path(n).suffix in {'.json','.jsonl','.log','.md','.py','.txt','.patch'}:assert not pattern.search(r),n
rows=[dict(name=n,bytes=len(r),sha256=hashlib.sha256(r).hexdigest()) for n,r in sorted(files.items())];files['prior-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',files=rows),indent=2)+'\n').encode();p=B/'prior-package.zip';assert not p.exists()
with zipfile.ZipFile(p,'x',zipfile.ZIP_LZMA) as z:
 for n,r in sorted(files.items()):z.writestr(n,r)
with zipfile.ZipFile(p) as z:assert z.testzip() is None
assert p.stat().st_size<100*1024**2
record=dict(source=s,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),members=len(files),scope='Prior development, superseded exact-source timeout and original selected logs; never final passing evidence');(B/'prior-package-complete.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
