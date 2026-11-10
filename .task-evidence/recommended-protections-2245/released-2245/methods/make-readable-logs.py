"""Readable byte-preserving parts; never reconstruct or join different attempts."""
from pathlib import Path
import hashlib,json,sys
b=Path('/workspace/2245-recommended-protections');out=b/'readable-originals';out.mkdir(exist_ok=True);sources=[]
for folder in ['hosted-decoded-originals','publisher-decoded-originals','prior-source-b3dd7/hosted-decoded-originals','prior-source-4850546/hosted-decoded-originals']:
 for p in (b/folder).glob('*.log'):sources.append((folder.replace('/','--')+'/'+p.name,p))
for folder in ['prior-source-b3dd7/local-canonical','prior-source-4850546/local-canonical','prior-local-80m/local-canonical']:
 p=b/folder/'unittest-console.log'
 if p.exists():sources.append((folder.replace('/','--')+'/unittest-console.log',p))
if '--final-canonical' in sys.argv:
 assert json.loads((b/'local-verified.json').read_text())['all_local_gates_passed']
 assert json.loads((b/'host-canonical-verified.json').read_text())['all_gates_passed']
 for folder in ['local-canonical','host-canonical-readable']:
  for name in ['unittest-console.log','canonical.log']:
   p=b/folder/name;assert p.is_file();sources.append((folder+'/'+name,p))
records=[]
for name,p in sources:
 data=p.read_bytes();destination=out/name;destination.mkdir(parents=True,exist_ok=True);parts=[];start=0
 while start<len(data):
  end=min(start+60000,len(data))
  while end<len(data) and data[end]&0xc0==0x80:end-=1
  assert end>start
  part=data[start:end];part.decode('utf-8');filename=f'part-{len(parts)+1:04d}.log';(destination/filename).write_bytes(part);parts.append(dict(name=filename,bytes=len(part),sha256=hashlib.sha256(part).hexdigest()));start=end
 assert b''.join((destination/r['name']).read_bytes() for r in parts)==data
 record=dict(original=str(p.relative_to(b)),original_bytes=len(data),original_sha256=hashlib.sha256(data).hexdigest(),parts=parts,qualification='Original decoded UTF-8 hosted console, or original retained inner canonical console; source/attempt labels remain distinct. Long lines may continue across adjacent parts.')
 (destination/'index.json').write_text(json.dumps(record,indent=2)+'\n');(destination/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in parts));records.append(dict(name=name,original_bytes=len(data),original_sha256=record['original_sha256'],parts=len(parts)))
(out/'INDEX.json').write_text(json.dumps(records,indent=2)+'\n');(out/'README.md').write_text('Original consoles split at UTF-8 boundaries into at most60,000byte parts. Follow each index and join parts in numeric order to reproduce its original SHA256. No lines are removed, rewritten or borrowed from another source/attempt. Preliminary/canceled canonical logs are explicitly incomplete; only final canonical logs with separately verified final summaries count as complete.\n');print({'originals':len(records),'parts':sum(r['parts'] for r in records),'original_bytes':sum(r['original_bytes'] for r in records)})
