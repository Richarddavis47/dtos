"""Seal complete source-pinned proof after, never before, every required gate."""
from pathlib import Path
import hashlib,json,zipfile,re
b=Path('/workspace/2245-recommended-protections');controller=Path('/workspace/dtos-publisher-2245');source=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());focused=json.loads((b/'focused-resource-verified.json').read_text())
assert local['candidate']==host['candidate']==focused['candidate']==source['candidate'] and local['tree']==host['tree']==focused['tree']==source['tree']
assert local['tests']==host['tests']==4346 and local['all_local_gates_passed'] and host['all_gates_passed'] and focused['all_native_guards_passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==847
files={}
for folder,prefix in [('local-canonical','local-canonical'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('local-resident-refresh','local-resident-refresh'),('partner-history','partner-history'),('team-need','team-need'),('focused-final','protections'),('win-now','win-now')]:
 for p in (b/folder).rglob('*'):
  if p.is_file():files[prefix+'/'+str(p.relative_to(b/folder))]=p
for p in (b/'offer-comparison').iterdir():
 if p.is_file() and (p.suffix=='.json' or p.name in ['phone-320.png','phone-375.png','phone-390.png','phone-1280.png']):files['offer-comparison/'+p.name]=p
files['feature/browser.json']=b/'history-browser/browser.json';files['feature/feature.json']=b/'retained-history-feature.json'
for p in (b/'history-browser').glob('*.png'):files['feature/'+p.name]=p
required=['REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','source.json','baseline.json','baseline-reproduction.json','baseline-reproduction-original.log','candidate.patch','preservation-review.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','public-welcome-test-counts.json','focused-resource-verified.json','focused-final-original.log','preserved-controls-original.log','win-now-control-original.log','retained-history-probe-original.log','publisher-tests-release-original.log','publisher-lint-release-original.log','publisher-compile-release-original.log','publisher-workflow-review.json','prior-package.json','canonical-invocation.json','live-access-limitation-release.json','local-container-cleanup.json','local-container-enforcement.json','hosted-artifacts-verified.json','canonical-runtime-freeze.txt','local-container-stdout-original.log','local-budget-recovery-method.json','environment-reconnection.json','prior-local-public-readback.json','prior-package-size-reconciliation.json','recovery-compression-reconciliation.json','recovery-package-deflate-attempt-original.log','focused-resource-integrity-original.log','local-canonical-integrity-original.log','host-canonical-integrity-original.log','hosted-artifacts-integrity-original.log','initial-public-readback.json','prior-public-readback.json','phone-failure-public-readback.json']
for name in required:
 p=b/name;assert p.is_file(),name;files[name]=p
for p in b.glob('*.py'):files['methods/'+p.name]=p
for p in (b/'runtime-build').iterdir():
 if p.is_file():files['runtime-build/'+p.name]=p
path=controller/'.github/release-plans/2245-recovery.zip';token=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(path,'w',zipfile.ZIP_LZMA) as z:
 for name,p in sorted(files.items()):
  raw=p.read_bytes();assert not token.search(raw),name;z.writestr(name,raw)
with zipfile.ZipFile(path) as z:assert z.testzip() is None
assert path.stat().st_size<100*1024**2,'Keep every mandatory original/guard; resolve transport without truncating evidence'
r=dict(candidate=source['candidate'],tree=source['tree'],files=len(files),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),compression='standard ZIP method14/LZMA; Python zipfile native reader, every original member retained byte-for-byte',readability='Full original local canonical console, all canonical manifest bytes, current native resource controls, original search captures and source patch. Other comparison photos and all hosted originals remain in the fifteen separately attached native archives and readable public handoff.')
(b/'recovery-package.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
