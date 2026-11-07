from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2239-trade-actionability');root=Path('/workspace/dtos-publisher-2239');s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());proof=json.loads((b/'focused-resource-verified.json').read_text());assert local['candidate']==host['candidate']==proof['candidate']==s['candidate'] and local['tree']==host['tree']==proof['tree']==s['tree'];assert local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4271 and proof['all_native_guards_passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==784
files={}
for folder,prefix in [('canonical','local-canonical'),('readable-console','readable-console'),('host-canonical-readable','host-canonical-readable'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('local-resident-refresh','local-resident-refresh'),('phone','phone'),('candidate','candidate'),('cases','cases'),('zero-result','zero-result'),('hosted-decoded-originals','hosted-decoded-originals'),('hosted-readable-parts','hosted-readable-parts')]:
 for p in (b/folder).rglob('*'):
  if p.is_file() and not (folder=='local-resident-refresh' and 'inputs' in p.relative_to(b/folder).parts):files[prefix+'/'+str(p.relative_to(b/folder))]=p
for n in ['REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','source.json','baseline.json','candidate-production.patch','preservation-review.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','focused-resource-verified.json','renderer-recovery-focused.log','renderer-partial-regression.log','final-candidate-probe.log','final-decision-cases.log','final-phone-interaction.log','zero-result-original.log','final-focused-resource-integrity.log','fois-liveness-control-spawn-safe-original.log','fois-liveness-control.json','fois-liveness-source-boundary.json','publisher-final-tests.log','publisher-final-lint.log','publisher-final-compile.log','publisher-workflow-review.json','prior-package.json','checkpoint-publication.json','checkpoint-public-readback.json','invocation-final.json','live-access-limitation.json']:
 p=b/n;assert p.is_file(),n;files[n]=p
for n in ['run-constrained.py','run-local-canonical.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','run-local-resource.py','candidate_probe.py','decision_case_probe.py','zero_result_probe.py','phone_interaction_probe.py','fois_liveness_control.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py']:
 files['methods/'+n]=b/n
out=root/'.github/release-plans/2239-recovery.zip';secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  raw=p.read_bytes();assert not secret.search(raw),name;z.writestr(name,raw)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
r=dict(candidate=s['candidate'],tree=s['tree'],files=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest());(b/'recovery-package.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
