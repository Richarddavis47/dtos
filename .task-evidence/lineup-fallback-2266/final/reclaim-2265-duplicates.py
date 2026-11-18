"""Remove local copies only after confirming exact immutable published bytes."""
from pathlib import Path
import hashlib,json,subprocess,zipfile
B=Path('/workspace/2265-playoff-race')
D=Path(__file__).resolve().parent
R=Path('/workspace/dtos-draft-capital-2247')
release=json.loads(subprocess.check_output(['gh','api','repos/Richarddavis47/dtos/releases/tags/v1.22.50']))
assert release['immutable'] and not release['draft']
assets={a['name']:a for a in release['assets']}
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sources={B/'recovery-package.zip':'Customer-Experience.zip',B/'prior-package-final.zip':'Prior-attempts.zip'}
sources.update({p:p.name for p in (B/'hosted-originals').glob('*.zip')})
copies=[]
for file,name in sources.items():
    a=assets[name]
    if not file.is_file():continue
    assert file.stat().st_size==a['size'] and 'sha256:'+digest(file)==a['digest']
    copies.append(dict(local=str(file),bytes=a['size'],sha256=a['digest'][7:],url=a['browser_download_url']))
    if name == 'Customer-Experience.zip':
        with zipfile.ZipFile(file) as z:
            rows=json.loads(z.read('recovery-manifest.json'))['files']
            for row in rows:
                n=row['name']
                if not n.startswith(('local-canonical/','readable-console/','customer-acceptance/','focused-exact/')):
                    continue
                candidate=B/(n.replace('focused-exact/','preservation-exact/',1) if n.startswith('focused-exact/') else n)
                if n.startswith('customer-acceptance/'):
                    candidate=B/'normalized-customer-acceptance'/n
                if candidate.is_file() and candidate.stat().st_size==row['bytes'] and digest(candidate)==row['sha256']:
                    copies.append(dict(local=str(candidate),bytes=row['bytes'],sha256=row['sha256'],url=a['browser_download_url'],member=n))
e=json.loads((B/'final-readable-published.json').read_text())
assert e['all_remote_bytes_verified']
subtree=subprocess.check_output(['git','rev-parse',e['commit']+':'+e['prefix']],text=True,cwd=R).strip()
tree=json.loads(subprocess.check_output(['gh','api','repos/Richarddavis47/dtos/git/trees/'+subtree+'?recursive=1']))
assert not tree['truncated']
for row in tree['tree']:
    if row['type']!='blob':continue
    p=B/'final-readable'/row['path']
    if p.is_file() and p.stat().st_size == row['size']:
        raw=p.read_bytes()
        assert hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==row['sha']
        copies.append(dict(local=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),url=e['url'],member=row['path']))
assert len({r['local'] for r in copies})==len(copies)
(D/'scratch-recovery-verified-2265.json').write_text(json.dumps(copies,indent=2)+'\n')
for row in copies:
    Path(row['local']).unlink()
print('Reclaimed',sum(r['bytes'] for r in copies),'bytes of verified replicas')
