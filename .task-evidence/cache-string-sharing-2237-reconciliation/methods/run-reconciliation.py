from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,time
b=Path('/workspace/2237-cache-duplication');out=b/'reconciliation';records=[]
script=b/'reconcile-restoration.py';frozen=hashlib.sha256(script.read_bytes()).hexdigest()
for fixture in ['oneqb','superflex','oneqb-diverse','oneqb-unicode']:
 for repeat in [2,3,4]:
  for decoder in (['standard','shipping'] if repeat%2==0 else ['shipping','standard']):
   assert hashlib.sha256(script.read_bytes()).hexdigest()==frozen
   cmd=['python',str(b/'run-constrained.py'),'/evidence/reconcile-restoration.py','--decoder',decoder,'--fixture',fixture,'--repeat',str(repeat)]
   logfile=out/f'{fixture}-{decoder}-{repeat}.log';started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
   with logfile.open('wb') as sink:r=subprocess.run(cmd,cwd=b,stdout=sink,stderr=subprocess.STDOUT)
   records.append(dict(command=cmd,started_at=started,seconds=time.monotonic()-t,exit_code=r.returncode,log=logfile.name,instrumentation_sha256=frozen))
   (out/'invocations.json').write_text(json.dumps(records,indent=2)+'\n')
   print(fixture,decoder,repeat,'exit',r.returncode,flush=True)
   if r.returncode:raise SystemExit(r.returncode)
