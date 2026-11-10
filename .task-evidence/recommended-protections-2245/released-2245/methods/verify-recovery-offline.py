"""Apply the same frozen publisher guards to complete sealed local evidence."""
from pathlib import Path
import json,sys,tempfile,zipfile,hashlib
sys.path.insert(0,'/workspace/dtos-publisher-2245')
from tools.release import publish as p
b=Path('/workspace/2245-recommended-protections');controller=Path('/workspace/dtos-publisher-2245');plan=json.loads((controller/'.github/release-plans/2245.json').read_text());s=json.loads((b/'source.json').read_text());p.verify_plan(plan);assert plan['candidate']==s['candidate'] and plan['tree']==s['tree'];archive=controller/plan['recovery_file'];assert p.digest(archive)==plan['recovery_sha256'];out={}
out['local_canonical']=p.verify_local_recovery(archive,plan)
for name,verify,prefix in [('partner_history',p.verify_partner_history_links,'partner-history/'),('team_need',p.verify_team_need_handoff,'team-need/'),('offer_comparison',p.verify_offer_comparison,'offer-comparison/'),('protections',p.verify_recommended_protections,'protections/'),('history',p.verify_completed_trade_browser,'feature/')]:
 out[name]=verify(archive,plan,prefix=prefix);assert out[name]['passed']
out['history_cases']=p.verify_completed_trade_cases(archive,plan);assert out['history_cases']['passed']
with tempfile.TemporaryDirectory() as temp,zipfile.ZipFile(archive) as z:
 p.verify_handoff(z.read('SCOUT_HANDOFF.md'),plan)
 for name,verify,names in [('local-preflight',p.verify_preflight,['result.json','raw.log','SHA256SUMS']),('local-restoration-unused',p.verify_actuals_restoration,['evidence/result.json','raw.log','prior-study.zip','SHA256SUMS']),('local-resident-refresh',p.verify_resident_refresh,['evidence/result.json','raw.log','SHA256SUMS'])]:
  f=Path(temp)/(name+'.zip');p.make_zip(f,{n:z.read(name+'/'+n) for n in names});out[name]=verify(f,plan);assert out[name]['passed']
p.verify_prior_evidence(controller/plan['prior_evidence_file'],plan)
r=dict(candidate=s['candidate'],tree=s['tree'],all_native_recovery_guards_passed=True,recovery_sha256=plan['recovery_sha256'],prior_sha256=plan['prior_evidence_sha256'],local_canonical_tests=4346,guards={name:{k:v for k,v in row.items() if k in ['passed','head','tree','commit','cgroup_limit','matched_cases']} for name,row in out.items()},method='Unchanged publisher native guards applied offline to the sealed original source-pinned recovery/prior ZIPs; not a substitute for authorized Actions preparation or production verification.');(b/'recovery-offline-verified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
