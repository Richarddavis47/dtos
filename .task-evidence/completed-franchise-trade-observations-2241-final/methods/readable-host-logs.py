from pathlib import Path
import hashlib,json
b=Path('/workspace/2241-trade-partner-history');out=b/'hosted-readable-parts';out.mkdir(exist_ok=True);rows=[]
for p in sorted((b/'hosted-decoded-originals').glob('*.log')):
 raw=p.read_bytes();parts=[];start=0
 while start<len(raw):
  end=min(start+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  parts.append(raw[start:end]);start=end
 for i,data in enumerate(parts,1):(out/f'{p.stem}-{i:03d}.log').write_bytes(data)
 assert b''.join(parts)==raw
 rows.append(dict(job=p.stem,original_bytes=len(raw),original_sha256=hashlib.sha256(raw).hexdigest(),parts=[dict(name=f'{p.stem}-{i:03d}.log',bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for i,data in enumerate(parts,1)]))
(out/'INDEX.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for group in rows for r in group['parts']));print('Original jobs',len(rows),'readable parts',sum(len(r['parts']) for r in rows))
