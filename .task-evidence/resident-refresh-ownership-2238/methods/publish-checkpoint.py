"""Publish only existing sanitized source/focused/resource evidence; full gates remain pending."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/resident-refresh-ownership-2238';out=repo/prefix
assert not out.exists();out.mkdir(parents=True)
(out/'.gitattributes').write_text('* -text\n')
for name in ['source.json','REPORT.md','SCOUT_HANDOFF.md','candidate-production.patch','measurement-source-association.json','resident-host-final-verified.json','resident-host-prior-job.json','resident-host-prior-original.log','resident-host-prior-original.zip','superseded-509-cancellation.json','superseded-hosted-final-records.json','prior-artifact-download-receipts.json','PRIOR_ATTEMPTS.md','prior-package.json','publisher-tests-108.log','publisher-lint-108.log','publisher-compile-108.log']:
 shutil.copy2(b/name,out/name)
for p in r.iterdir():
 if p.is_file() and p.name!='next-publication.json':
  dest=out/'task-records'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
for folder in ['resource-final-108','local-preflight-108','local-restoration-unused-108']:
 shutil.copytree(r/folder,out/folder)
for name in ['retention_memory_acceptance.py','retention_memory_probe.py','retention_reproduction.py','run-constrained.py']:
 dest=out/'methods'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(r.parent/name,dest)
for name in ['run-local-canonical.py','prepare-methods-and-report.py','package-prior.py','publish-checkpoint.py']:
 shutil.copy2(b/name,out/'methods'/name)
original=Path('/workspace/dtos-publisher-2238/.github/release-plans/2238-prior.zip');shutil.copy2(original,out/'Prior-attempts.zip')
(out/'README.md').write_text('''# Resident-refresh ownership evidence checkpoint

**VALIDATING — PR#327 unmerged; production unchanged.**\n
This publishes existing sanitized source, focused controls and resource evidence for independent review while full exact-source mandatory gates run. It is not a release or Granite acceptance. Read REPORT.md, source.json, SCOUT_HANDOFF.md and PRIOR_ATTEMPTS.md. Native hosted final resource originalZIP is linked by its source job; byte/checksum verification is in resident-host-final-verified.json. The failed originalZIP and prior archive are preserved separately.\n
Application candidate108624a0a3be61501376de243a54f23dd2e1e34a/treea09397ad108c2bf221a70ff55fe7e06ab1cbc07c. Matched controls on509share its exact production function; do not relabel them as108executions. Source-compatible disposable fixtures are not production Granite measurements. Current live preflight/entry/parity remainHELD because existing authenticated Shell/browser control is unavailable here. No memory policy or infrastructure change.\n
New complete validation, immutable publication and deployment receipts will be published only when verified. Original complete logs remain unchanged; oversized logs have separately indexed parts. No credentials/private production payloads are included.\n''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file():
  data=p.read_bytes();assert not secret.search(data),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(out/'manifest.json').write_text(json.dumps(dict(status='VALIDATING; no release or live recovery claimed',candidate='108624a0a3be61501376de243a54f23dd2e1e34a',tree='a09397ad108c2bf221a70ff55fe7e06ab1cbc07c',files=rows),indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in rows)+hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
paths=[str(p.relative_to(repo)) for p in out.rglob('*') if p.is_file()];spec=b/'checkpoint-paths.nul';spec.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0');subprocess.run(['git','add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Preserve resident-refresh ownership evidence while mandatory gates run'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();(b/'checkpoint-publication.json').write_text(json.dumps(dict(evidence_commit=head,files=len(rows),manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()),indent=2)+'\n');print(head)
