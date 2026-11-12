"""Seal source-bound originals only after every mandatory final gate passes."""
from pathlib import Path,PurePosixPath
import json,hashlib,zipfile,re,importlib.util,datetime,sys
B=Path('/workspace/2249-sleeper-relevance');P=Path('/workspace/dtos-publisher-2249');files={}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(p):return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def add(name,p):
 name=str(name);n=PurePosixPath(name);p=Path(p);assert not n.is_absolute() and '..' not in n.parts and '\\' not in name;assert p.is_file() and not p.is_symlink() and name not in files;raw=p.read_bytes()
 if p.suffix in ['.py','.md','.json','.jsonl','.log','.txt','.patch','.js']:assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})',raw),name
 files[name]=raw
s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());resource=json.loads((B/'resource-preservation-verified.json').read_text());product=json.loads((B/'product-test-counts.json').read_text());focus=json.loads((B/'focused-ready.json').read_text())
assert all(x['candidate']==s['candidate'] and x['tree']==s['tree'] for x in [local,host,native,focus]);assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and resource['all_native_guards_passed'];assert local['tests']==host['tests']==s['expected_test_count']==4419 and product['total']==916 and focus['tests']==123 and focus['passed'];assert len(native['originals'])==15
cap=json.loads((B/'local-capital-capture/result.json').read_text());ci=json.loads((B/'local-capital-capture-invocation.json').read_text());assert cap['commit']==s['candidate'] and cap['tree']==s['tree'] and not cap['dirty'] and cap['passed'] and cap['tests']==2 and cap['failures']==cap['errors']==cap['skipped']==0 and cap['memory_limit']==2147483648 and not any(int(cap['events'].get(k,0)) for k in ('oom','oom_kill')) and ci['exit_code']==0 and ci['container_absent_after'] and ci['original_local_manifest_sha256']==digest(B/'local-canonical/manifest.json')
# Bind source before allocating or publishing the archive.
sys.dont_write_bytecode=True;spec=importlib.util.spec_from_file_location('source_bound_publisher_guard',P/'tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
plan=dict(s,capital_tests=14,market_roster_tests=21,roster_source_scope_tests=20,canonical_tests=4419,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],python_version='3.14.3')
g.verify_handoff((B/'SCOUT_HANDOFF.md').read_bytes(),plan)
for folder in ['local-canonical','local-preflight','local-restoration-unused','local-resident-refresh','focused-exact','partner-history','team-need','protections','market-browser','roster-browser','local-capital-capture']:
 assert (B/folder).is_dir(),folder
 for p in sorted((B/folder).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:add(folder+'/'+str(p.relative_to(B/folder)),p)
for p in sorted((B/'history-browser').glob('*')):
 if p.is_file():add('feature/'+p.name,p)
add('feature/feature.json',B/'retained-history-feature.json')
required=['source.json','source-transition.json','candidate.patch','FEATURE_METHOD.md','EVIDENCE_BOUNDARIES.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','baseline-probe.json','baseline-probe-original.log','baseline-probe.py','focused-ready.json','focused-final-invocation.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','local-container-stdout-original.log','canonical-invocation.json','canonical-runner-extraction.json','canonical-harness-schema-adaptation.json','local-canonical-integrity-original.log','host-canonical-verified.json','host-canonical-integrity-original.log','hosted-artifacts-verified.json','all-native-integrity-original.log','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','capture-extraction.json','product-test-counts.json','resource-preservation-verified.json','resource-invocation.json','resource-inputs.json','resource-native-guards.json','production-baseline.json','live-access-boundary.json','checkpoint-published-verified.json','checkpoint-hosted-published-verified.json','publisher-source-clean-controls-original.log','publisher-source-clean-ruff-original.log','retained-history-feature.json','retained-history-probe-invocation.json','retained-history-probe-original.log','prior-package-complete.json','prior-package-scope-correction.json','prior-package-scope-correction-original.log','source-cleanup-verified.json','handoff-source-binding-correction.json','SCOUT_HANDOFF_UNBOUND_ORIGINAL.md','recovery-before-handoff-binding-original.json','recovery-build-before-handoff-binding-original.log','resumed-original-reconciliation.json','resumed-original-reconciliation-original.log','eligibility-boundary-review.json','production-baseline-resumed.json','recovery-packaging-interruption.json','recovery-build-interrupted-original.log','local-capital-capture-invocation.json','local-capital-capture-original.log','recovery-packaging-failure.json','recovery-build-first-incomplete-original.log','recovery-manifest-first-incomplete-original.json','publisher-local-capital-prefix-correction.json','recovery-component-precheck.json','recovery-component-precheck-original.log','prior-manifest-unfinalized-scope-original.json','prior-package-unfinalized-scope-original.json','final-serial-preflight-original.log']
for name in required:add(name,B/name)
for p in sorted((B/'hosted-decoded-originals').glob('*')):
 if p.is_file():add('hosted-decoded-originals/'+p.name,p)
for p in sorted(B.glob('*.py')):add('methods/'+p.name,p)
for p in sorted((B/'prior-publisher-attempts').rglob('*')):
 if p.is_file():add('prior-publisher-attempts/'+str(p.relative_to(B/'prior-publisher-attempts')),p)
# Preserve the remaining complete cancelled native artifact separately from
# current proofs and the bounded prior Git blob. Never relabel its source.
old=B/'prior-hosted-c821/native-originals/trade-resource-cancelled-original.zip';assert digest(old)=='046a010832bccbd435b4e28a197cd87cd019bb604a9288a2827913eb7909ae0a';add('prior-originals/source-c821/trade-resource-cancelled-original.zip',old)
files['prior-originals/README.md']=b'Original cancelled c821 Trade artifact, SHA256/API/CRC verified. Historical source and incomplete outcomes only; not final36fc evidence. Otherfailed/cancelledoriginals and readablelogs are in prior-package.zip.\n'
rows=[dict(name=n,bytes=len(raw),sha256=sha(raw)) for n,raw in sorted(files.items())];files['recovery-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='Complete pre-publication exact-source proof; deployment receipt is separate',files=rows),indent=2)+'\n').encode();files['SHA256SUMS']=''.join(sha(raw)+'  '+n+'\n' for n,raw in sorted(files.items())).encode();path=B/'recovery-package.zip';assert not path.exists()
with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for n,raw in sorted(files.items()):z.writestr(n,raw)
with zipfile.ZipFile(path) as z:
 assert z.testzip() is None
 for row in rows:raw=z.read(row['name']);assert len(raw)==row['bytes'] and sha(raw)==row['sha256']
for fn,prefix in [(g.verify_local_recovery,None),(g.verify_draft_capital,'local-capital-capture/'),(g.verify_market_roster,'local-canonical/market-needs/'),(g.verify_roster_source_scope,'local-canonical/roster-source-scope/'),(g.verify_activation_deferral,'local-canonical/activation/'),(g.verify_front_office_workflow,'local-canonical/front-office-workflow/'),(g.verify_partner_history_links,'partner-history/'),(g.verify_team_need_handoff,'team-need/'),(g.verify_recommended_protections,'protections/'),(g.verify_completed_trade_browser,'feature/')]:
 if prefix is None:fn(path,plan)
 else:fn(path,plan,prefix=prefix)
g.verify_completed_trade_cases(path,plan);assert path.stat().st_size<256*1024**2
record=dict(source=s,passed=True,bytes=path.stat().st_size,sha256=digest(path),canonical_members_preserved=local['local_manifest_entries'],members=len(files),publisher_guard_sha256=digest(P/'tools/release/publish.py'),generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Complete mandatory pre-publication exact-source originals. No ownerlive or deployment claim.');(B/'recovery-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
