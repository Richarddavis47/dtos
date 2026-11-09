from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2242-trade-partner-history-link');root=Path('/workspace/dtos-publisher-2242');s=json.loads((b/'source.json').read_text())
names=['PRIOR_ATTEMPTS.md','focused-precommit.log','lint-precommit.log','lint-corrected-precommit.log','publisher-preliminary-tests.log','publisher-preliminary-lint.log','publisher-preliminary-compile.log','publisher-corrected-tests.log','publisher-corrected-lint.log','scratch-recovery.json','scratch-identical-inputs.json','evidence-count-reconciliation.json']+[f'focused-attempt-{i}.log' for i in range(1,7)]
files={name:(b/name).read_bytes() for name in names}
for folder in ['focused-precommit','focused-attempt-6']:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[folder+'/'+str(p.relative_to(b/folder))]=p.read_bytes()
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for name,raw in files.items():
 assert not secret.search(raw),name;rows.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
files['prior-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',source_boundary='Original failed/preliminary controls and precommit working-tree reports. Their recorded HEAD does not claim a clean final tree or a rendered production-baseline observation.',files=rows),indent=2)+'\n').encode()
out=root/'.github/release-plans/2242-prior.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name,raw in sorted(files.items()):z.writestr(name,raw)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
r=dict(files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest());(b/'prior-package.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
