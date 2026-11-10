"""Preserve original failed/incomplete bytes and fixed public references."""
from pathlib import Path
import hashlib,json,zipfile,re
b=Path('/workspace/2245-recommended-protections');s=json.loads((b/'source.json').read_text());target=Path('/workspace/dtos-publisher-2245/.github/release-plans/2245-prior.zip');files={};references=[]
for folder,receipt in [('prior-source-b3dd7','prior-public-readback.json'),('prior-source-4850546','phone-failure-public-readback.json')]:
 readback=json.loads((b/receipt).read_text());assert readback['all_bytes_verified'];commit=readback['commit'];verified={r['name']:r for r in readback['files']}
 for p in (b/folder).rglob('*'):
  if not p.is_file() or any(x in p.parts for x in ['fixture-final','__pycache__']):continue
  relative=str(p.relative_to(b/folder));raw=p.read_bytes()
  # Duplicate pictures and the immutable study input remain fixed and readable
  # at the already byte-verified public commit. Keep every original failed log,
  # manifest and failed/canceled native canonical/Trade archive in this ZIP.
  omit=p.suffix=='.png' or p.name in ['prior-study.zip','public-welcome-partial.zip']
  if omit:
   row=verified[relative];assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'];references.append(dict(source=folder,name=relative,bytes=len(raw),sha256=row['sha256'],url='https://raw.githubusercontent.com/Richarddavis47/dtos/'+commit+'/.task-evidence/recommended-protections-2245/'+folder+'/'+relative))
  else:files[folder+'/'+relative]=raw
# Preserve original incomplete final-source text and byte-verified immutable
# public references for duplicate screenshots, not lost or reconstructed proof.
readback=json.loads((b/'prior-local-public-readback.json').read_text());assert readback['all_bytes_verified'];commit=readback['commit'];verified={r['name']:r for r in readback['files']}
for p in (b/'prior-local-80m').rglob('*'):
 if not p.is_file() or 'fixture-final' in p.parts:continue
 relative=str(p.relative_to(b/'prior-local-80m'));raw=p.read_bytes()
 if p.suffix=='.png':
  row=verified[relative];assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'];references.append(dict(source='prior-local-80m',name=relative,bytes=len(raw),sha256=row['sha256'],url='https://raw.githubusercontent.com/Richarddavis47/dtos/'+commit+'/'+readback['prefix']+'/'+relative))
 else:files['prior-local-80m/'+relative]=raw
files['prior-local-public-readback.json']=(b/'prior-local-public-readback.json').read_bytes()
for name in ['PRIOR_ATTEMPTS.md','baseline-reproduction-original.log','focused-attempt-1-original.log','focused-attempt-2-original.log','focused-attempt-3-original.log','focused-attempt-4-original.log','layout-correction-focused-original.log','publisher-lint-attempt1-original.log','publisher-lint-attempt2-original.log','publisher-lint-attempt3-original.log']:
 files[name]=(b/name).read_bytes()
files['immutable-public-original-references.json']=(json.dumps(references,indent=2)+'\n').encode()
rows=[];token=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,raw in sorted(files.items()):
  assert not token.search(raw),name;z.writestr(name,raw);rows.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
 z.writestr('prior-manifest.json',json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',files=rows,source_boundary='Each preliminary source retains its original identity and outcome; association with the final release is not final validation. Duplicate photos and the study input remain at checksum-verified fixed public commits, not omitted from available evidence.'),indent=2)+'\n')
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 for row in rows:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
assert target.stat().st_size<100*1024**2
r=dict(files=len(rows),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),original_bytes_verified=True,public_reference_count=len(references));(b/'prior-package.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
