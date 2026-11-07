from pathlib import Path
import json,zipfile,tempfile,hashlib
from tools.release import publish as p
root=Path('/workspace/dtos-publisher-2238');b=Path('/workspace/2238-resident-refresh');plan=json.loads((root/'.github/release-plans/2238.json').read_text());p.verify_plan(plan)
archive=root/plan['recovery_file'];assert p.digest(archive)==plan['recovery_sha256'];p.verify_local_recovery(archive,plan);p.verify_prior_evidence(root/plan['prior_evidence_file'],plan)
with tempfile.TemporaryDirectory() as directory,zipfile.ZipFile(archive) as z:
 for label,verify,prefix,names in [('preflight',p.verify_preflight,'local-preflight/',('result.json','raw.log','SHA256SUMS')),('unused',p.verify_actuals_restoration,'local-restoration-unused/',('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('resident',p.verify_resident_refresh,'local-resident-refresh/',('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(directory)/(label+'.zip');p.make_zip(target,{name:z.read(prefix+name) for name in names});assert verify(target,plan)['passed']
 p.verify_handoff(z.read('SCOUT_HANDOFF.md'),plan)
for row in plan['artifacts']:
 a=next(x for n in ['canonical','product','lifecycle'] for x in json.loads((b/(n+'-artifact-metadata.json')).read_text())['artifacts'] if x['id']==row['id'])
 path=b/'hosted-originals'/(a['name']+'.zip');assert p.digest(path)==row['sha256'];p.verify_zip(path)
result=dict(candidate=plan['candidate'],tree=plan['tree'],mandatory_artifacts=len(plan['artifacts']),jobs=sum(len(r['jobs']) for r in plan['runs']),local_canonical_manifest=plan['local_canonical_entries'],host_canonical_manifest=plan['canonical_entries'],recovery_sha256=plan['recovery_sha256'],prior_sha256=plan['prior_evidence_sha256'],all_native_recovery_guards_passed=True)
(b/'recovery-offline-verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
