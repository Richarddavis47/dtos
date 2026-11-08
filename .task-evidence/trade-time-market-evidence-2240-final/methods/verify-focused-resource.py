from pathlib import Path
import hashlib,json,tempfile,re,sys
sys.path.insert(0,'/workspace/dtos-publisher-2240')
from tools.release import publish as p
b=Path('/workspace/2240-trade-time-market');source=json.loads((b/'source.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2240/.github/release-plans/2240.json').read_text());assert plan['candidate']==source['candidate'] and plan['tree']==source['tree']
results={}
with tempfile.TemporaryDirectory() as folder:
 for label,verifier,names in [('local-preflight',p.verify_preflight,('result.json','raw.log','SHA256SUMS')),('local-restoration-unused',p.verify_actuals_restoration,('evidence/result.json','raw.log','prior-study.zip','SHA256SUMS')),('local-resident-refresh',p.verify_resident_refresh,('evidence/result.json','raw.log','SHA256SUMS'))]:
  target=Path(folder)/(label+'.zip');p.make_zip(target,{n:(b/label/n).read_bytes() for n in names});r=verifier(target,plan);assert r['passed'];results[label]=dict(passed=True,head=r['head'],tree=r['tree'],zip_sha256=p.digest(target))
console=(b/'final-source-focused-original.log').read_bytes();assert re.search(rb'Ran 56 tests in [0-9.]+s\s+OK\s*$',console)
with tempfile.TemporaryDirectory() as folder:
 target=Path(folder)/'feature.zip';p.make_zip(target,{'feature/browser.json':(b/'browser-final-source/browser.json').read_bytes(),'feature/feature.json':(b/'feature.json').read_bytes(),'supplied-screen.json':(b/'supplied-screen.json').read_bytes()});feature=p.verify_trade_time_market(target,plan);assert feature['passed']
out=dict(candidate=source['candidate'],tree=source['tree'],resource_controls=results,focused_tests=56,expanded_precommit_tests=162,feature=feature,all_native_guards_passed=True,live_screen='Supplied Main Chat counts; not independently reproduced, not package coverage',scope='Exact-source tests, controlled recorded values and native enforced2GiB controls; no live parity claim')
(b/'focused-resource-verified.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
