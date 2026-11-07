"""Publish only existing sanitized source/focused/resource evidence; full gates remain pending."""
from pathlib import Path
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2238-resident-refresh');r=Path('/workspace/2237-cache-duplication/runtime-retention');repo=Path('/workspace/cache-sharing-handoff');prefix='.task-evidence/resident-refresh-ownership-2238';out=repo/prefix
out.mkdir(parents=True,exist_ok=True)
(out/'.gitattributes').write_text('* -text\n')
for name in ['source.json','OWNERSHIP.md','production-retained-memory-samples.json','global-owner-before-fix.log','global-owner-after-fix.log','prior-108-product-log-receipt.json','resident-host-prior-108-verified.json','REPORT.md','SCOUT_HANDOFF.md','candidate-production.patch','measurement-source-association.json','resident-host-final-verified.json','resident-host-prior-job.json','resident-host-prior-original.log','resident-host-prior-original.zip','superseded-509-cancellation.json','superseded-hosted-final-records.json','prior-artifact-download-receipts.json','PRIOR_ATTEMPTS.md','prior-package.json','publisher-tests-0a4.log','publisher-lint-0a4.log','publisher-compile-0a4.log']:
 shutil.copy2(b/name,out/name)
for p in r.iterdir():
 if p.is_file() and p.name!='next-publication.json':
  dest=out/'task-records'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
for folder in ['resource-final-0a4','local-preflight-0a4','local-restoration-unused-0a4']:
 shutil.copytree(r/folder,out/folder,dirs_exist_ok=True)
shutil.copytree(r/'global-fixtures',out/'global-fixtures',dirs_exist_ok=True)
shutil.copy2(r/'global-owner-memory.py',out/'methods/global-owner-memory.py')
for name in ['retention_memory_acceptance.py','retention_memory_probe.py','retention_reproduction.py','run-constrained.py']:
 dest=out/'methods'/name;dest.parent.mkdir(exist_ok=True);shutil.copy2(r.parent/name,dest)
for name in ['run-local-canonical.py','prepare-methods-and-report.py','package-prior.py','publish-checkpoint.py']:
 shutil.copy2(b/name,out/'methods'/name)
original=Path('/workspace/dtos-publisher-2238/.github/release-plans/2238-prior.zip');shutil.copy2(original,out/'Prior-attempts.zip')
(out/'hosted-originals').mkdir(exist_ok=True)
shutil.copy2(b/'hosted-originals/resident-refresh-ownership-2g.zip',out/'hosted-originals/resident-refresh-ownership-2g.zip')
(out/'README.md').write_text('''# Resident-refresh ownership evidence checkpoint

**VALIDATING — PR#327 unmerged; production unchanged.**\n
This publishes existing sanitized source, focused controls and resource evidence for independent review while full exact-source mandatory gates run. It is not a release or Granite acceptance. Read REPORT.md, source.json, SCOUT_HANDOFF.md and PRIOR_ATTEMPTS.md. Native hosted final resource originalZIP is linked by its source job; byte/checksum verification is in resident-host-final-verified.json. The failed originalZIP and prior archive are preserved separately.\n
Application candidate0a4b2aba52a3ebd65ec2c110c2377bfb3f9e7662/treeab6d36fe3a543841e670c48f9654f64aeb5f01d3. Matched controls on509share its exact production function; do not relabel them as0a4executions. Additional global-only matched controls run on final0a4. Source-compatible disposable fixtures are not production Granite measurements. Current live preflight/entry/parity remainHELD because existing authenticated Shell/browser control is unavailable here. No memory policy or infrastructure change.\n
New complete validation, immutable publication and deployment receipts will be published only when verified. Original complete logs remain unchanged; oversized logs have separately indexed parts. No credentials/private production payloads are included.\n''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(out.rglob('*')):
 if p.is_file() and p not in {out/'manifest.json',out/'SHA256SUMS'}:
  data=p.read_bytes();assert not secret.search(data),p;rows.append(dict(name=str(p.relative_to(out)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(out/'manifest.json').write_text(json.dumps(dict(status='VALIDATING; no release or live recovery claimed',candidate='0a4b2aba52a3ebd65ec2c110c2377bfb3f9e7662',tree='ab6d36fe3a543841e670c48f9654f64aeb5f01d3',files=rows),indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(x['sha256']+'  '+x['name']+'\n' for x in rows)+hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
paths=[str(p.relative_to(repo)) for p in out.rglob('*') if p.is_file()];spec=b/'checkpoint-paths.nul';spec.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0');subprocess.run(['git','add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=repo,check=True);subprocess.run(['git','commit','-m','Preserve global and resident maintenance ownership evidence on final candidate'],cwd=repo,check=True);subprocess.run(['git','push','origin','evidence/cache-string-sharing-2237'],cwd=repo,check=True)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();(b/'checkpoint-0a4-publication.json').write_text(json.dumps(dict(evidence_commit=head,files=len(rows),manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest()),indent=2)+'\n');print(head)
