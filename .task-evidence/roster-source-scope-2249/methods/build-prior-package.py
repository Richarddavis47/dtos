"""Seal actual earlier originals with explicit exclusions and outcomes."""
from pathlib import Path,PurePosixPath
import json,hashlib,zipfile,re
B=Path('/workspace/2249-sleeper-relevance');s=json.loads((B/'source.json').read_text());files={}
def add(name,p):
 p=Path(p);assert p.is_file() and not p.is_symlink();assert name not in files;files[name]=p.read_bytes()
for folder in ['focus-1','focus-2','focus-browser-1','focus-browser-2','focus-browser-3','focus-provenance-fix','prior-local-c821','canonical-created-before-core']:
 for p in sorted((B/folder).rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  # Retain test evidence and exact source patches; input databases and duplicated
  # frozen fixture archive are referenced by original SHA256, not replicated.
  if 'fixture' in p.relative_to(B/folder).parts or 'local-resource-inputs' in p.parts:continue
  if p.suffix in ['.json','.jsonl','.log','.md','.py','.patch','.txt'] or p.name=='SHA256SUMS':add(folder+'/'+str(p.relative_to(B/folder)),p)
prior=B/'prior-hosted-c821'
for name in ['130955607520.decoded.log','130955607615.decoded.log','RECONCILIATION.json','transport-boundary-sanitized.json']:add('prior-hosted-c821/'+name,prior/name)
# The original APIs stay private; publish only whitelisted validation metadata.
records=[]
for run in [43149667688,43149667725,43149667697,43149667665]:
 r=json.loads((prior/(str(run)+'-run.json')).read_text());jobs=json.loads((prior/(str(run)+'-jobs.json')).read_text())['jobs'];arts=json.loads((prior/(str(run)+'-artifacts.json')).read_text())['artifacts']
 record=dict(run={k:r.get(k) for k in ['id','name','path','event','head_sha','head_branch','status','conclusion','created_at','updated_at','html_url','run_attempt']},jobs=[{k:j.get(k) for k in ['id','run_id','name','head_sha','status','conclusion','started_at','completed_at','html_url','steps']} for j in jobs],artifacts=[{k:a.get(k) for k in ['id','name','size_in_bytes','expired','digest','created_at','updated_at','workflow_run']} for a in arts]);records.append(record)
files['prior-hosted-c821/validation-metadata-sanitized.json']=(json.dumps(records,indent=2)+'\n').encode()
for name,sha in [('welcome-failed-original.zip','4b4b6f00c2f8d63f9b1fbd7f26338b25d7cab842b9b2e39f8c1dd66b6401adb0'),('canonical-cancelled-original.zip','54867f5d76eda7f7b741056488c51652a7a24edbc0415cc5735a4a96a0adba00')]:
 p=prior/'native-originals'/name;assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==sha
 with zipfile.ZipFile(p) as z:assert z.testzip() is None
 add('prior-hosted-c821/native-originals/'+name,p)
add('PRIOR_ATTEMPTS.md',B/'PRIOR_ATTEMPTS.md')
pattern=re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})')
for n,raw in files.items():
 if Path(n).suffix in ['.json','.jsonl','.log','.md','.py','.txt','.patch']:assert not pattern.search(raw),n
rows=[dict(name=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(files.items())];files['prior-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='Prior/superseded attempts only; no finalpass claim',files=rows),indent=2)+'\n').encode();p=B/'prior-package.zip';assert not p.exists()
with zipfile.ZipFile(p,'x',zipfile.ZIP_LZMA) as z:
 for n,raw in sorted(files.items()):z.writestr(n,raw)
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 for row in rows:raw=z.read(row['name']);assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
assert p.stat().st_size<100*1024**2
record=dict(source=s,bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),members=len(files),scope='Prior-only originals; failed/cancelled/incomplete remain distinct. One42MBnativecancelled archive is stored separately underprior-originals in recovery. Raw signedredirectstderr excluded.')
(B/'prior-package-complete.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
