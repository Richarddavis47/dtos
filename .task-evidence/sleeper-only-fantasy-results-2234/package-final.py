"""Seal exact-source original evidence only after mandatory acceptance."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2234-release');m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['tests']==host['tests']==4216
assert local['all_local_gates_passed'] and host['all_gates_passed']
focus=(b/'focused-exact.log').read_bytes();assert re.search(rb'Ran 171 tests in [0-9.]+s\s+OK\s*$',focus)
pre=json.loads((b/'local-preflight/result.json').read_text());assert pre['passed'] and pre['complete'] and pre['head']==m['candidate'] and pre['tree']==m['tree']
assert (b/'local-preflight/raw.log').read_bytes()==(b/'local-preflight-console.log').read_bytes()
for n in ['native-sleeper-replay.json','before-after.json']:
 r=json.loads((b/n).read_text());assert r['candidate']==m['candidate'] and r['tree']==m['tree']
assert json.loads((b/'resource-verified.json').read_text())['all_native_guards_passed']
files={}
for folder,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),('browser-final','current-production-coverage'),('readable-console','readable-console'),('prior-attempts','supplementary-attempts')]:
 for p in sorted((b/folder).rglob('*')):
  if p.is_file():files[prefix+'/'+str(p.relative_to(b/folder))]=p
required=['post-validation-source-clean.json','version-availability.json','timestamp-token-control.json','coverage-map.json','render-service-baseline.json','REPORT.md','SCOUT_HANDOFF.md','source.json','candidate-production.patch','source-integrity.json','local-verified.json','host-canonical-verified.json','focused-exact.log','timestamp-token-focused.log','local-preflight-console.log','commands.md','run-clean.py','run-constrained.py','finish-local.py','sequential-final-scopes.json','local-container-exit.log','invocation.json','local-console.log','baseline.json','package-final.py','package-prior.py','package-prior-report.json','harness-preservation.json','clean-checkout.json','publisher-focused-final.log','publisher-lint-final.log','publisher-compilation.log','before-after.json','before-after.py','before-after.log','resource-verified.json','lifecycle-verified.json','product-artifact-integrity.log','lifecycle-artifact-integrity.log','verify-lifecycle.py','verify-product-artifacts.py','verify-local-canonical.py','verify-host-canonical.py','native-sleeper-selected-score.json','native-sleeper-read.log','read-native-sleeper.py','native-sleeper-replay.py','native-sleeper-replay.json','native-sleeper-replay.log','native-sleeper-component.html','browser-access.json','product-test-counts.json','prior-hosted-status-final.json','artifact-download-receipts.jsonl','scratch-reclamation.json','ruff-final.log','local-canonical-integrity.log']
for n in required:assert (b/n).is_file(),n;files[n]=b/n
out=Path('/workspace/dtos-publisher-2234/.github/release-plans/2234-recovery.zip');assert not out.exists(),'Earlier archive must remain preserved'
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,p in sorted(files.items()):
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(p.read_bytes()),n
  z.write(p,n)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
assert out.stat().st_size<100*1024**2
print(json.dumps({'candidate':m['candidate'],'tree':m['tree'],'payloads':len(files),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
