"""Seal verified exact-source evidence only after mandatory gates pass."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2235-restoration');m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree']
assert local['tests']==host['tests']==4229 and local['all_local_gates_passed'] and host['all_gates_passed']
assert re.search(rb'Ran 69 tests in [0-9.]+s\s+OK\s*$',(b/'focused-exact.log').read_bytes())
assert json.loads((b/'local-preflight/result.json').read_text())['passed']
assert json.loads((b/'resource-final/result.json').read_text())['passed']
assert json.loads((b/'cycles/result.json').read_text())['passed']
assert json.loads((b/'liveness/result.json').read_text())['passed']
assert json.loads((b/'resource-verified.json').read_text())['all_native_guards_passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==745
files={}
for folder,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('readable-console','readable-console'),('cycles','cycles'),('liveness','liveness'),('matched-baseline','matched-baseline')]:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[prefix+'/'+str(p.relative_to(b/folder))]=p
names=['lifecycle-control-results.json','commands.md','REPORT.md','SCOUT_HANDOFF.md','source.json','source-integrity.json','candidate-production.patch','baseline.json','production-baseline-readiness.json','render-service-baseline.json','version-availability.json','measurements.json','matched-before-after.json','baseline-recovery-probe.json','baseline-recovery-probe.log','recovery_probe.py','matched-baseline-control.py','matched-baseline.log','restore-cycles.py','cycles.log','restore-liveness.py','restore-liveness.log','focused-exact.log','canonical-console.log','ruff-final.log','harness-preservation.json','run-constrained.py','run-clean.py','invocation.json','clean-checkout.log','local-verified.json','host-canonical-verified.json','resource-verified.json','lifecycle-verified.json','verify-local-canonical.py','verify-host-canonical.py','verify-product-artifacts.py','verify-lifecycle.py','product-artifact-integrity-final.log','lifecycle-artifact-integrity.log','local-canonical-integrity.log','host-canonical-integrity.log','publisher-focused-final.log','publisher-lint-final.log','publisher-compilation.log','product-test-counts.json','product-jobs.json','artifact-download-receipts.jsonl','hosted-final-records.json','scratch-reclamation.json','prior-original-archive-preservation.json','immutable-download-retirement.json','post-validation-source-clean.json','make-report.py','package-final.py','package-prior.py','package-prior-report.json','finalize-plan.py']
for name in names:
 p=b/name;assert p.is_file(),name;files[name]=p
out=Path('/workspace/dtos-publisher-2235/.github/release-plans/2235-recovery.zip');assert not out.exists()
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(p.read_bytes()),name
  z.write(p,name)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
print(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],payloads=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
