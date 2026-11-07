from pathlib import Path
import sys,json,hashlib,subprocess,datetime
sys.path.insert(0,'/workspace/dtos-publisher-2237')
from tools.release import publish
b=Path('/workspace/2237-cache-duplication');out=b/'reconciliation';plan=json.loads(Path('/workspace/dtos-publisher-2237/.github/release-plans/2237.json').read_text());records,_=publish.verify_runs(plan);assert len(records)==12
local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());assert local['tests']==host['tests']==4250 and local['all_local_gates_passed'] and host['all_gates_passed']
head=subprocess.check_output(['git','-C','/workspace/dtos','rev-parse','HEAD'],text=True).strip();tree=subprocess.check_output(['git','-C','/workspace/dtos','rev-parse','HEAD^{tree}'],text=True).strip();assert head=='1e1234fbcf7ca18f3862e5cdeac1451780e51b49' and tree==local['tree']==host['tree']==plan['tree']
assert not subprocess.check_output(['git','-C','/workspace/dtos','status','--porcelain'],text=True).strip()
zip_path=b/'hosted-originals/canonical-release-2g-python314.zip';assert hashlib.file_digest(zip_path.open('rb'),'sha256').hexdigest()==host['original_sha256']
result=dict(observed_at=datetime.datetime.now(datetime.UTC).isoformat(),baseline=head,tree=tree,application_source_unchanged=True,reused_source_candidate=plan['candidate'],full_regression_local=4250,full_regression_hosted=4250,local_gates=10,hosted_gates=10,local_manifest_entries=640,hosted_manifest_entries=644,hosted_jobs_freshly_reconciled=records,original_hosted_zip_sha256=host['original_sha256'],new_full_regression_rerun=False,new_release=False,explanation='No application code change is justified. Existing complete local/hosted release validation is reused only because its exact source tree equals the current deployed baseline; latest12job statuses are rechecked. These are previous full runs,not new executions.')
(out/'baseline-validation-reuse.json').write_text(json.dumps(result,indent=2)+'\n');print('Unchanged baseline tree verified; prior4250local+4250hosted,10gates each and12latest successful hosted jobs reconciled. No new full-run claim.')
