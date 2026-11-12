"""Expose exact decoded successful publisher logs as bounded readable parts."""
from pathlib import Path
import json,hashlib
B=Path(__file__).resolve().parent;T=Path('/workspace/cache-sharing-handoff/.task-evidence/roster-source-scope-2249')
for p in sorted((B/'release-job-consoles').glob('*-transfer.json')):
 m=json.loads(p.read_text());raw=(B/'release-job-consoles'/(str(m['job'])+'.log')).read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256'];raw.decode('utf-8');D=T/'release-job-consoles'/str(m['job']);D.mkdir(parents=True,exist_ok=False);parts=[];off=0
 while off<len(raw):
  end=min(off+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  assert end>off;parts.append(raw[off:end]);off=end
 for i,data in enumerate(parts,1):(D/f'part-{i:03}.log').write_bytes(data)
 assert b''.join(parts)==raw;(D/'transfer.json').write_bytes(p.read_bytes());meta=dict(source=m,parts=[dict(name=f'part-{i:03}.log',bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for i,v in enumerate(parts,1)]);(D/'parts.json').write_text(json.dumps(meta,indent=2)+'\n');(D/'README.md').write_text('# Original publisher console\n\nRun'+str(m['run'])+', publisher`'+m['publisher']+'`. OriginalMCPdecodedtext, notHTTPwirebytes. Whole SHA256`'+m['sha256']+'`. Concatenate parts in order to reproduce exactbytes.\n\n'+'\n'.join(f'- [part-{i:03}.log](part-{i:03}.log)' for i in range(1,len(parts)+1))+'\n')
print('Both original successful publisher consoles split without changing bytes.')
