"""Verify source-pinned controls using the established release guards."""
from pathlib import Path
import json,tempfile,re,sys
sys.path.insert(0,'/workspace/dtos-publisher-2244')
from tools.release import publish as p
b=Path('/workspace/2244-trade-comparison');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2244/.github/release-plans/2244.json').read_text());assert plan['candidate']==source['candidate'] and plan['tree']==source['tree'];results={}
with tempfile.TemporaryDirectory() as folder:
 for label,verify,names in [('local-preflight',p.verify_preflight,('result.json','raw.log','SHA256SUMS')),('local-restoration-unused',p.verify_actuals_restoration,('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('local-resident-refresh',p.verify_resident_refresh,('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(folder)/(label+'.zip');p.make_zip(target,{n:(b/label/n).read_bytes() for n in names});r=verify(target,plan);assert r['passed'];results[label]=dict(passed=True,head=r['head'],tree=r['tree'],zip_sha256=p.digest(target))
for name,count in [('focused-final2-original.log',31),('preserved-native-feature-controls-original.log',8)]:
 assert re.search(('Ran '+str(count)+r' tests in [0-9.]+s\s+OK\s*$').encode(),(b/name).read_bytes()),name
files={'feature/browser.json':(b/'history-browser-final-source/browser.json').read_bytes(),'feature/feature.json':(b/'retained-history-feature.json').read_bytes()};files.update({'feature/'+f.name:f.read_bytes() for f in (b/'history-browser-final-source').glob('*.png')})
files.update({'partner-history/'+str(f.relative_to(b/'browser-final-source')):f.read_bytes() for f in (b/'browser-final-source').iterdir() if f.is_file()})
files.update({'team-need/'+f.name:f.read_bytes() for f in (b/'browser-final-source/team-need').iterdir() if f.is_file()})
files.update({'offer-comparison/'+f.name:f.read_bytes() for f in (b/'focused-final2').iterdir() if f.is_file() and not f.name.startswith('review-')})
with tempfile.TemporaryDirectory() as folder:
 target=Path(folder)/'feature.zip';p.make_zip(target,files);feature=p.verify_completed_trade_browser(target,plan,prefix='feature/');feature['matched_cases']=p.verify_completed_trade_cases(target,plan);links=p.verify_partner_history_links(target,plan,prefix='partner-history/');handoff=p.verify_team_need_handoff(target,plan,prefix='team-need/');comparison=p.verify_offer_comparison(target,plan,prefix='offer-comparison/')
r=dict(candidate=source['candidate'],tree=source['tree'],resource_controls=results,focused_tests=31,preserved_feature_tests=8,partner_history_links=links,team_need_handoff=handoff,offer_comparison=comparison,feature=feature,all_native_guards_passed=True,scope='Exact-source disposable controls and retained source replay under enforced2GiB; authenticated owner/Safari acceptance unverified')
(b/'focused-resource-verified.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
