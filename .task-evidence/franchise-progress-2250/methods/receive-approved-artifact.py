"""Consume only an approved tool-delivered URL in memory, never persist/print it."""
import datetime,hashlib,json,os,re,sys,urllib.parse,urllib.request,zipfile
from pathlib import Path
B=Path(__file__).resolve().parent
print('READY_FOR_APPROVED_ARTIFACT',flush=True)
r=json.loads(sys.stdin.readline());assert re.fullmatch(r'[a-z0-9-]+\.zip',r['file']) and re.fullmatch(r'[0-9a-f]{64}',r['sha256'])
assert isinstance(r['bytes'],int) and 0<r['bytes']<512*1024**2
url=r.pop('url');parts=urllib.parse.urlsplit(url);assert parts.scheme=='https' and not parts.username and not parts.password
out=B/'hosted-originals';out.mkdir(exist_ok=True);target=out/r['file'];partial=out/(r['file']+'.partial-'+str(os.getpid()))
try:
 if target.exists():
  assert target.stat().st_size==r['bytes'] and hashlib.sha256(target.read_bytes()).hexdigest()==r['sha256']
 else:
  sha=hashlib.sha256();count=0
  with urllib.request.urlopen(url,timeout=30) as response,partial.open('xb') as sink:
   while chunk:=response.read(1024*1024):
    count+=len(chunk);assert count<=r['bytes'];sha.update(chunk);sink.write(chunk)
  assert count==r['bytes'] and sha.hexdigest()==r['sha256']
  with zipfile.ZipFile(partial) as z:assert z.testzip() is None
  partial.rename(target)
 with zipfile.ZipFile(target) as z:assert z.testzip() is None
 record=dict(**r,passed=True,source='GitHubMCP approved reusable file delivery; URL consumed only in process memory',observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 (out/(r['file']+'.delivery.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
except Exception as exc:
 print(json.dumps(dict(file=r['file'],passed=False,error_type=type(exc).__name__,partial_preserved=partial.exists())))
 raise SystemExit(1)
