"""Seal actual passing source-bound evidence; never replace missing results."""
from pathlib import Path
import json,hashlib,re,zipfile
b=Path('/workspace/2244-trade-comparison');controller=Path('/workspace/dtos-publisher-2244');source=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());focused=json.loads((b/'focused-resource-verified.json').read_text())
assert local['candidate']==host['candidate']==focused['candidate']==source['candidate'] and local['tree']==host['tree']==focused['tree']==source['tree']
assert local['tests']==host['tests']==4342 and local['all_local_gates_passed'] and host['all_gates_passed'] and focused['all_native_guards_passed'] and focused['offer_comparison']['passed']
assert json.loads((b/'product-test-counts.json').read_text())['total']==843 and json.loads((b/'public-welcome-test-counts.json').read_text())['total']==412
files={}
for folder,prefix in [('canonical','local-canonical'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('local-resident-refresh','local-resident-refresh')]:
 for p in (b/folder).rglob('*'):
  if p.is_file() and 'inputs' not in p.relative_to(b/folder).parts:files[prefix+'/'+str(p.relative_to(b/folder))]=p
for p in (b/'browser-final-source').iterdir():
 if p.is_file():files['partner-history/'+p.name]=p
for p in (b/'browser-final-source/team-need').iterdir():
 if p.is_file():files['team-need/'+p.name]=p
for p in (b/'focused-final2').iterdir():
 if p.is_file() and (p.suffix=='.json' or p.name in ('phone-320.png','phone-375.png','phone-390.png','phone-1280.png')):files['offer-comparison/'+p.name]=p
files['feature/browser.json']=b/'history-browser-final-source/browser.json';files['feature/feature.json']=b/'retained-history-feature.json'
for p in (b/'history-browser-final-source').glob('*.png'):files['feature/'+p.name]=p
required=['REPORT.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','source.json','baseline.json','baseline-reproduction.json','candidate.patch','preservation-review.json','resource-qualification.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','product-test-counts.json','public-welcome-test-counts.json','focused-resource-verified.json','focused-final2-original.log','preserved-native-feature-controls-original.log','retained-history-probe-original.log','publisher-final-tests-original.log','publisher-final-lint-original.log','publisher-final-compile-original.log','publisher-workflow-review.json','prior-package.json','invocation-final.json','live-access-limitation.json','browser-capability-original.json','local-container-cleanup.json','immutable-static-assets-after.json','local-container-enforcement.json','local-hosted-manifest-reconciliation.json','hosted-job-log-receipts.json','hosted-artifacts-verified.json','focused-commands.json','source-remote-recheck.json','canonical-harness-provenance.json','canonical-outer-transport-limitation.json','local-canonical-original.log','publisher-scoped-checks.json','local-canonical-integrity-original.log','host-canonical-integrity-original.log','hosted-artifacts-integrity-original.log','noncanonical-artifact-integrity-attempt2-original.log']
for name in required:
 p=b/name;assert p.is_file(),name;files[name]=p
for name in ['run-constrained.py','run-local-canonical.py','run-local-resource.py','verify-local-canonical.py','verify-host-canonical.py','verify-focused-resource.py','verify-native-originals.py','verify-noncanonical-originals.py','retained-history-probe.py','build-final-artifact-queue.py','make-recovery.py','package-prior.py','readable-root-logs.py','readable-host-logs.py','dispatch-guarded.py','verify-certificate.py','create-draft.py','finalize-plan.py','merge-approved.py','verify-production.py','verify-final-publication.py']:
 assert (b/name).is_file(),name;files['methods/'+name]=b/name
path=controller/'.github/release-plans/2244-recovery.zip';token=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in sorted(files.items()):
  raw=p.read_bytes();assert not token.search(raw),name;z.writestr(name,raw)
with zipfile.ZipFile(path) as z:assert z.testzip() is None
assert path.stat().st_size<100*1024**2,'Keep original mandatory proofs; do not truncate to fit'
r=dict(candidate=source['candidate'],tree=source['tree'],files=len(files),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),readability='Full original local regression console and canonical manifest are included. All original13hosted consoles, readable<=60k parts and other comparison photos remain in separately published checksum-verified task evidence; all13comparisonJSON and required4phonePNG are included here, and all captured comparison photos also remain in the original hostedTradeZIP. No mandatory guard or original evidence is omitted.')
(b/'recovery-package.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
