"""Freeze exact-source successful validation and declared synthetic measurements."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2237-cache-duplication');root=Path('/workspace/dtos-publisher-2237');m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());memory=json.loads((b/'cache-memory-verified.json').read_text())
assert local['tests']==host['tests']==4250 and local['all_local_gates_passed'] and host['all_gates_passed']
for x in [local,host,memory]:assert x['candidate']==m['candidate'] and x['tree']==m['tree']
assert memory['passed'] and len(memory['kernel_cases'])==4
assert re.search(rb'Ran 63 tests in [0-9.]+s\s+OK\s*$',(b/'focused-final-exact.log').read_bytes())
assert json.loads((b/'resource-verified.json').read_text())['all_native_guards_passed']
assert json.loads((b/'complete-payload-verified.json').read_text())['passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==757
files={}
for folder,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('readable-console','readable-console')]:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[prefix+'/'+str(p.relative_to(b/folder))]=p
for p in (b/'fixture').glob('*'):
 if p.is_file() and (p.name in ['oneqb.json','superflex.json','projections.sqlite3']):files['synthetic-fixtures/'+p.name]=p
# Profiles and their methods are raw evidence, not production-data exports.
for pattern in ['profile-*.json','profile-*.log','profile-*.py','baseline-original-profile-*.json','warm-cycles*.json','warm-cycles*.log','*fixture-metadata.json','*fixture-build.log']:
 for p in b.glob(pattern):files['studies/'+p.name]=p
names=['source.json','BASELINE.json','REPORT.md','SCOUT_HANDOFF.md','commands.md','candidate-production.patch','source-integrity.json','source-reconciliation.json','production-baseline.log','pre-release-baseline-check.json','version-availability.json','focused-final-exact.log','lint-final-exact.log','canonical-final-console.log','local-verified.json','host-canonical-verified.json','product-test-counts.json','product-jobs.json','resource-verified.json','lifecycle-verified.json','artifact-download-receipts.jsonl','hosted-final-records.json','cache-memory-verified.json','cache-memory-verification.log','complete-payload-verified.json','complete-payload-verification.log','fixture-metadata.json','fixture-locations.json','fixture-build.log','build-fixture.py','diverse-fixture.py','unicode-fixture.py','profile-combined.py','profile-variants.py','warm-cycles.py','verify-memory.py','verify-complete-payload.py','run-constrained.py','run-clean-final.py','invocation-final.json','verify-local-canonical.py','verify-host-canonical.py','verify-product-artifacts.py','verify-lifecycle.py','verify-certificate.py','verify-recovery-offline.py','publisher-focused.log','publisher-focused-attempt-records.log','publisher-focused-final.log','publisher-lint-attempt-records-first.log','publisher-lint-final.log','publisher-compilation.json','product-artifact-integrity.log','lifecycle-artifact-integrity.log','local-canonical-integrity.log','host-canonical-integrity.log','make-report.py','package-final.py','package-prior.py','package-prior-report.json','finalize-plan.py','LIVE_ACCEPTANCE_STATUS.json','host-watch-attempt2.log','hosted-records-capture.log','packaging-precondition-note.json','render-baseline-metadata.json','readiness-during-host-retry.json']
for n in names:
 p=b/n;assert p.is_file(),n;files[n]=p
out=root/'.github/release-plans/2237-recovery.zip';assert not out.exists()
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,p in sorted(files.items()):
  if p.suffix in ['.json','.jsonl','.log','.md','.py','.patch','.txt','.html','.js']:assert not secret.search(p.read_bytes()),n
  z.write(p,n)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
(b/'package-final-report.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],files=len(files),bytes=out.stat().st_size,sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest()),indent=2)+'\n');print('Final evidence payloads:',len(files))
