from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2240-trade-time-market');root=Path('/workspace/dtos-publisher-2240');source=json.loads((b/'source.json').read_text())
names=['PRIOR_ATTEMPTS.md','baseline-reproduction-original.log','baseline-reproduction.json','baseline-reproduction.py','baseline-test-module.py','focused-attempt1-original.log','focused-attempt2-original.log','focused-attempt3-original.log','focused-expanded-original.log','lint-attempt1-original.log','publisher-tests-initial.log','publisher-tests-expanded.log','publisher-lint-original.log','scratch-recovery-prior-unreadable.py','scratch-recovery-prior-unreadable.log','scratch-recovery-prior-hardlinks.py','scratch-recovery-prior-hardlinks.log','scratch-recovery.py','scratch-recovery-verified-sanitized.log','scratch-recovery-public-summary.json','published-download-cleanup.json','published-download-cleanup-additional.json','published-download-cleanup-remaining.json','completed-worktree-sparse-cleanup.json','git-maintenance-before.log','git-maintenance-after.log','git-maintenance-original.log']
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows=[];files={}
for n in names:
 p=b/n;assert p.is_file(),n;raw=p.read_bytes();assert not secret.search(raw),n;rows.append(dict(name=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()));files[n]=raw
meta=dict(candidate=source['candidate'],tree=source['tree'],scope='prior-attempts-only',source_boundary='Precommit/author-method original failures, expected baseline failures and preliminary passes are not final exact-source release acceptance.',files=rows)
files['prior-manifest.json']=(json.dumps(meta,indent=2)+'\n').encode()
out=root/'.github/release-plans/2240-prior.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for n,raw in sorted(files.items()):z.writestr(n,raw)
with zipfile.ZipFile(out) as z:assert z.testzip() is None
r=dict(files=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),scope=meta['source_boundary']);(b/'prior-package.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
