"""Verify the unchanged sealed package with the complete reviewed baseline-alias plan."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,sys,zipfile
B=Path(__file__).resolve().parent;P=Path('/workspace/dtos-publisher-2252')
def digest(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
s=json.loads((B/'source.json').read_text());local=json.loads((B/'local-verified.json').read_text());host=json.loads((B/'host-canonical-verified.json').read_text());assert local['all_local_gates_passed'] and host['all_gates_passed']
plan=json.loads((P/'.github/release-plans/2252.json').read_text());assert all(plan[k]==s[k] for k in ['candidate','tree','baseline','baseline_tree']);plan.update(canonical_tests=4501,canonical_entries=host['entries'],local_canonical_entries=local['local_manifest_entries'])
sys.dont_write_bytecode=True;spec=importlib.util.spec_from_file_location('existing_release_guard',P/'tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
out=B/'recovery-package.zip';before=digest(out)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None;meta=json.loads(z.read('recovery-manifest.json'));assert meta['candidate']==s['candidate'] and meta['tree']==s['tree'];files={r['name']:None for r in meta['files']}
 for r in meta['files']:
  with z.open(r['name']) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==r['sha256']
for fn,prefix in [(g.verify_local_recovery,None),(g.verify_customer_experience,None),(g.verify_draft_capital,'local-capital-capture/'),(g.verify_market_roster,'local-canonical/market-needs/'),(g.verify_roster_source_scope,'local-canonical/roster-source-scope/'),(g.verify_activation_deferral,'local-canonical/activation/'),(g.verify_front_office_workflow,'local-canonical/front-office-workflow/'),(g.verify_partner_history_links,'partner-history/'),(g.verify_team_need_handoff,'team-need/'),(g.verify_recommended_protections,'protections/'),(g.verify_franchise_progress_browser,'feature/'),(g.verify_completed_trade_browser,'feature/')]:
 if prefix is None:fn(out,plan)
 else:fn(out,plan,prefix=prefix)
g.verify_customer_experience_tests(out,plan,prefix='local-canonical/')
g.verify_franchise_progress_cases(out,plan);g.verify_completed_trade_cases(out,plan);g.verify_franchise_progress_tests(out,plan,prefix='local-canonical/');g.verify_acquisition_tests(out,plan,prefix='local-canonical/');g.verify_acquisition_recovery(out,plan);g.verify_normal_execution_tests(out,plan,prefix='local-canonical/')
assert out.stat().st_size<256*1024**2
assert digest(out)==before,'The sealed archive must remain unchanged'
record=dict(source=s,passed=True,bytes=out.stat().st_size,sha256=digest(out),canonical_members_preserved=local['local_manifest_entries'],members=len(files)+2,publisher_guard_sha256=digest(P/'tools/release/publish.py'),generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Complete actual pre-publication exact-source proof; deployment/controller receipts issued separately.')
(B/'recovery-verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
