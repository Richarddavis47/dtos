from pathlib import Path
import subprocess,json,hashlib,urllib.request,os
b=Path('/workspace/2243-my-team-trade-need');s=json.loads((b/'source.json').read_text());env=dict(os.environ,DTOS_EXPECTED_HEAD=s['candidate']);wrapper=b/'run-constrained.py'
folder=b/'local-resident-refresh-candidate588';(folder/'inputs').mkdir(parents=True,exist_ok=True)
fixtures={'oneqb.json':'98d76b8452431ff3e6f961b6bddd9a654f7b6d23129d96cce60e52cbf79cb11b','superflex.json':'49915270f727cd3eb6a3a792b8531a487d7da96a06c031ee0e5a176887f69c81','projections.sqlite3':'43541f6a3c738d0ebeac0794cdfd7c009bd27f450816919315b824b512a7b708'}
base='https://raw.githubusercontent.com/Richarddavis47/dtos/2fffaf5672202a27e155a4a9bdfeee62c9ff27b7/.task-evidence/cache-string-sharing-2237/synthetic-fixtures/'
for n,sha in fixtures.items():
 p=folder/'inputs'/n
 if not p.exists():
  with urllib.request.urlopen(base+n,timeout=90) as response:p.write_bytes(response.read())
 assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
for name,cmd,names in [
 ('local-preflight',['-m','tools.validation.restoration_preflight_gate','--output','/evidence/local-preflight'],['result.json','raw.log']),
 ('local-restoration-unused',['-m','tools.validation.restoration_unused_memory','--archive','/prior/Granite-cache-restoration-memory-profile.zip','--output','/evidence/local-restoration-unused/evidence','--native-actuals'],['evidence/result.json','raw.log','prior-study.zip']),
 ('local-resident-refresh',['-m','tools.validation.resident_refresh_ownership','--fixtures','/evidence/local-resident-refresh-candidate588/inputs','--output','/evidence/local-resident-refresh/evidence'],['evidence/result.json','raw.log'])]:
 d=b/name;d.mkdir(exist_ok=True)
 if name=='local-restoration-unused':
  import shutil
  shutil.copyfile('/workspace/2226-efficiency/Granite-cache-restoration-memory-profile.zip',d/'prior-study.zip')
 with (d/'raw.log').open('w') as sink:
  r=subprocess.run(['python',str(wrapper),*cmd],env=env,stdout=sink,stderr=subprocess.STDOUT)
 (d/'invocation.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],command=cmd,exit_code=r.returncode),indent=2))
 if r.returncode:raise SystemExit(r.returncode)
 (d/'SHA256SUMS').write_text(''.join(hashlib.sha256((d/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
 print(name+' complete',flush=True)
