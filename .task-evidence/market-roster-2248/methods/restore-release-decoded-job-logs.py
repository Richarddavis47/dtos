"""Restore exact decoded job text, including original mixed Windows CRLF."""
from pathlib import Path
import json,hashlib
b=Path('/workspace/2248-market-final/release-decoded-originals')
for m in sorted(b.glob('*-transfer-input.json')):
 r=json.loads(m.read_text());job=str(r['job']);p=b/(job+'.log')
 if p.exists():continue
 parts=sorted((b/('transport-'+job)).glob('part-*.log'));assert len(parts)==r['parts'];raw=b''.join(x.read_bytes() for x in parts);assert raw.count(b'\n')==r['lf_count'];lines=raw.split(b'\n');inds=set(r['crlf_indices']);restored=b''.join(line+(b'\r\n' if i in inds else b'\n') for i,line in enumerate(lines[:-1]))+lines[-1];text=restored.decode();assert len(text.encode('utf-16-le'))//2==r['original_utf16_units'];assert text.count('\r\n')==len(inds);p.write_bytes(restored);r.update(bytes=len(restored),sha256=hashlib.sha256(restored).hexdigest(),exact_decoded_text_utf16_length_verified=True,original_newline_map_restored=True,parts_sha256=[dict(name=x.name,bytes=x.stat().st_size,sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in parts]);(b/(job+'-transfer.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['job','bytes','sha256']}))
