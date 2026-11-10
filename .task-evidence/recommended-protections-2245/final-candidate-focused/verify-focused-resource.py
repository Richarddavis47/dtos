from pathlib import Path
import json,tempfile,sys,re
sys.path.insert(0,'/workspace/dtos-publisher-2245')
from tools.release import publish as p
b=Path('/workspace/2245-recommended-protections');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2245/.github/release-plans/2245.json').read_text());out={}
assert source['candidate']==plan['candidate'] and source['tree']==plan['tree']
for name in ['focused-final-original.log','preserved-controls-original.log']:
 assert re.search(rb'Ran 15 tests in [0-9.]+s\s+OK\s*$',(b/name).read_bytes()),name
with tempfile.TemporaryDirectory() as folder:
 for name,verify,names in [('local-preflight',p.verify_preflight,['result.json','raw.log','SHA256SUMS']),('local-restoration-unused',p.verify_actuals_restoration,['evidence/result.json','raw.log','prior-study.zip','SHA256SUMS']),('local-resident-refresh',p.verify_resident_refresh,['evidence/result.json','raw.log','SHA256SUMS'])]:
  z=Path(folder)/(name+'.zip');p.make_zip(z,{n:(b/name/n).read_bytes() for n in names});out[name]=verify(z,plan);assert out[name]['passed']
 files={}
 for name,prefix in [('partner-history','partner-history/'),('team-need','team-need/'),('offer-comparison','offer-comparison/'),('focused-final','protections/')]:
  for f in (b/name).iterdir():
   if f.is_file():files[prefix+f.name]=f.read_bytes()
 files['feature/browser.json']=(b/'history-browser/browser.json').read_bytes();files['feature/feature.json']=(b/'retained-history-feature.json').read_bytes()
 for f in (b/'history-browser').glob('*.png'):files['feature/'+f.name]=f.read_bytes()
 z=Path(folder)/'browser.zip';p.make_zip(z,files)
 for name,verify,prefix in [('partner-history',p.verify_partner_history_links,'partner-history/'),('team-need',p.verify_team_need_handoff,'team-need/'),('offer-comparison',p.verify_offer_comparison,'offer-comparison/'),('protections',p.verify_recommended_protections,'protections/'),('history',p.verify_completed_trade_browser,'feature/')]:
  out[name]=verify(z,plan,prefix=prefix);assert out[name]['passed']
 out['history_cases']=p.verify_completed_trade_cases(z,plan)
report=dict(candidate=source['candidate'],tree=source['tree'],all_native_guards_passed=True,focused_tests=15,preservation_tests=15,results=out)
(b/'focused-resource-verified.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
