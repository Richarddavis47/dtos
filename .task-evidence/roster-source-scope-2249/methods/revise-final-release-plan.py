"""Revise only document-bound evidence after the preserved failed preparation."""
from pathlib import Path
import json,hashlib,zipfile,importlib.util,datetime
B=Path(__file__).resolve().parent;P=Path('/workspace/dtos-publisher-2249');old=json.loads((P/'.github/release-plans/2249.json').read_text());s=json.loads((B/'source.json').read_text());r=json.loads((B/'recovery-verified.json').read_text());assert r['passed'] and r['source']['candidate']==s['candidate'] and r['source']['tree']==s['tree'];assert old['candidate']==s['candidate'] and old['tree']==s['tree'] and old['draft_id']==442627098 and old['recovery_sha256']=='a1172316196d4c062216b2d3da6a01b2a6f8d03772c7d73dcefbacacc4a628b5';spec=importlib.util.spec_from_file_location('unchanged_plan_guard',P/'tools/release/publish.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
with zipfile.ZipFile(B/'recovery-package.zip') as z:g.verify_handoff(z.read('SCOUT_HANDOFF.md'),old)
parts=[]
with (B/'recovery-package.zip').open('rb') as f:
 i=0
 while raw:=f.read(64*1024**2):
  i+=1;assert i<=4;name=f'.github/release-plans/2249-recovery-{i:03}.part';(P/name).write_bytes(raw);parts.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
assert len(parts)==len(old['recovery_parts'])==3
new=dict(old,recovery_sha256=r['sha256'],recovery_parts=parts,prior_runs=old['prior_runs']+[43177742523]);g.verify_plan(new)
for key in old:
 if key not in {'recovery_sha256','recovery_parts','prior_runs'}:assert new[key]==old[key]
raw=(json.dumps(new,indent=2)+'\n').encode();(P/'.github/release-plans/2249.json').write_bytes(raw);(B/'final-release-plan.json').write_bytes(raw);(B/'recovery-final-verified.json').write_bytes((B/'recovery-verified.json').read_bytes());record=dict(observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_publisher='d41c134fa5cc09070fb9756938fefd941720d86d',failed_prepare_run=43177742523,old_archive_sha256=old['recovery_sha256'],final_archive_sha256=r['sha256'],final_archive_bytes=r['bytes'],changed_plan_fields=['recovery_sha256','recovery_parts','prior_runs'],all_source_validation_and_native_artifact_identities_unchanged=True,source_binding_guard_passed=True,publisher_python_unchanged=True,scope='Only corrected source-bound handoff and separately preserved failed-run evidence. No code, reserve, qualification or app-suite change.');(B/'publisher-plan-revision.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
