"""Sanitized held evidence backup; not release or deployed acceptance."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil,subprocess
b=Path('/workspace/2237-cache-duplication');checkout=Path('/workspace/cache-sharing-handoff');root=checkout/'.task-evidence/cache-string-sharing-2237';root.mkdir(parents=True,exist_ok=False);m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());assert local['tests']==4250 and local['all_local_gates_passed']
(root/'.gitattributes').write_text('* -text\n')
for source,prefix in [('canonical','local-canonical'),('readable-console','readable-console'),('local-preflight','local-preflight'),('local-restoration-unused','local-restoration-unused'),('host-failed-4fb-attempt1','host-failed-attempt1')]:shutil.copytree(b/source,root/prefix)
for p in (b/'fixture').glob('*'):
 if p.is_file() and p.name in ['oneqb.json','superflex.json','oneqb-diverse.json','oneqb-unicode.json','projections.sqlite3']:
  dest=root/'synthetic-fixtures'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
for pattern in ['profile-*.json','profile-*.log','profile-*.py','baseline-original-profile-*.json','warm-cycles*.json','warm-cycles*.log','*fixture-metadata.json','*fixture-build.log']:
 for p in b.glob(pattern):
  dest=root/'studies'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
names=['source.json','BASELINE.json','source-integrity.json','candidate-production.patch','commands.md','SCOUT_HANDOFF.md','LIVE_ACCEPTANCE_STATUS.json','local-verified.json','resource-verified.json','lifecycle-verified.json','product-test-counts.json','product-jobs.json','product-artifact-metadata.json','lifecycle-artifact-metadata.json','artifact-download-receipts.jsonl','focused-final-exact.log','lint-final-exact.log','canonical-final-console.log','local-canonical-integrity.log','product-artifact-integrity.log','lifecycle-artifact-integrity.log','cache-memory-verified.json','cache-memory-verification.log','complete-payload-verified.json','complete-payload-verification.log','fixture-metadata.json','build-fixture.py','diverse-fixture.py','unicode-fixture.py','verify-memory.py','verify-complete-payload.py','warm-cycles.py','run-constrained.py','run-clean-final.py','invocation-final.json','verify-local-canonical.py','verify-host-canonical.py','verify-product-artifacts.py','verify-lifecycle.py','host-timeout-attempt1-original-api.json','host-timeout-diagnosis.json','host-timeout-diagnosis.log','host-timeout-prior-run-comparison.json','diagnose-host-timeout.py','publisher-focused-final.log','publisher-lint-final.log','publisher-lint-attempt-records-first.log','publisher-compilation.json','production-baseline.log','pre-release-baseline-check.json','version-availability.json','package-prior.py','package-prior-report.json']
for n in names:
 p=b/n;assert p.is_file(),n;shutil.copy2(p,root/n)
shutil.copy2('/workspace/dtos-publisher-2237/.github/release-plans/2237-prior.zip',root/'2237-prior.zip')
status=dict(observed_at=datetime.now(timezone.utc).isoformat(),status='HELD — hosted canonical attempt2 pending; not released',candidate=m['candidate'],tree=m['tree'],local_tests=4250,local_gates=10,focused=63,hosted_jobs_passed=11,hosted_jobs_required=12,hosted_canonical_run=42293956827,hosted_attempt1='4200s timeout;4008completed/no recorded failure/error/skip;not full regression',hosted_attempt2='One fresh-runner recovery; same source,workflow,2GiB/no-swap/twoCPU and deadlines. No further retries authorized by this bounded recovery decision.',live_granite_parity='HELD:session lacks existing Render Shell/SSH or authenticated browser runtime',release_or_deployment_performed=False)
(root/'checkpoint-status.json').write_text(json.dumps(status,indent=2)+'\n')
index=['# Readable original local regression console','','All numbered parts concatenate byte-for-byte to local-canonical/unittest-console.log. Prior failed/canceled/timed-out evidence is separate in2237-prior.zip. This held snapshot is not a release.','', '| Part | Bytes | SHA256 |','|---|---:|---|']
for p in sorted((root/'readable-console').glob('*.log')):index.append(f'| [{p.name}](readable-console/{p.name}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# HELD evidence backup — league cache string sharing, build2237

This is an evidence backup, not a release. [PR326](https://github.com/Richarddavis47/dtos/pull/326) remains draft. No merge,tag,release or deployment has occurred. Last verified production is v1.22.21/build2236,8af490880bb59b357b0e5fa82575cfa164401b07.

Candidate `{m['candidate']}`, tree `{m['tree']}`. Local validation passed4250tests and all ten gates,63focused controls and640manifest entries. Eleven required hosted jobs pass,including757Product executions. Hosted canonical attempt1 reached the unchanged4200s total deadline after4008completed tests with no recorded failures/errors/skips and no OOM. The last tests and final gates are incomplete. A single bounded fresh-runner attempt2 is running on the exact same source and controls. This snapshot never counts that job as passed.

The implementation shares equal short immutable strings within each JSON read. Mutable containers, persisted bytes,16× basis,2GiB cap,FOIS/Trade reserves,source/native score contracts and lifecycle ownership remain unchanged. Actual kernel before/after full-publication measurements,charged file-page cases,high-cardinality/Unicode sensitivities and full-value equivalence are recorded in [cache-memory-verified.json](cache-memory-verified.json). These are fictional structural fixtures,not a private Granite profile. They do not establish Granite entry,earlier503cause or live score parity. The supplied Nov6snapshot still defers under unchanged arithmetic.

[Exact patch](candidate-production.patch) · [source/protected-module hashes](source-integrity.json) · [local manifest/result](local-canonical/result.json) · [readable complete original console](LOG_INDEX.md) · [timeout diagnosis](host-timeout-diagnosis.json) · [original attempt1 API records](host-timeout-attempt1-original-api.json) · [proposed final acceptance prompt](SCOUT_HANDOFF.md) · [status/limits](checkpoint-status.json) · [checksums](SHA256SUMS).

The original failed/canceled/timed-out payloads and their own manifest are in2237-prior.zip. No missing final record was reconstructed. A publisher-test style error is preserved separately and corrected;49scoped publisher tests and lint pass. Source inspection,disposable fixtures,public readiness and unperformed authenticated live acceptance remain separate. Main Chat's configured-token Render-local identity200 is supplied evidence; no external401retry or token export was attempted. The existing Render-local preflight procedure is in the acceptance prompt,which requires verified publication and fresh capacity before any conditional normal entry. It is not authorization to force a sync,search,FOIS rebuild,cache clear,manual restart or preference change.
''')
secret=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  assert p.stat().st_size<100*1024**2
  data=p.read_bytes()
  if p.suffix in ['.json','.jsonl','.log','.md','.py','.patch','.txt','.html','.js']:assert not secret.search(data),p
  rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],merge=None,status=status['status'],files=rows),indent=2)+'\n');(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows)+hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()+'  manifest.json\n')
paths=[str(p.relative_to(checkout)) for p in root.rglob('*') if p.is_file()];spec=b/'checkpoint-pathspec.nul';spec.write_bytes(b'\0'.join(p.encode() for p in paths)+b'\0');subprocess.run(['git','add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul'],cwd=checkout,check=True);subprocess.run(['git','commit','-m','Preserve build2237 original evidence while hosted canonical recovery is held'],cwd=checkout,check=True);subprocess.run(['git','push','-u','origin','evidence/cache-string-sharing-2237'],cwd=checkout,check=True);print('Published held evidence backup',subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip())
