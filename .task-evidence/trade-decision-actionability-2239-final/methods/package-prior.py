from pathlib import Path
import json,hashlib,re,zipfile
b=Path('/workspace/2239-trade-actionability');s=json.loads((b/'source.json').read_text());out=Path('/workspace/dtos-publisher-2239/.github/release-plans/2239-prior.zip');files={}
for pattern in ['baseline-probe-*.log','baseline-probe-prior*.py','focused-new-attempt*.log','focused-existing-initial.log','focused-all-attempt5.log','focused-lint.log','publisher-initial-*.log','product-attempt1-original-decoded.log*','canonical-cancelled-90-original.zip','canonical-cancelled-90-original-decoded.log*','prior90-cancellation.json','prior90-host-canonical-integrity.json','prior90-source.json','prior90-invocation-final.json','prior90-local-canonical-launch.log','prior90-source-generated-validation.zip*','prior90-disposable-foundation.zip*','prior90-focused-resource-verified.json','prior-*-artifact-metadata.json','host-canonical-superseded-status.json','cancel-superseded-*.log','renderer-recovery-focused.log','renderer-partial-regression.log','fois-liveness-control-original.log','fois-liveness-control-prior-spawn-unsafe.json','fois_liveness_control-prior-spawn-unsafe.py','final-focused-resource-integrity-prior-cwd.log','focused-resource-integrity.log']:
 for p in b.glob(pattern):
  if p.is_file():files['prior/'+p.name]=p
for folder in ['prior90-local-canonical-cancelled','prior90-host-canonical-readable']:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[folder+'/'+str(p.relative_to(b/folder))]=p
files['PRIOR_ATTEMPTS.md']=b/'PRIOR_ATTEMPTS.md';files['checkpoint-publication.json']=b/'checkpoint-publication.json';files['checkpoint-public-readback.json']=b/'checkpoint-public-readback.json'
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  raw=p.read_bytes();assert not secret.search(raw),name;z.writestr(name,raw);rows.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 z.writestr('prior-manifest.json',json.dumps({'candidate':s['candidate'],'tree':s['tree'],'scope':'prior-attempts-only','files':rows},indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for r in rows:assert hashlib.sha256(z.read(r['name'])).hexdigest()==r['sha256']
assert out.stat().st_size<100*1024**2
r=dict(candidate=s['candidate'],tree=s['tree'],files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),scope='Failed/cancelled/precommit outcomes are separate from final mandatory evidence. No unavailable completion records are reconstructed.');(b/'prior-package.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
