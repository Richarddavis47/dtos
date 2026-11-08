from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2241-trade-partner-history');root=Path('/workspace/dtos-publisher-2241');s=json.loads((b/'source.json').read_text())
names=['PRIOR_ATTEMPTS.md','focused-attempt1-original.log','focused-attempt2-original.log','focused-expanded-original.log','focused-final-precommit.log','lint-attempt1-original.log','lint-final-precommit.log','feature-probe-attempt1.py','feature-probe-attempt1-original.log','merge-approved-attempt1.py','helper-compile-corrected.log','publisher-preliminary-tests.log','publisher-preliminary-lint.log','publisher-preliminary-compile.log','validation-scratch-recovery.json','validation-scratch-public-worktree.json','download-orchestration-note.json']
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');files={};rows=[]
for name in names:
 raw=(b/name).read_bytes();assert not secret.search(raw),name;files[name]=raw;rows.append(dict(name=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
files['prior-manifest.json']=(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],scope='prior-attempts-only',source_boundary='Original failures and preliminary method/test outcomes; not final committed whole-tree validation.',files=rows),indent=2)+'\n').encode();out=root/'.github/release-plans/2241-prior.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for name,raw in sorted(files.items()):z.writestr(name,raw)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
result=dict(files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest());(b/'prior-package.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
