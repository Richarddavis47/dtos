from pathlib import Path
import json,hashlib,re,zipfile
b=Path('/workspace/2244-trade-comparison');s=json.loads((b/'source.json').read_text());target=Path('/workspace/dtos-publisher-2244/.github/release-plans/2244-prior.zip');files={}
for p in b.iterdir():
 if not p.is_file():continue
 if p.name in ['PRIOR_ATTEMPTS.md','noncanonical-artifact-integrity-original.log','baseline-probe-import-attempt1-original.log','baseline-reproduction-original.log','baseline-reproduction.json','initial-syntax-original.log','final-working-focused-original.log','reload-probe-original.log','focused-state-isolation-original.log','focused-state-isolation-attempt2-original.log','focused-final-original.log','hosted-product-dependency-failure-original.log','hosted-resident-dependency-failure-original.log','hosted-dependency-retry-request.json','hosted-attempt1-product-completed-original.json','product-dependency-retry-original.log','source-probe-original.log','source-probe.json','hosted-product-dependency-failure-diagnosis.json','hosted-attempt1-product-run-original.json','product-rerun-deferred-by-github.json'] or p.name.startswith(('focused-attempt','focused-expanded-attempt')):files[p.name]=p
for p in (b/'hosted-decoded-originals').glob('*.log'):
 if p.name in {'job-'+str(n)+'-original.log' for n in (129649170663,129649170948,129649170984,129649171040,129649171066)}:files['first-attempt-successful-siblings/'+p.name]=p
rows=[];token=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  data=p.read_bytes();assert not token.search(data),name;z.writestr(name,data);rows.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 z.writestr('prior-manifest.json',json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',files=rows,source_boundary='Original working-tree attempts retain their real source qualification. Final-candidate association does not relabel old failures as final proof.'),indent=2)+'\n')
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for row in rows:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
assert target.stat().st_size<100*1024**2
r=dict(files=len(rows),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),original_bytes_verified=True);(b/'prior-package.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
