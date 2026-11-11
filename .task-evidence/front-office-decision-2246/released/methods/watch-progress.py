"""Read-only bounded progress, never release approval."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,subprocess,time
b=Path(__file__).resolve().parent;s=json.loads((b/'source.json').read_text())
for _ in range(125):
 p=b/'local-canonical/tests.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()] if p.exists() else [];counts=dict(Counter(x['event'] for x in rows));q=b/'local-canonical/result.json';result=json.loads(q.read_text()) if q.exists() else None
 checks=json.loads(subprocess.check_output(['gh','api','repos/Richarddavis47/dtos/commits/'+s['candidate']+'/check-runs?filter=latest&per_page=100'],text=True,timeout=25))['check_runs'];jobs=[{k:x[k] for k in ['name','status','conclusion','head_sha','details_url']} for x in checks if x['name']!='publish-2191'];state=dict(at=datetime.now(timezone.utc).isoformat(),status='VALIDATING',source=s,local_counts=counts,local_current=rows[-1]['test'] if rows else None,local_finished=result is not None,local_result=result,hosted_jobs=jobs,scope='Progress only. Original complete results/manifests/native proof still must pass before publication; old-source failures remain separate. No ownerliveacceptance claimed.')
 (b/'WORK_STATUS.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps({'at':state['at'],'local':counts,'current':state['local_current'],'finished':bool(result),'hosted_success':sum(x['conclusion']=='success' for x in jobs),'required':13}),flush=True)
 if counts.get('failure') or counts.get('error') or counts.get('skip') or any(x['status']=='completed' and x['conclusion']!='success' for x in jobs):print('Knownmandatoryfailure; preserve results andholdrelease',flush=True);break
 if result is not None and len(jobs)==13 and all(x['conclusion']=='success' for x in jobs):break
 time.sleep(50)
