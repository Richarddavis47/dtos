"""Make final original logs readable; never publish before verified guarded release."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2235-restoration');checkout=Path('/workspace/restoration-handoff');relative='.task-evidence/restoration-recovery-2235';root=checkout/relative
m=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2235/.github/release-plans/2235.json').read_text())
assert local['candidate']==host['candidate']==m['candidate'] and local['tree']==host['tree']==m['tree'] and local['tests']==host['tests']==4229
assert pub['release']['immutable'] and not pub['release']['draft'] and len(pub['release']['assets'])==21 and smoke['production_ready']['deployment']['commit']==merged['merge_commit']
root.mkdir(parents=True,exist_ok=True);assert not (root/'manifest.json').exists()
required=['REPORT.md', 'SCOUT_HANDOFF.md', 'source.json', 'source-integrity.json', 'candidate-production.patch', 'baseline.json', 'production-baseline-readiness.json', 'render-service-baseline.json', 'render-deployed.json', 'post-validation-source-clean.json', 'version-availability.json', 'commands.md', 'harness-preservation.json', 'local-verified.json', 'host-canonical-verified.json', 'hosted-final-records.json', 'focused-exact.log', 'canonical-console.log', 'local-preflight-console.log', 'run-clean.py', 'run-constrained.py', 'invocation.json', 'clean-checkout.log', 'merged-source.json', 'publication-verified.json', 'production-readonly-smoke.json', 'publisher-production-smoke.json', 'publisher-source.json', 'preparation-run.json', 'publication-run.json', 'prepared-publication.json', 'published-publication.json', 'preparation-certificate.zip', 'publication-certificate.zip', 'preparation-certificate-metadata.json', 'publication-certificate-metadata.json', 'preparation-certificate-verification.log', 'publication-certificate-verification.log', 'prepared-attachment-verification.json', 'published-attachment-verification.json', 'publisher-focused-final.log', 'publisher-finalized-plan-tests.log', 'publisher-lint-final.log', 'publisher-compilation.log', 'recovery-offline-verified.json', 'recovery-offline-integrity.log', 'verify-recovery-offline.py', 'verify-host-canonical.py', 'verify-local-canonical.py', 'verify-production.py', 'verify-certificate.py', 'verify-readable-publication.py', 'publish-evidence.py', 'package-final.py', 'package-final.log', 'package-prior.py', 'package-prior-report.json', 'package-prior.log', 'finalize-plan.py', 'finalize-plan.log', 'resource-verified.json', 'lifecycle-verified.json', 'lifecycle-control-results.json', 'verify-product-artifacts.py', 'verify-lifecycle.py', 'product-artifact-integrity-final.log', 'lifecycle-artifact-integrity.log', 'local-canonical-integrity.log', 'host-canonical-integrity.log', 'measurements.json', 'matched-before-after.json', 'matched-baseline-control.py', 'matched-baseline.log', 'recovery_probe.py', 'baseline-recovery-probe.json', 'baseline-recovery-probe.log', 'restore-cycles.py', 'cycles.log', 'restore-liveness.py', 'restore-liveness.log', 'product-test-counts.json', 'artifact-download-receipts.jsonl', 'ruff-final.log', 'scratch-reclamation.json', 'prior-original-archive-preservation.json', 'immutable-download-retirement.json', 'published-raw-joblogs-verified.json', 'published-raw-job-logs.zip']
for name in required:assert (b/name).is_file(),name;shutil.copyfile(b/name,root/name)
for name in ['local-preflight','local-restoration-unused','readable-console','prior-attempts','cycles','liveness','matched-baseline']:shutil.copytree(b/name,root/name,dirs_exist_ok=True)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir(exist_ok=True)
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copyfile(source/name,d/name)
for name in ['2235-recovery.zip','2235-prior.zip','2235.json']:shutil.copyfile(Path('/workspace/dtos-publisher-2235/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2235-prior.zip') as z:
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts
  if Path(name).suffix not in {'.log','.json','.jsonl','.md','.txt','.py','.patch','.html'} and Path(name).name!='SHA256SUMS':continue
  dest=root/'prior-originals'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
resource=root/'hosted-resource';resource.mkdir(exist_ok=True)
for name in ['restoration-unused-2g','current-production-coverage-browser','market-history-coverage-browser','trade-resource-2g','league-entry-2g','restoration-preflight-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(name+'.zip')) as z:
  for member in ['browser.json','result.json','summary.json','evidence/result.json']:
   if member in z.namelist():(resource/(name+'-'+member.replace('/','-'))).write_bytes(z.read(member))
with zipfile.ZipFile(b/'published-raw-job-logs.zip') as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.startswith('/') and '..' not in Path(name).parts and '\\' not in name
  dest=root/'original-product-and-prior-job-logs'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(name))
index_rows=[]
for log in (root/'original-product-and-prior-job-logs').glob('*.log'):
 job_id=int(log.stem);matches=[]
 for group in json.loads((b/'hosted-final-records.json').read_text()):
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
(root/'README.md').write_text(f"""# Reliable cached-league restoration — v1.22.20 / build 2235

Released through [PR324](https://github.com/Richarddavis47/dtos/pull/324) and the [immutable release]({pub['release']['html_url']}). Production is ready on `{merged['merge_commit']}`. The exact validated candidate is `{m['candidate']}`; application tree `{m['tree']}`. Normal expected-head merge preserved that tree. Both [Actions publication certificates](published-attachment-verification.json) and [read-only production smoke](production-readonly-smoke.json) passed; [Render independently reports the same live commit](render-deployed.json).

Cold restoration now attempts one bounded cleanup of already expired analytical references and safely idle local workers when its known memory deficit permits safe cleanup. It then remeasures raw container usage and reapplies the unchanged guard. Valid/caller-held results, active runtimes, source identity, account boundaries and publications survive. No provider acquisition or automatic search/retry is added.

**Live Granite entry and live Sleeper parity remain unverified in this session.** The available Render management connector does not provide Shell execution; the associated signed-in browser runtime and configured VPN/TCP grant are unavailable. Main Chat's earlier Render-local credential200 is supplied evidence, not our new observation. The external401 was not retried. [Exact existing Render-local procedure and complete Scout prompt](SCOUT_HANDOFF.md) performs one metadata-only snapshot, then permits conditional normal entry and a supported player-week parity check only if fresh evidence permits. No forced entry, sync, FOIS, Trade search, restart, cache clear, user-data or infrastructure change was performed.

## Results and scope

| Evidence | Result |
|---|---|
| Focused exact-candidate controls |69 passed|
| Full local regression |4,229 passed; all ten gates passed|
| Full hosted canonical |4,229 passed; all ten gates passed|
| Required hosted jobs |12 of12 passed|
| Product executions |745 passed|
| Publisher controls |45 passed|
| Original canonical manifest entries |{local['local_manifest_entries']} local / {host['entries']} hosted|
| Immutable attachments |21 verified by native byte readback and independent API digest checks|

[Plain-English report](REPORT.md), [complete patch](candidate-production.patch), [source-file identity](source-integrity.json), [original workflow records](hosted-final-records.json), [original logs/readable chunks](LOG_INDEX.md), [checksums](SHA256SUMS), [manifest](manifest.json).

Both canonical runs enforce2,147,483,648bytes/no swap,2CPUs, offline execution and normal non-root validation. Local lifetime peak:{local['kernel_peak']}bytes; hosted:{host['kernel_peak']}bytes. These include deliberate negative-pressure fixtures and are not normal navigation/restoration demand. The original8GiB initial scratch prerequisite and canonical time budgets were retained.

[Matched controls](matched-before-after.json) use identical22,974,328-byte sealed synthetic input and unchanged501,806,976-byte requirement. The baseline defers before decoding; the final candidate actually restores after freeing222,117,888bytes locally. Hosted independently frees215,027,712bytes and completes. These are separate observations, not additive savings. Neither alone establishes that the owner's reported254,512,784-byte production deficit was resolved. Three expired ownership graphs, a fresh context, two active fixture runtimes and an idle worker establish conditional recovery, not actual production object ownership.

The old PARTIAL study archive is reused byte-for-byte (SHA256df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439). Its synthetic catalog has12teams/10,788identities and two projection weeks; it is not Granite's actual payload. No private production cache was exported or profiled. Matching serialized size cannot establish equal demand. The16× allowance and effective2GiB cap remain unchanged; FOIS768MiB and Trade256+128MiB policies remain independent and intact.

Unsafe unexpired-resource pressure still defers without JSON decode. An explicit retry after pressure relief completes. Active FOIS ownership prevents retiring its worker even between submissions and preserves the full existing reserve. Worker PIDs exit; Python's owned resource tracker is identified separately. Scratch cleanup and OOM counters pass. [Detailed resource facts](measurements.json), [local proof](local-restoration-unused/evidence/result.json), [hosted proof](hosted-resource/restoration-unused-2g-evidence-result.json), [selected actual lifecycle controls](lifecycle-control-results.json).

Six same-process restore/close cycles alternate one-QB/K/DEF and Superflex inputs. Their sampled incremental peaks range34.8–119.3MiB and final post-close usage is184.5MiB, with explicit harnessGC/trim disclosed. Six reads during actual restoration have maximum106.045ms server and237.097ms client duration. These do not establish universal latency, actual private payload demand or long-term leak freedom. The main recovery tool's whole-operation peak above its post-cleanup level includes pre-cleanup samples; it is not a decode-only increment.

No scoring, projection, native Sleeper score, Neutral/Custom valuation, exact pick, submitted lineup, saved preference, FOIS grade or bilateral Trade threshold changes. Explicit zero/negative and missing evidence retain their contracts. Browser coverage includes320×432,375×667,390×844 and desktop through the unchanged required Product/navigation suites; physical iPhone/Safari is not claimed.

Original failures/incomplete attempts remain [separate](prior-originals) and in2235-prior.zip: fixture setup, resource-tracker assertion, mistyped module, read-only Ruff cache and unchanged scratch prerequisite. The matched baseline process intentionally exits on expected HeavyWorkDeferred; it is not a completed evaluation or a final candidate failure. The finalizer's old stdout says12source artifacts, but the authoritative finalized plan/native certificate contains13mandatory original artifacts including the new recovery proof; no artifact was omitted. No unexecuted gate is labeled passed.

The full local canonical payload tree is in2235-recovery.zip. The original hosted artifact is attached ascanonical-original.zip to the immutable release. Their manifests resolve after extraction. Numbered console parts concatenate byte-for-byte to the original hashes. Raw Product job bytes are directly readable and retain their job/source identity. Prior study history and immutable releases remain unchanged.

Valid live working sets can still leave insufficient capacity. A larger RAM plan is not proven technically necessary by this work and was not changed; it remains a separately authorized alternative if legitimate production working sets exceed safe headroom. This release does not establish Granite recovery, the cause of an earlier503 or live Sleeper parity.
""")
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if p.is_file():
  data=p.read_bytes()
  if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
  rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=m['candidate'],tree=m['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifestSHA256',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
