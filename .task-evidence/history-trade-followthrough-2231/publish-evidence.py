"""Assemble readable original evidence after verified immutable publication."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2231-release');root=Path('/workspace/team-assessment-handoff/.task-evidence/history-trade-followthrough-2231');root.mkdir(exist_ok=True,parents=True)
assert not (root/'manifest.json').exists(), 'Preserve any already finalized handoff before rerunning packaging'
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2231/.github/release-plans/2231.json').read_text())
assert smoke['production_ready']['deployment']['commit']==merged['merge_commit'] and pub['release']['immutable'] and not pub['release']['draft']
assert local['candidate']==host['candidate']==s['candidate'] and local['tree']==host['tree']==s['tree'] and local['tests']==host['tests']==4136
names=['source.json','source-integrity.json','candidate-production.patch','baseline.json','preservation.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','focused-exact.log','commands.md','run-clean.py','run-constrained.py','invocation.json','local-console.log','local-preflight-console.log','production-before-release.json','render-deployed.json','merged-source.json','publication-verified.json','production-readonly-smoke.json','publisher-production-smoke.json','SCOUT_HANDOFF.md','package-final.py','package-final.log','package-prior.py','package-prior-report.json','harness-preservation.json','environment-reconnection.json','finalize-plan.py','verify-host-canonical.py','verify-production.py','publish-evidence.py','publisher-focused.log','publisher-lint.log','publisher-lint-corrected.log','publisher-final.log','publisher-final-lint.log','publisher-source.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','preparation-certificate.zip','publication-certificate.zip','checkout-reuse.json','resource-verified.json','ci-budget-focused.log','worker-tail-focused.log','superseded-source-decision.json','final-source-lint.log','hosted-history-integrity.log','hosted-resource-integrity.log','resource-reporting-note.json','verify-readable-publication.py','packaging-correction.json','publisher-prepare-original-failure.log','prepare-original-failure.zip','prepare-original-failure-artifact.json','original-preparation-run.json','publisher-original-source.json','publisher-finalized-runtime.log','publisher-finalized-runtime-lint.log','offline-publication-guards.log','publisher-recovery-focused.log','preparation-certificate-metadata.json','publication-certificate-metadata.json','release-admission-before-draft.json','render-deployment-progress.json']
for name in names:shutil.copy2(b/name,root/name)
for name in ['browser-final','local-preflight','readable-console','hosted-logs']:
 shutil.copytree(b/name,root/name,dirs_exist_ok=True)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir(exist_ok=True)
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copy2(source/name,d/name)
for name in ['2231-recovery.zip','2231-prior.zip','2231.json']:shutil.copy2(Path('/workspace/dtos-publisher-2231/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2231-prior.zip') as z:
 d=root/'prior-originals';d.mkdir(exist_ok=True)
 for name in z.namelist():
  target=d/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
d=root/'hosted-resource';d.mkdir(exist_ok=True)
for artifact in ['trade-resource-2g','league-entry-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(artifact+'.zip')) as z:
  for name in ['result.json','summary.json']:
   if name in z.namelist():(d/(artifact+'-'+name)).write_bytes(z.read(name))
def split(source,dest,prefix):
 dest.mkdir(exist_ok=True);data=source.read_bytes();chunks=[];current=bytearray()
 for line in data.splitlines(keepends=True):
  if current and len(current)+len(line)>400000:chunks.append(bytes(current));current.clear()
  current.extend(line)
 if current:chunks.append(bytes(current))
 files=[]
 for i,part in enumerate(chunks,1):
  p=dest/f'{prefix}-{i:03d}.log';p.write_bytes(part);files.append(p)
 assert b''.join(p.read_bytes() for p in files)==data
 (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
product_jobs=[j['id'] for record in json.loads((b/'hosted-final-records.json').read_text()) for j in record['jobs'] if j['name']=='product-browser']; assert len(product_jobs)==1
split(b/'hosted-logs'/(str(product_jobs[0])+'.log'),root/'readable-product-console','product-console')
for log in (root/'hosted-logs').glob('*.log'):
 if log.stat().st_size>400000:split(log,root/('readable-job-'+log.stem),'job-'+log.stem)
index=['# Readable original validation logs','','Each numbered collection concatenates byte-identically to its full original. GitHub decoded job logs are labelled separately from original canonical ZIP payloads.','']
for folder in sorted([root/'readable-console',root/'readable-host-console',root/'readable-product-console',*root.glob('readable-job-*')]):
 index.extend(['## '+folder.name,'','| Download | Bytes | SHA256 |','|---|---:|---|'])
 for p in sorted(folder.glob('*.log')):
  name=str(p.relative_to(root));index.append(f'| [{p.name}]({name}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
 index.append('')
index.extend(['[Full local console](original-local-canonical/unittest-console.log?raw=1) · [Full hosted console](original-host-canonical/unittest-console.log?raw=1) · [Original prior attempts](prior-originals)'])
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# Franchise History to trade follow-through — v1.22.16 / build2231

Released through [PR320](https://github.com/Richarddavis47/dtos/pull/320) and the [immutable release]({pub['release']['html_url']}). Candidate `{s['candidate']}`; validated tree `{s['tree']}`; deployed merge `{merged['merge_commit']}`. [Complete patch](candidate-production.patch), [source/patch integrity](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render live deploy](render-deployed.json), [verified publication/attachments](publication-verified.json), [full Scout acceptance prompt](SCOUT_HANDOFF.md).

## Customer outcome and confirmed defect

The original exchange, observed later trades, exact pick conversion, current observed ownership, source limitations and original-trade links already worked. They are reused. The reproduced integration defect was contextual Back: its URL filter dropped events_page, stored History pages1and2as identical and skipped page1 after returning from a trade. The only application behavior change preserves that existing read-only pagination parameter in the existing bounded navigation mechanism. Routes, canonical history/graph/timeline, prices, grades, scoring, source acquisition and admission policies are unchanged.

The original matched baseline console fails at the next Back target (League instead of the preceding History page). The corrected matched probe passes. Actual clicked controls follow History -> original multi-asset trade -> exact pick -> selected player -> later package -> original trade, then Back through every prior page and both History pages, native Forward and reload. Real disposable account/session middleware and the navigation-context endpoint verify scope. A selected-league switch resets former-league return context.

## Final exact-source validation

| Evidence | Result |
|---|---|
| Broad focused source/timeline/navigation controls |123passed,122.179s|
| Exact-candidate new source/render/browser controls |7passed on the final source (see focused-exact.log);8viewport/league records and8screenshots|
| Local mandatory regression |4136passed,all10canonical gates passed|
| Hosted mandatory canonical |4136passed,all10canonical gates passed|
| Required hosted jobs |12of12passed|
| Main Product executions |{plan['product_tests']}passed; existing620+16and extended29-test history step|
| Publisher scoped integrity/security controls |42passed|
| Canonical manifest payloads |{local['local_manifest_entries']}local / {host['entries']}hosted; all checksums verified|

[Original full local console](original-local-canonical/unittest-console.log?raw=1), [original full hosted console](original-host-canonical/unittest-console.log?raw=1), [readable numbered logs](LOG_INDEX.md), [all hosted records](hosted-final-records.json), [local result](local-verified.json), [hosted result](host-canonical-verified.json). Original failed/incomplete/intermediate attempts remain [separate](prior-originals) and in [2231-prior.zip](2231-prior.zip). No unexecuted gate or deferred worker is counted as successful completion.

Both canonical runs use actual2147483648-byte memory/no swap/two CPUs/network none. Local kernel peak{local['kernel_peak']}bytes; hosted{host['kernel_peak']}bytes; no OOM/OOM-kill. Dedicated existing Trade/league-entry/FOIS worker execution, deferral, recovery, cancellation and cleanup controls pass on this exact source. Peaks from deliberately pressured fixtures do not represent ordinary navigation demand, and cleanup observations do not prove long-term leak freedom. [Protected-object identities](preservation.json) establish unchanged core/platform/routes/services/components. The8GiB validation scratch prerequisite remains intact; scratch cleanup removed only a recorded obsolete dependency-image backup, not original validation evidence.

## Evidence categories and remaining limits

Day Traders' bounded retained replay supplies original trade1333655835015942144, pickPICK-2026-R2-ORIG7, selected playerDTOS-P-13346 and later trade1414718106177122304. Pagination waivers and accounts are explicitly disposable. Arkham retained history is an independent scope/qualification control, not an invented auction-pick conversion. Day traces include the final subsequent Arkham membership-switch URL as the full chronology; separate records verify scope reset. Four sizes320x432,375x667,390x844,1280x900pass keyboard/touch emulation, focus, overflow and disclosure-request controls. Physical Safari is untested.

Current-season disposable Weeks1–8 survive real fresh owned publication, cache restoration, eviction and reopening through rendered history/trade routes. Existing actual sync/save tests remain mandatory. Missing clocks preserve original consideration while withholding continuation; pending/failed API records never become completed movements. Exact pick originals remain distinct from holders/selecting franchises. Missing periods, ambiguous manager tenure, current observations versus uninterrupted holdings, current prices versus historical quotes and FOIS RETAINED / NOT REVALIDATED stay qualified. No retrospective decision grade or championship credit is inferred.

The initial baseline JSON snapshot was overwritten by the first after-probe; its original failing console remains. A separately labelled baseline-source replay is another actual execution on the same source tree, not a recovered original snapshot. Import/navigation-router, future-clock, fixture store-binding, canonical API type and publisher lint setup failures are preserved and corrected without relaxing application assertions or resource policy. No immutable historical evidence was replaced. The first guarded preparation correctly refused a recovery archive missing the local preflight raw-log subpath. The original console already existed; its exact bytes were copied to the required subpath and a new checksum sidecar was generated. No test was rerun or reconstructed. The original failed publisher revision, logs and outcome are retained; only evidence packaging and its guard were corrected. The initial606candidate passed620+16Product assertions but exceeded the aggregate20-minute CI deadline. Later gates were skipped, never accepted as passing. The bounded25-minute CI deadline correction retains both commands, every assertion, application/browser timeouts and resource policy. Superseded606local/hosted canonical attempts were cancelled; their partial original bytes and archive remain separate from final acceptance. The structural verifier initially failed on an unnamed YAML step, and a publisher host-runner path/host Ruff availability issue were corrected using the pinned validation runtime. Original errors remain preserved.

Public readiness, immutable publication and bounded guest smoke are live observations. Private authenticated history was not inspected: this session has no associated owner-browser control or Render Shell/SSH capability, and the previous external Cloud inspection401was not retried. Fixture/replay success does not establish a new live Granite/Day/Arkham result. No production sync, FOIS rebuild, Trade search, cache clear, restart, user-data or saved-setting mutation was initiated. Source gaps remain genuine limitations; this release does not acquire missing periods.

[SHA256SUMS](SHA256SUMS) · [Complete manifest](manifest.json) · [Scout prompt](SCOUT_HANDOFF.md).
''')
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if not p.is_file():continue
 data=p.read_bytes()
 if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
 rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Sanitized original payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifestSHA256',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
