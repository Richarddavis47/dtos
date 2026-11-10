from pathlib import Path
import hashlib,json
b=Path('/workspace/2244-trade-comparison');out=b/'readable-root-logs';out.mkdir(exist_ok=True);rows=[]
for p in sorted(b.glob('*.log')):
 if p.name in {'scratch-recovery-verified-original.log', 'final-evidence-publication-original.log', 'final-public-readback-original.log', 'final-readback-publication-original.log', 'readable-root-original.log'}:continue  # Completed transport/readability self-logs are supplied separately, never indexed while being written.
 raw=p.read_bytes();chunks=[];start=0
 while start<len(raw):
  end=min(start+60000,len(raw))
  while end<len(raw) and raw[end]&0xc0==0x80:end-=1
  chunks.append(raw[start:end]);start=end
 for i,data in enumerate(chunks,1):(out/f'{p.stem}-{i:03d}.log').write_bytes(data)
 assert b''.join(chunks)==raw
 rows.append(dict(original=p.name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),parts=[dict(name=f'{p.stem}-{i:03d}.log',bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for i,data in enumerate(chunks,1)]))
(out/'INDEX.json').write_text(json.dumps(rows,indent=2)+'\n');print('Original root logs',len(rows),'parts',sum(len(r['parts']) for r in rows))
