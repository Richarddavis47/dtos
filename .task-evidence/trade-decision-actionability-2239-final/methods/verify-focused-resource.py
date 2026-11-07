from pathlib import Path
import hashlib,json,tempfile,re
from tools.release import publish as p
b=Path('/workspace/2239-trade-actionability');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('.github/release-plans/2239.json').read_text())
assert plan['candidate']==source['candidate'] and plan['tree']==source['tree']
results={}
with tempfile.TemporaryDirectory() as folder:
 for label,verifier,names in [
 ('local-preflight',p.verify_preflight,('result.json','raw.log','SHA256SUMS')),
 ('local-restoration-unused',p.verify_actuals_restoration,('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),
 ('local-resident-refresh',p.verify_resident_refresh,('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(folder)/(label+'.zip');p.make_zip(target,{n:(b/label/n).read_bytes() for n in names});r=verifier(target,plan);assert r['passed'];results[label]={'passed':True,'head':r['head'],'tree':r['tree'],'zip_sha256':p.digest(target)}
console=(b/'focused-all-attempt5.log').read_bytes();assert re.search(rb'Ran 70 tests in [0-9.]+s\s+OK\s*$',console)
phone=json.loads((b/'phone/interaction.json').read_text());assert phone['source']==[source['candidate'],source['tree']] and len(phone['records'])==4
for r in phone['records']:assert r['keyboard_preview'] and r['keyboard_keep_original'] and r['action_unobstructed'] and not r['overflow'] and not r['errors'] and r['extra_searches']==0
out={'candidate':source['candidate'],'tree':source['tree'],'resource_controls':results,'focused_tests':70,'renderer_recovery_tests':35,'partial_renderer_control':1,'focused_scope':'70 initial precommit controls on superseded90. 35 renderer-recovery controls plus one extended partial-context control preceded bc4. Final source-bound phone/resource probes and canonical/hosted runs are separate; no precommit run is relabeled.','focused_console_sha256':hashlib.sha256(console).hexdigest(),'phone_interaction':phone,'all_native_guards_passed':True}
(b/'focused-resource-verified.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
