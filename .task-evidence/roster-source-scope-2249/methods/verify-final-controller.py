from pathlib import Path
import importlib.util,json,hashlib,tempfile,subprocess
import yaml
B=Path('/workspace/2249-sleeper-relevance');P=Path('/workspace/dtos-publisher-2249')
spec=importlib.util.spec_from_file_location('publisher_final',P/'tools/release/publish.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
plan=json.loads((P/'.github/release-plans/2249.json').read_text());m.verify_plan(plan)
local=json.loads((B/'local-verified.json').read_text());assert local['all_local_gates_passed'] and local['local_manifest_entries']==plan['local_canonical_entries']
m.verify_prior_evidence(P/plan['prior_evidence_file'],plan)
with tempfile.TemporaryDirectory(prefix='capital-controller-proof-',dir=B) as directory:
    archive=m.materialize_recovery(plan,Path(directory),P)
    assert m.digest(archive)==m.digest(B/'recovery-package.zip')==plan['recovery_sha256']
raw=subprocess.run(['git','show',plan['candidate']+':.github/workflows/canonical-release-recovery.yml'],cwd=P,check=True,capture_output=True,text=True).stdout
assert yaml.safe_load(raw)['jobs']['canonical-release']['steps']==yaml.safe_load((P/'.github/workflows/canonical-release-recovery.yml').read_text())['jobs']['canonical-release']['steps']
workflow=yaml.safe_load((P/'.github/workflows/canonical-release-recovery.yml').read_text());job=workflow['jobs']['guarded-release-publisher'];assert job['permissions']=={'contents':'write','checks':'read','pull-requests':'read','actions':'read'};assert job['concurrency']=={'group':'dtos-guarded-release-2249','cancel-in-progress':False};assert job['timeout-minutes']==25 and "github.event_name == 'workflow_dispatch'" in job['if'];assert any('--plan .github/release-plans/2249.json' in row.get('run','') for row in job['steps'])
changed=subprocess.run(['git','diff','--cached','--name-only',plan['baseline']],cwd=P,check=True,capture_output=True,text=True).stdout.splitlines();assert changed and set(changed)<=m.ALLOWED_PATHS
record=dict(candidate=plan['candidate'],tree=plan['tree'],all_local_and_hosted_application_gates_passed=True,plan_valid=True,exact_recovery_parts_and_full_bytes_verified=True,prior_bytes_verified=True,application_canonical_steps_unchanged=True,allowlisted_staged_paths=changed,plan_sha256=hashlib.sha256((P/'.github/release-plans/2249.json').read_bytes()).hexdigest(),scope='Local final controller integrity; Actions context, upload/readback and publication are separately required.')
(B/'publisher-final-integrity.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
