"""Verify only the changed summary bytes; reuse the full original readback."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib,json,subprocess,zipfile
b=Path('/workspace/2237-cache-duplication');c=Path('/workspace/cache-sharing-handoff');relative='.task-evidence/cache-string-sharing-2237';root=c/relative
old=json.loads((b/'final-readable-verification.json').read_text());base=old['evidence_commit'];commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=c,text=True).strip()
assert subprocess.check_output(['git','ls-remote','origin','refs/heads/evidence/cache-string-sharing-2237'],cwd=c,text=True).split()[0]==commit
changed=subprocess.check_output(['git','diff','--name-only',base,commit,'--',relative],cwd=c,text=True).splitlines();expected=[relative+'/'+n for n in ['README.md','SHA256SUMS','manifest.json']];assert set(changed)==set(expected)
def tree(ref):
 rows=subprocess.check_output(['git','ls-tree','-r',ref,'--',relative],cwd=c,text=True).splitlines();return {line.split('\t',1)[1]:line.split('\t',1)[0] for line in rows}
a,z=tree(base),tree(commit);assert set(a)==set(z) and len(z)==old['verified_files']==1294
assert all(a[n]==z[n] for n in a if n not in expected)
with zipfile.ZipFile(b/'final-public-download.zip') as archive:
 original=json.loads(archive.read('dtos-'+base+'/'+relative+'/manifest.json'))
new=json.loads((root/'manifest.json').read_text());o={r['name']:r for r in original['files']};n={r['name']:r for r in new['files']};assert set(o)==set(n)
assert all(o[name]==n[name] for name in o if name!='README.md')
assert 'by17–20MiB' in (root/'README.md').read_text()
def read(path):
 expected_bytes=(c/path).read_bytes()
 with urlopen(Request('https://raw.githubusercontent.com/Richarddavis47/dtos/'+commit+'/'+path,headers={'User-Agent':'DTOS-evidence-verification'}),timeout=30) as r:data=r.read(len(expected_bytes)+1)
 assert data==expected_bytes
 return dict(name=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
with ThreadPoolExecutor(max_workers=3) as pool:verified=list(pool.map(read,expected))
report=dict(evidence_commit=commit,source_candidate=new['candidate'],tree=new['tree'],merge=new['merge'],prior_full_verification=base,prior_public_receipt_commit='aedd25d1efce420ac0e34353834821f14fa2ada8',prior_archive_sha256=old['archive_sha256'],total_verified_files=1294,unchanged_git_blobs_verified=1291,new_raw_readbacks=verified,manifest_sha256=hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),method='Full previous actual public archive verification plus1291unchanged Git blob identities and direct raw-byte verification of the only3changed files. No second full-archive download claimed.',correction='Rounded retained-memory summary now17–20MiB,including the16.809MiB high-cardinality control. Raw values, original immutable release evidence, source and tests are unchanged.')
(b/'summary-correction-verified.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
