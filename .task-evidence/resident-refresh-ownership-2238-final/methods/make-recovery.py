"""Package only verified exact-source completed evidence, preserving prior bytes separately."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');out=Path('/workspace/dtos-publisher-2238/.github/release-plans/2238-recovery.zip');m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['all_local_gates_passed'] and host['all_gates_passed'] and local['tests']==host['tests']==4261
assert re.search(rb'Ran 123 tests in [0-9.]+s\s+OK\s*$',(b/'focused-final-49-writable.log').read_bytes())
assert re.search(rb'Ran 50 tests in [0-9.]+s\s+OK\s*$',(b/'publisher-tests-final49.log').read_bytes())
resource=json.loads((r/'resource-final-49/result.json').read_text());assert resource['passed'] and resource['head']==m['candidate'] and resource['tree']==m['tree']
assert json.loads((b/'resident-host-final-verified.json').read_text())['passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==757
files={}
for folder,prefix in [(b/'canonical','local-canonical'),(b/'readable-console','readable-console'),(b/'host-canonical-readable','host-canonical-readable'),(r/'local-preflight-49','local-preflight'),(r/'local-restoration-unused-49','local-restoration-unused'),(r/'resource-final-49','local-resident-refresh')]:
 for p in folder.rglob('*'):
  if p.is_file():files[prefix+'/'+str(p.relative_to(folder))]=p
for p in (b/'hosted-decoded-originals').rglob('*'):
 if p.is_file():files['hosted-decoded-originals/'+str(p.relative_to(b/'hosted-decoded-originals'))]=p
for pattern in ['memory-final-*.json','memory-final-*.log','memory-accounting-detail.json','global-memory-*.json','global-memory-*.log','global-fixture-metadata.json','global-fixtures/*.gz','baseline-global-evidence.py','baseline-ownership-reproduction.*','baseline-periodic-refresh.py','regression-after-fix.log','focused-final-0a4.log','lint-final-0a4.log','next-publication-metadata.log','next-publication-compressed-receipt.json','next-publication.json.gz','version-availability.json']:
 for p in r.glob(pattern):
  if p.is_file():files['ownership-controls/'+p.name]=p
for name in ['retention_memory_acceptance.py','retention_memory_probe.py','retention_reproduction.py','run-constrained.py']:files['methods/'+name]=r.parent/name
files['methods/global-owner-memory.py']=r/'global-owner-memory.py'
for name in ['run-local-canonical.py','prepare-methods-and-report.py','package-prior.py','make-recovery.py','verify-local-canonical.py','verify-host-canonical.py','finalize-plan.py','verify-certificate.py','verify-recovery-offline.py','verify-production.py']:files['methods/'+name]=b/name
for name in ['REPORT.md','OWNERSHIP.md','production-retained-memory-samples.json','global-owner-before-fix.log','global-owner-after-fix.log','SCOUT_HANDOFF.md','source.json','candidate-production.patch','measurement-source-association.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','resident-host-final-verified.json','prior-package.json','PRIOR_ATTEMPTS.md','checkpoint-publication.json','checkpoint-public-readback.json','publisher-tests-final49.log','publisher-lint-final49.log','publisher-compile-final49.log','invocation-final.json','local-container-enforcement.json','focused-final-49-writable.log','final-app-byte-equivalence.json','prior-0a4-public-readback.json','focused-and-resource-final49-verified.json','workflow-final-49-lint.log']:
 p=b/name;assert p.is_file(),name;files[name]=p
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,p in sorted(files.items()):
  if p.suffix in ('.json','.jsonl','.log','.md','.py','.patch','.txt'):assert not secret.search(p.read_bytes()),n
  z.write(p,n)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
receipt=dict(candidate=m['candidate'],tree=m['tree'],files=len(files),bytes=out.stat().st_size,sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest());(b/'recovery-package.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
