from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2242-trade-partner-history-link');root=Path('/workspace/dtos-publisher-2242');s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());proof=json.loads((b/'focused-resource-verified.json').read_text());assert local['candidate']==host['candidate']==proof['candidate']==s['candidate'] and local['tree']==host['tree']==proof['tree']==s['tree'];assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4316 and proof['all_native_guards_passed'];assert json.loads((b/'product-test-counts.json').read_text())['total']==821
files={}
for folder,prefix in [('canonical','local-canonical'),('readable-console','readable-console'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('local-resident-refresh','local-resident-refresh'),('hosted-decoded-originals','hosted-decoded-originals'),('readable-root-logs','readable-root-logs'),('browser-final-source','partner-history')]:
 for p in (b/folder).rglob('*'):
  if p.is_file() and not (folder=='local-resident-refresh' and 'inputs' in p.relative_to(b/folder).parts):files[prefix+'/'+str(p.relative_to(b/folder))]=p
for name in ['REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','source.json','baseline.json','candidate-production.patch','preservation-review.json','resource-qualification.json','pr-metadata-tooling-note.json','local-container-cleanup.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','public-welcome-test-counts.json','evidence-count-reconciliation.json','focused-resource-verified.json','hosted-partner-history-verified.json','focused-commands.json','final-source-focused.log','focused-precommit.log','final-history-browser-original.log','retained-history-probe.log','publisher-corrected-tests.log','publisher-corrected-lint.log','publisher-preliminary-compile.log','publisher-workflow-review.json','prior-package.json','invocation-final.json','live-access-limitation.json','render-baseline.json','hosted-precanonical-artifacts-verified.json','precanonical-download-receipts.json','hosted-job-log-receipts.json','download-orchestration-note.json','recovery-size-reconciliation.json']:
 p=b/name;assert p.is_file(),name;files[name]=p
files['feature/browser.json']=b/'history-browser-final-source/browser.json';files['feature/feature.json']=b/'retained-history-feature.json'
for p in (b/'history-browser-final-source').glob('*.png'):files['feature/'+p.name]=p
for name in ['run-constrained.py','run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','run-local-resource.py','retained-history-probe.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py','readable-root-logs.py','readable-host-logs.py']:files['methods/'+name]=b/name
out=root/'.github/release-plans/2242-recovery.zip';secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  raw=p.read_bytes();assert not secret.search(raw),name;z.writestr(name,raw)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
r=dict(candidate=s['candidate'],tree=s['tree'],files=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest());(b/'recovery-package.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
