"""Seal current-source originals only after all real release gates are verified."""
from pathlib import Path,PurePosixPath
import datetime,hashlib,importlib.util,json,re,sys,zipfile
B=Path(__file__).resolve().parent;P=Path('/workspace/dtos-publisher-2250');files={}
def digest(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def add(name,path):
 path=Path(path);key=PurePosixPath(name);assert not key.is_absolute() and '..' not in key.parts and '\\' not in name
 assert name not in files and path.is_file() and not path.is_symlink(),name
 raw=path.read_bytes()
 if path.suffix in {'.py','.md','.json','.jsonl','.log','.txt','.patch','.js'}:
  assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})',raw),name
 files[name]=raw
s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());native=json.loads((B/'hosted-artifacts-verified.json').read_text());resource=json.loads((B/'resource-preservation-verified.json').read_text());product=json.loads((B/'product-test-counts.json').read_text());focus=json.loads((B/'focused-ready.json').read_text())
assert all(r['candidate']==s['candidate'] and r['tree']==s['tree'] for r in [local,host,native,focus])
assert local['all_local_gates_passed'] and host['all_gates_passed'] and native['passed'] and resource['all_native_guards_passed']
assert local['tests']==host['tests']==s['expected_test_count']==4435 and focus['passed'] and focus['tests']==103 and product['total']==932
assert len(native['originals'])==15
cap=json.loads((B/'local-capital-capture/result.json').read_text());ci=json.loads((B/'local-capital-capture-invocation.json').read_text())
assert cap['commit']==s['candidate'] and cap['tree']==s['tree'] and cap['passed'] and not cap['dirty'] and cap['tests']==2 and cap['failures']==cap['errors']==cap['skipped']==0
assert cap['memory_limit']==2147483648 and not any(int(cap['events'].get(k,0)) for k in ('oom','oom_kill')) and ci['exit_code']==0 and ci['container_absent_after'] and ci['original_local_manifest_sha256']==digest(B/'local-canonical/manifest.json')
sys.dont_write_bytecode=True;spec=importlib.util.spec_from_file_location('release_guard',P/'tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
plan=dict(s,canonical_tests=4435,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'],python_version='3.14.3',capital_tests=14,market_roster_tests=21,roster_source_scope_tests=20,franchise_progress_tests=16)
g.verify_handoff((B/'SCOUT_HANDOFF.md').read_bytes(),plan)
for folder in ['observer-recovery-2','observer-recovery','local-canonical','local-preflight','local-restoration-unused','local-resident-refresh','focused-exact','partner-history','team-need','protections','local-capital-capture']:
 assert (B/folder).is_dir(),folder
 for p in sorted((B/folder).rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:add(folder+'/'+str(p.relative_to(B/folder)),p)
# Keep the original exact-source focused capture bytes, with explicit alias provenance.
for p in sorted((B/'focused-exact/franchise-progress').glob('*')):
 if p.is_file():add('feature/'+p.name,p)
add('feature/feature.json',B/'retained-history-feature.json')
required=['source.json','candidate.patch','FEATURE_METHOD.md','EVIDENCE_BOUNDARIES.md','SCOUT_HANDOFF.md','PRIOR_ATTEMPTS.md','preservation.json','baseline.json','baseline-probe.json','baseline-probe-original.log','baseline-probe.py','baseline-probe-invocation.json','focused-ready.json','focused-exact-invocation.json','local-verified.json','local-container-cleanup.json','local-container-state-original.json','local-container-stdout-original.log','canonical-invocation.json','canonical-launch-original.log','canonical-runner-extraction.json','local-canonical-integrity-original.log','host-canonical-verified.json','host-canonical-integrity-original.log','hosted-artifacts-verified.json','all-native-integrity-original.log','hosted-final-records.json','validation-runs.json','artifact-download-queue.json','capture-extraction.json','product-test-counts.json','resource-preservation-verified.json','resource-invocation.json','resource-inputs.json','resource-native-guards.json','production-baseline-and-access.json','pre-commit-baseline.json','publisher-controls-original.log','publisher-controls-final-original.log','publisher-controls-2-original.log','publisher-controls-reconciled.json','publisher-ruff-original.log','publisher-ruff-2-original.log','publisher-controls-3-original.log','publisher-ruff-3-original.log','publisher-source-checkpoint.json','publisher-base-alignment.json','retained-history-feature.json','retained-history-probe-invocation.json','retained-history-probe-original.log','prior-package-final-complete.json','local-capital-capture-invocation.json','local-capital-capture-original.log','checkpoint-published.json','checkpoint-planning-correction.json','local-completion-observer.json']
required += ['source-transition-f40-to-b522.json','contextual-diagnostic-reconciled.json','contextual-diagnostic-sealed.json','input-relocation-reconciliation.json','executor-transport-recovery.json','reconciliation-checkpoint-published.json','cancelled-artifact-immutable-location.json','visual-review.json','fois-fixture-structural-review.json','resumption-baseline.json','observer-recovery.json','FOIS_FIXTURE_REVIEW.md','hosted-checkout-identities.json','hosted-resource-measurements.json','capture-extraction-scope-correction.json','observer-recovery-2.json','local-resource-measurements.json','pre-release-baseline.json']
for name in required:add(name,B/name)
for p in sorted((B/'hosted-decoded-originals').glob('*')):
 if p.is_file():add('hosted-decoded-originals/'+p.name,p)
for p in sorted(B.glob('*.py')):add('methods/'+p.name,p)
rows=[dict(name=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(files.items())]
files['recovery-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='Exact-source mandatory pre-publication originals; deployment/controller receipt is separately issued',files=rows),indent=2)+'\n').encode()
files['SHA256SUMS']=''.join(hashlib.sha256(raw).hexdigest()+'  '+n+'\n' for n,raw in sorted(files.items())).encode()
path=B/'recovery-package.zip';assert not path.exists()
with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,raw in sorted(files.items()):z.writestr(name,raw)
with zipfile.ZipFile(path) as z:
 assert z.testzip() is None
 for r in rows:
  raw=z.read(r['name']);assert len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
for fn,prefix in [(g.verify_local_recovery,None),(g.verify_draft_capital,'local-capital-capture/'),(g.verify_market_roster,'local-canonical/market-needs/'),(g.verify_roster_source_scope,'local-canonical/roster-source-scope/'),(g.verify_activation_deferral,'local-canonical/activation/'),(g.verify_front_office_workflow,'local-canonical/front-office-workflow/'),(g.verify_partner_history_links,'partner-history/'),(g.verify_team_need_handoff,'team-need/'),(g.verify_recommended_protections,'protections/'),(g.verify_franchise_progress_browser,'feature/')]:
 if prefix is None:fn(path,plan)
 else:fn(path,plan,prefix=prefix)
g.verify_franchise_progress_cases(path,plan);g.verify_franchise_progress_tests(path,plan,prefix='local-canonical/')
assert path.stat().st_size<256*1024**2
record=dict(source=s,passed=True,bytes=path.stat().st_size,sha256=digest(path),canonical_members_preserved=local['local_manifest_entries'],members=len(files),publisher_guard_sha256=digest(P/'tools/release/publish.py'),generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Complete actual pre-publication exact-source proof. No authenticated owner or deployment claim.')
(B/'recovery-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
