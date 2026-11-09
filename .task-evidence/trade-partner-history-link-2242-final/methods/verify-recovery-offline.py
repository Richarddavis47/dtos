from pathlib import Path
import json,zipfile,tempfile
from tools.release import publish as p
root=Path('/workspace/dtos-publisher-2242');b=Path('/workspace/2242-trade-partner-history-link');plan=json.loads((root/'.github/release-plans/2242.json').read_text());p.verify_plan(plan);archive=root/plan['recovery_file'];assert p.digest(archive)==plan['recovery_sha256'];p.verify_local_recovery(archive,plan);p.verify_prior_evidence(root/plan['prior_evidence_file'],plan);p.verify_completed_trade_browser(archive,plan,prefix="feature/");p.verify_completed_trade_cases(archive,plan);p.verify_partner_history_links(archive,plan,prefix="partner-history/")
with tempfile.TemporaryDirectory() as directory,zipfile.ZipFile(archive) as z:
 for label,verify,prefix,names in [('preflight',p.verify_preflight,'local-preflight/',('result.json','raw.log','SHA256SUMS')),('unused',p.verify_actuals_restoration,'local-restoration-unused/',('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('resident',p.verify_resident_refresh,'local-resident-refresh/',('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(directory)/(label+'.zip');p.make_zip(target,{name:z.read(prefix+name) for name in names});assert verify(target,plan)['passed']
 p.verify_handoff(z.read('SCOUT_HANDOFF.md'),plan)
for row in plan['artifacts']:
 path=b/'hosted-originals'/(row['name']+'.zip');assert p.digest(path)==row['sha256'];p.verify_zip(path)
 if row['file']=='canonical-original.zip':p.verify_canonical(path,plan)
r=dict(candidate=plan['candidate'],tree=plan['tree'],mandatory_artifacts=len(plan['artifacts']),jobs=sum(len(x['jobs']) for x in plan['runs']),local_manifest=plan['local_canonical_entries'],host_manifest=plan['canonical_entries'],recovery_sha256=plan['recovery_sha256'],prior_sha256=plan['prior_evidence_sha256'],all_native_recovery_guards_passed=True,completed_trade_feature_and_phone_verified=True,partner_history_feature_and_return_verified=True,descriptive_only=True)
(b/'recovery-offline-verified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
