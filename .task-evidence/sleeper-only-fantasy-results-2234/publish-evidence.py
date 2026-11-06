"""Make final original logs readable; never publish before verified guarded release."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2234-release');checkout=Path('/workspace/sleeper-results-handoff');relative='.task-evidence/sleeper-only-fantasy-results-2234';root=checkout/relative
m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2234/.github/release-plans/2234.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['tests']==host['tests']==4216
assert pub['release']['immutable'] and not pub['release']['draft'] and len(pub['release']['assets'])==20 and smoke['production_ready']['deployment']['commit']==merged['merge_commit']
root.mkdir(parents=True,exist_ok=True);assert not (root/'manifest.json').exists()
required=['post-validation-source-clean.json','version-availability.json','REPORT.md','SCOUT_HANDOFF.md','source.json','source-integrity.json','candidate-production.patch','baseline.json','harness-preservation.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','focused-exact.log','commands.md','run-clean.py','run-constrained.py','finish-local.py','sequential-final-scopes.json','invocation.json','local-console.log','local-preflight-console.log','merged-source.json','publication-verified.json','production-readonly-smoke.json','publisher-production-smoke.json','render-deployed.json','render-service-baseline.json','package-final.py','package-final.log','package-prior.py','package-prior-report.json','package-prior-final.log','finalize-plan.py','verify-host-canonical.py','verify-local-canonical.py','verify-production.py','verify-certificate.py','verify-readable-publication.py','publish-evidence.py','publisher-focused-final.log','publisher-final-plan-verification.log','publisher-lint-final.log','publisher-compilation.log','publisher-source.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','preparation-certificate.zip','publication-certificate.zip','preparation-certificate-metadata.json','publication-certificate-metadata.json','preparation-certificate-verification.log','prepared-attachment-verification.json','publication-certificate-verification.log','published-attachment-verification.json','recovery-offline-verified.json','recovery-offline-integrity.log','product-artifact-integrity.log','lifecycle-artifact-integrity.log','resource-verified.json','lifecycle-verified.json','verify-product-artifacts.py','verify-lifecycle.py','prior-hosted-status-final.json','published-raw-joblogs-verified.json','published-raw-job-logs.zip','clean-checkout.json','coverage-map.json','timestamp-token-focused.log','timestamp-token-control.json','native-sleeper-selected-score.json','native-sleeper-read.log','read-native-sleeper.py','native-sleeper-replay.py','native-sleeper-replay.json','native-sleeper-replay.log','native-sleeper-component.html','browser-access.json','before-after.py','before-after.json','before-after.log','product-test-counts.json','artifact-download-receipts.jsonl','ruff-final.log','local-canonical-integrity.log','completed-checkout-retirement.log','retired-duplicate-images.json','scratch-reclamation.json']
for name in required:assert (b/name).is_file(),name;shutil.copyfile(b/name,root/name)
for name in ['browser-final','local-preflight','readable-console','prior-attempts']:shutil.copytree(b/name,root/name,dirs_exist_ok=True)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir(exist_ok=True)
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copyfile(source/name,d/name)
for name in ['2234-recovery.zip','2234-prior.zip','2234.json']:shutil.copyfile(Path('/workspace/dtos-publisher-2234/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2234-prior.zip') as z:
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts
  if Path(name).suffix not in {'.log','.json','.jsonl','.md','.txt','.py','.patch','.html'} and Path(name).name!='SHA256SUMS':continue
  dest=root/'prior-originals'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
resource=root/'hosted-resource';resource.mkdir(exist_ok=True)
for name in ['current-production-coverage-browser','market-history-coverage-browser','trade-resource-2g','league-entry-2g','restoration-preflight-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(name+'.zip')) as z:
  for member in ['browser.json','result.json','summary.json']:
   if member in z.namelist():(resource/(name+'-'+member)).write_bytes(z.read(member))
with zipfile.ZipFile(b/'published-raw-job-logs.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name
  dest=root/'original-product-and-prior-job-logs'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
index_rows=[]
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 job_id=int(log.stem);matches=[]
 for group in [*json.loads((b/'hosted-final-records.json').read_text()),*json.loads((b/'prior-hosted-status-final.json').read_text())]:
  for job in group['jobs']:
   if job['id']==job_id:matches.append(dict(job=job_id,name=job['name'],run=group['run']['id'],source=group['run']['head_sha'],conclusion=job['conclusion'],final_candidate=group['run']['head_sha']==m['candidate'],path=str(log.relative_to(root))))
 assert len(matches)==1;index_rows+=matches
(root/'original-hosted-job-index.json').write_text(json.dumps(index_rows,indent=2)+'\n')
def split(source,dest,prefix):
 data=source.read_bytes();parts=[];start=0
 while start<len(data):
  end=min(start+60000,len(data))
  while end<len(data) and data[end]&0xc0==0x80:end-=1
  assert end>start;parts.append(data[start:end]);start=end
 assert b''.join(parts)==data
 dest.mkdir(exist_ok=True)
 for i,part in enumerate(parts,1):(dest/f'{prefix}-{i:03d}.log').write_bytes(part)
 (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(part).hexdigest()+f'  {prefix}-{i:03d}.log\n' for i,part in enumerate(parts,1)))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 if log.stat().st_size>60000:split(log,root/('readable-original-job-'+log.stem),'original-job-'+log.stem)
for log in (root/'prior-originals').rglob('*.log'):
 if log.stat().st_size>60000:
  label=hashlib.sha256(str(log.relative_to(root)).encode()).hexdigest()[:12];split(log,root/('readable-prior-'+label),'prior-'+label)
index=['# Readable original validation evidence','','Numbered parts concatenate byte-for-byte to the full original. Original canonical and Actions job bytes remain distinct from explicitly labeled connector-decoded prior logs. Superseded and failed attempts are not final acceptance.','']
for folder in sorted([root/'readable-console',root/'readable-host-console',*root.glob('readable-original-job-*'),*root.glob('readable-prior-*')]):
 index+=['## '+folder.name,'','| Download | Bytes | SHA256 |','|---|---:|---|']
 for p in sorted(folder.glob('*.log')):index.append(f'| [{p.name}]({p.relative_to(root)}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
 index.append('')
index+=['[Full local console](original-local-canonical/unittest-console.log?raw=1) · [Full hosted console](original-host-canonical/unittest-console.log?raw=1) · [Raw job identity index](original-hosted-job-index.json) · [Prior original logs](prior-originals)']
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# Sleeper-only fantasy results — v1.22.19 / build 2234

Explicit Sleeper league matchup results now reach dossiers, Market production summaries, asset evidence, Trade facts and public Career History without an NFLverse scoring fallback. Missing NFLverse fields cannot block a compatible native score. Non-Sleeper usage and fixed-reference valuation analysis remain separately labeled. Existing Sleeper forward projections, league scoring and display policy remain unchanged.

Released through [PR323](https://github.com/Richarddavis47/dtos/pull/323) and the [immutable release]({pub['release']['html_url']}). Exact candidate `{m['candidate']}`; validated tree `{m['tree']}`; deployed merge `{merged['merge_commit']}`. [Complete report](REPORT.md), [patch](candidate-production.patch), [independent tree reconstruction](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render deployment](render-deployed.json), [attachment verification](published-attachment-verification.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Contract and customer impact

The shared reader admits finite explicit zero/negative scores at native precision. Contradictory player-map/starter or duplicate ownership scores remain unresolved. Identical player/week observations count once across roster moves. Team custom points never become individual production. Current roster, taxi/IR, bye/DNP and absent records do not invent a score or participation.

Completed-week score-observation windows show their sample and observed subtotal. They do not claim games played, PPG or full-season acquisition. Live/unknown/future records remain separate, and dependent incomplete averages stay withheld. Exact league/season/scoring/generation guards and original knowledge boundaries survive fresh publication, admitted cache restoration and failed refresh. Batch observations are not exact HTTP receipt or provider-publication timestamps. Older reconstructed values and retained grades are not relabeled Sleeper-backed.

## Verification and limits

| Final evidence | Result |
|---|---|
| Focused exact-source controls |171 passed;36 new source-contract tests|
| Full local regression |4,216 passed; all 10 canonical gates passed|
| Full hosted regression |4,216 passed; all 10 canonical gates passed|
| Required hosted jobs |12 of 12 passed|
| Main Product executions |745 passed|
| Guarded publisher controls |44 passed|
| Original canonical manifest payloads |{local['local_manifest_entries']} local / {host['entries']} hosted|

[Original logs and readable chunks](LOG_INDEX.md), [local proof](local-verified.json), [hosted proof](host-canonical-verified.json), [source-bound workflow records](hosted-final-records.json), [four-size browser evidence](browser-final/browser.json). Earlier failures, cancellations and unexecuted gates remain [separate](prior-originals), with all original prior payloads in 2234-prior.zip. The89cc full run's single timestamp-substring test failure is preserved; its correction retains actual-score withholding assertions. No superseded pass replaces final-source acceptance.

Both full runs enforce 2,147,483,648 bytes, no swap, 2 CPUs and offline execution. Local kernel peak {local['kernel_peak']} bytes; hosted{host['kernel_peak']} bytes. Ordinary liveness, worker execution, unsafe-pressure deferral, recovery, actual cancellation/timeout and cleanup remain guarded. Deliberate pressure-fixture peaks are not normal navigation demand; cleanup does not prove long-term leak freedom. The original memory reserves, 8 GiB initial scratch prerequisite and canonical time budgets remain unchanged. [Resource proofs](resource-verified.json), [lifecycle originals](lifecycle-verified.json), [local preflight](local-preflight/result.json).

The full local canonical payload tree is inside 2234-recovery.zip and the full hosted original is attached as canonical-original.zip to the immutable release. Their manifest-relative paths resolve after extraction. The readable folders mirror original core logs and manifests. Prior text originals are directly readable here; prior images and other payloads remain in 2234-prior.zip. Private disposable databases and ignored scratch archives are retained locally and excluded from public handoff.

[Matched before/after fixtures](before-after.json) preserve exact native 23.4738 / 0 / -2.125 values and supported 21.3488 subtotal while leaving fixed-reference generation/values unchanged. Nine critical scoring, projection, optimizer, bilateral, valuation and resource files are byte-identical to production baseline. The [native public source capture](native-sleeper-selected-score.json) found Granite 2026 / week 8 / player 4984 at 26.56 in both source fields; the [frozen replay](native-sleeper-replay.json) uses the exact candidate without further acquisition. It is not an authenticated DTOS route observation, complete season capture or validation of an older 183.82 total.

Authenticated owner source-to-screen parity remains unverified: this session has no associated owner DTOS browser or bound Render Shell/SSH. Native public source access worked; the previous external inspection 401 was not retried. Main Chat's earlier Render-local credential check is supplied evidence only. Public production readiness, deployed identity and guest/authentication-boundary smoke are live checks. No forced production sync, Trade search, FOIS rebuild, cache clear, restart or user preference/ranking/goal/lineup mutation was performed.

320×432,375×667,390×844 and1280×900 pass disposable route/component controls with keyboard, touch emulation, no page overflow and no acquisition from disclosure expansion. Physical Safari and comprehensive assistive-technology acceptance remain qualified.

Matchup evidence cannot cover absent NFL players or establish participation/full-season completeness. Last-valid and source conflicts remain qualified. Existing 2 GiB capacity may still defer cold restoration/heavy work. Shipping this update does not establish Granite entry recovery, a qualified Trade recommendation or the cause of an earlier 503. [Complete independent Scout acceptance prompt](SCOUT_HANDOFF.md).

[Checksums](SHA256SUMS) · [Manifest](manifest.json).
''')
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  data=p.read_bytes()
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
  rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifestSHA256',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
