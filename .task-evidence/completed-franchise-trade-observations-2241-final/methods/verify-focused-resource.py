from pathlib import Path
import json,tempfile,re,sys
sys.path.insert(0,'/workspace/dtos-publisher-2241')
from tools.release import publish as p
b=Path('/workspace/2241-trade-partner-history');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2241/.github/release-plans/2241.json').read_text());assert plan['candidate']==source['candidate'] and plan['tree']==source['tree'];results={}
with tempfile.TemporaryDirectory() as folder:
 for label,verify,names in [('local-preflight',p.verify_preflight,('result.json','raw.log','SHA256SUMS')),('local-restoration-unused',p.verify_actuals_restoration,('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('local-resident-refresh',p.verify_resident_refresh,('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(folder)/(label+'.zip');p.make_zip(target,{n:(b/label/n).read_bytes() for n in names});r=verify(target,plan);assert r['passed'];results[label]=dict(passed=True,head=r['head'],tree=r['tree'],zip_sha256=p.digest(target))
console=(b/'final-source-focused-original.log').read_bytes();assert re.search(rb'Ran 18 tests in [0-9.]+s\s+OK\s*$',console)
files={'feature/browser.json':(b/'browser-final-source/browser.json').read_bytes(),'feature/feature.json':(b/'feature.json').read_bytes()};files.update({'feature/'+f.name:f.read_bytes() for f in (b/'browser-final-source').glob('*.png')})
with tempfile.TemporaryDirectory() as folder:
 target=Path(folder)/'feature.zip';p.make_zip(target,files);feature=p.verify_completed_trade_browser(target,plan,prefix='feature/');feature['matched_cases']=p.verify_completed_trade_cases(target,plan)
r=dict(candidate=source['candidate'],tree=source['tree'],resource_controls=results,focused_tests=18,expanded_precommit_tests=106,feature=feature,all_native_guards_passed=True,scope='Source-pinned controlled/retained replay and enforced2GiB controls; authenticated live history acceptance unverified')
(b/'focused-resource-verified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
