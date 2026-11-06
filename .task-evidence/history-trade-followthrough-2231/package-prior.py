"""Retain original investigation payloads under explicit non-final scope."""
from pathlib import Path
import hashlib,json,re,zipfile
b=Path('/workspace/2231-release');root=b/'investigation';out=Path('/workspace/dtos-publisher-2231/.github/release-plans/2231-prior.zip');meta=json.loads((b/'source.json').read_text());files={}
for p in sorted(root.rglob('*')):
 if p.is_file():files['investigation/'+str(p.relative_to(root))]=p.read_bytes()
for folder,prefix in [('prior-606-local','superseded-606-local'),('prior-606-hosted-logs','superseded-606-hosted-logs'),('prior-606-local-preflight','superseded-606-preflight')]:
 for p in sorted((b/folder).rglob('*')):
  if p.is_file() and 'fixture' not in p.relative_to(b/folder).parts:
   files[prefix+'/'+str(p.relative_to(b/folder))]=p.read_bytes()
for name in ['publisher-lint.log','ci-budget-focused-original-error.log','product-failure-steps.json','superseded-source-decision.json','publisher-runner-path-error-publisher-final.log','publisher-runner-path-error-publisher-final-lint.log','publisher-host-ruff-unavailable.log','resource-reporting-note.json','publisher-prepare-original-failure.log','prepare-original-failure.zip','prepare-original-failure-artifact.json','original-preparation-run.json','publisher-original-source.json','packaging-correction.json']:
 files['prior-setup/'+name]=(b/name).read_bytes()
for name in ['canonical-release-2g-python314-cancelled.zip','canonical-cancelled-metadata.json','integrity-initial.json','metadata-0.json','metadata-1.json']:
 p=b/'prior-606-hosted-originals'/name
 if p.exists():files['superseded-606-hosted-originals/'+name]=p.read_bytes()
files['README.md']=b'''Original prior/intermediate evidence only; never final-source mandatory acceptance.
The original baseline-pagination-matched.log demonstrates the production-source navigation defect. pagination-after.log is the matched corrected-source probe. Initial import-path/navigation-router setup errors are separate. The first original baseline JSON was overwritten by the after-probe; its original console remains, and the baseline-source-replay JSON/log are clearly labelled another execution on the same baseline tree, not recovered original bytes. Saved probe variants and the disclosure note remain intact.
Current-season fixture failures used future event clocks, an incorrect historical-assets test-store binding and an incorrect expected canonical API type. These were corrected in fixtures while retaining application evidence rules. The final real API fixtures use exact numeric provider-shaped IDs, genuine completion/pending/failed statuses and the canonical string season/round contract. Original failing logs and the debug probe remain.
Candidate606 original Product job127596198200 passed620+16 tests but exceeded its aggregate20-minute CI deadline; later steps were skipped, not passed. Its original log and timestamps remain. Superseded606 local and hosted canonical attempts were cancelled after the workflow-budget-only correction, and are incomplete. The original hosted cancelled archive is preserved byte-for-byte with API digest; original partial local consoles, events, measurements and source records are separate. The CI verifier initially assumed every YAML step had a name; its original error is retained.
The123-test precommit focused success and earlier7-test/browser successes are intermediate source scope, not substitutes for final exact-source canonical/hosted validation. The separate recovery/hosted artifacts and final release plan must establish that completion. Publisher lint initially rejected compact one-line test statements; formatting was corrected without disabling any rule.
All payload bytes in this archive are original saved files; this README and the outer manifest are explanatory metadata. No historical immutable evidence was rewritten. No live owner account/cache, production sync, FOIS rebuild or Trade search was used. Cleanup observations do not prove long-term leak freedom.
'''
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,data in sorted(files.items()):
  if Path(name).suffix in {'.py','.json','.jsonl','.log','.md','.txt','.html','.js'}:assert not pattern.search(data),name
  z.writestr(name,data);rows.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 z.writestr('prior-manifest.json',json.dumps(dict(candidate=meta['candidate'],tree=meta['tree'],scope='prior-attempts-only',files=rows),indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for row in rows:assert hashlib.sha256(z.read(row['name'])).hexdigest()==row['sha256']
report=dict(payloads=len(rows),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),scope='Prior/intermediate original bytes; not final acceptance')
(b/'package-prior-report.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
