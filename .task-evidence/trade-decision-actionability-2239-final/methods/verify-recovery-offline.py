from pathlib import Path
import json,zipfile,tempfile,hashlib
from tools.release import publish as p
root=Path('/workspace/dtos-publisher-2239');b=Path('/workspace/2239-trade-actionability');plan=json.loads((root/'.github/release-plans/2239.json').read_text());p.verify_plan(plan);archive=root/plan['recovery_file'];assert p.digest(archive)==plan['recovery_sha256'];p.verify_local_recovery(archive,plan);p.verify_prior_evidence(root/plan['prior_evidence_file'],plan)
with tempfile.TemporaryDirectory() as directory,zipfile.ZipFile(archive) as z:
 for label,verify,prefix,names in [('preflight',p.verify_preflight,'local-preflight/',('result.json','raw.log','SHA256SUMS')),('unused',p.verify_actuals_restoration,'local-restoration-unused/',('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('resident',p.verify_resident_refresh,'local-resident-refresh/',('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(directory)/(label+'.zip');p.make_zip(target,{name:z.read(prefix+name) for name in names});assert verify(target,plan)['passed']
 p.verify_handoff(z.read('SCOUT_HANDOFF.md'),plan)
 cases=json.loads(z.read('cases/matched-cases.json'));assert cases['source']==[plan['candidate'],plan['tree']]
 for strategy in ('WIN NOW','RETOOL','REBUILD'):
  assert cases[strategy]['qualified']>0
  for row in cases[strategy]['pairs']:assert all(row['exact_numeric_and_verdict_agreement'].values())
 phone=json.loads(z.read('phone/interaction.json'));assert phone['source']==[plan['candidate'],plan['tree']] and len(phone['records'])==4 and all(not r['errors'] and not r['overflow'] and r['extra_searches']==0 for r in phone['records'])
 zero=json.loads(z.read('zero-result/response.json'));assert zero['source']==[plan['candidate'],plan['tree']] and zero['status']==200 and not any(r['evaluation']['generated_trade_eligible'] for r in zero['response']['results']) and zero['response']['zero_result_guidance']['recommendation'] is False
for row in plan['artifacts']:
 path=b/'hosted-originals'/(row['name']+'.zip');assert p.digest(path)==row['sha256'];p.verify_zip(path)
 if row['file']=='canonical-original.zip':p.verify_canonical(path,plan)
result=dict(candidate=plan['candidate'],tree=plan['tree'],mandatory_artifacts=len(plan['artifacts']),jobs=sum(len(r['jobs']) for r in plan['runs']),local_canonical_manifest=plan['local_canonical_entries'],host_canonical_manifest=plan['canonical_entries'],recovery_sha256=plan['recovery_sha256'],prior_sha256=plan['prior_evidence_sha256'],all_native_recovery_guards_passed=True,matched_trade_and_zero_phone_evidence=True)
(b/'recovery-offline-verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
