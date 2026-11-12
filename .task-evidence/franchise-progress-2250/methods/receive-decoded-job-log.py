"""Original approved tool-decoded text, with loss checks and no console echo."""
import datetime,hashlib,json,re,sys
from pathlib import Path
print('READY_FOR_DECODED_JOB_LOG',flush=True)
r=json.loads(sys.stdin.readline());assert isinstance(r['job'],int) and r['job']>0
text=r.pop('text');raw=text.encode('utf-8');assert len(raw)<32*1024**2
assert len(text.encode('utf-16-le'))//2==r['original_utf16_units'] and text.count('\n')==r['original_lf'] and text.count('\r')==r['original_cr']
assert not re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&]sig=[A-Za-z0-9%+/]{16,})',raw),'Credential-shaped content; preserve privately for explicit sanitation'
out=Path('/workspace/2250-franchise-progress/hosted-decoded-originals');out.mkdir(exist_ok=True);path=out/(str(r['job'])+'.log');assert not path.exists();path.write_bytes(raw)
meta=dict(**r,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),received_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Original MCP-decoded text encoded UTF8; UTF16 logical length and originalCR/LF verified. Not HTTP wire bytes.')
(out/(str(r['job'])+'-transfer.json')).write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
