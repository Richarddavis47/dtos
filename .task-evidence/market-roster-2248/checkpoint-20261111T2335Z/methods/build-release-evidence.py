"""Seal original final-source evidence only after complete mandatory validation."""
from pathlib import Path,PurePosixPath
import json,hashlib,zipfile,re,importlib.util,datetime
B=Path('/workspace/2248-market-needs-final');P=Path('/workspace/dtos-publisher-2248')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(path):return sha(Path(path).read_bytes())
def add(files,name,path):
 n=PurePosixPath(name);assert not n.is_absolute() and '..' not in n.parts and '\\' not in name
 p=Path(path);assert p.is_file() and not p.is_symlink(),p;raw=p.read_bytes();assert name not in files
 if p.suffix in {'.py','.md','.json','.jsonl','.log','.txt','.patch','.js'}:assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',raw),name
 files[name]=raw
s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());resources=json.loads((B/'resource-preservation-verified.json').read_text());products=json.loads((B/'product-test-counts.json').read_text())
assert all(r['candidate']==s['candidate'] and r['tree']==s['tree'] for r in [local,host,native]);assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and resources['all_native_guards_passed'];assert local['tests']==host['tests']==s['expected_test_count']==4399 and products['total']==896 and len(native['originals'])==15
spec=importlib.util.spec_from_file_location('final_publisher_guard',P/'tools/release/publish.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
plan=dict(s,capital_tests=14,market_roster_tests=21,canonical_tests=4399,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],python_version='3.14.3');files={}
for folder in ['local-canonical','local-preflight','local-restoration-unused','local-resident-refresh','anchor-probe','partner-history','team-need','protections']:
 for p in sorted((B/folder).rglob('*')):
  if p.is_file() and (folder=='local-canonical' or '__pycache__' not in p.parts):add(files,folder+'/'+str(p.relative_to(B/folder)),p)
for p in (B/'history-browser').glob('*'):
 if p.is_file():add(files,'feature/'+p.name,p)
add(files,'feature/feature.json',B/'retained-history-feature.json')
required=['source.json','candidate.patch','FEATURE_METHOD.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','focused-code-fingerprint-proof.json','focused-ready.json','focused-exact-console.log','focused-exact/result.json','focused-exact-container.json','focused-invocation.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','local-container-stdout-original.log','canonical-invocation.json','start-final-local-original.log','local-canonical-integrity-original.log','host-canonical-verified.json','host-canonical-integrity-original.log','hosted-artifacts-verified.json','all-native-integrity-original.log','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','capture-extraction.json','product-test-counts.json','resource-preservation-verified.json','resource-invocation.json','resource-inputs.json','resource-native-guards.json','anchor-launch-original.log','anchor-probe.py','run-anchor-probe.py','retained-history-feature.json','retained-history-probe-invocation.json','retained-history-probe-original.log','production-baseline.json','live-access-boundary.json','publisher-current-final-controls.log','publisher-attachment-rename-controls.log','publisher-current-final-ruff.log']
for name in required:add(files,name,B/name)
for p in sorted((B/'hosted-decoded-originals').glob('*')):
 if p.is_file():add(files,'hosted-decoded-originals/'+p.name,p)
for p in sorted(B.glob('*.py')):add(files,'methods/'+p.name,p)
manifest=[dict(name=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(files.items())];files['recovery-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='Complete pre-publication source-bound validation; deployment receipt is separate',files=manifest),indent=2)+'\n').encode();files['SHA256SUMS']=''.join(sha(r)+'  '+n+'\n' for n,r in sorted(files.items())).encode()
p=B/'recovery-package.zip';assert not p.exists()
with zipfile.ZipFile(p,'x',zipfile.ZIP_LZMA) as z:
 for n,r in sorted(files.items()):z.writestr(n,r)
with zipfile.ZipFile(p) as z:assert z.testzip() is None
for function,prefix in [(guard.verify_local_recovery,None),(guard.verify_draft_capital,'local-canonical/offer-comparison/'),(guard.verify_market_roster,'local-canonical/market-needs/'),(guard.verify_activation_deferral,'local-canonical/activation/'),(guard.verify_front_office_workflow,'local-canonical/front-office-workflow/'),(guard.verify_partner_history_links,'partner-history/'),(guard.verify_team_need_handoff,'team-need/'),(guard.verify_recommended_protections,'protections/'),(guard.verify_completed_trade_browser,'feature/')]:
 if prefix is None:function(p,plan)
 else:function(p,plan,prefix=prefix)
guard.verify_completed_trade_cases(p,plan);assert p.stat().st_size<256*1024**2
record=dict(source=s,passed=True,bytes=p.stat().st_size,sha256=digest(p),canonical_members_preserved=local['local_manifest_entries'],members=len(files),generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Complete final-source pre-publication evidence, not owner live or deployment acceptance');(B/'recovery-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
