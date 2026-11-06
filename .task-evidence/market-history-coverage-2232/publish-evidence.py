"""Publish readable original evidence only after verified release and deployment."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2232-release');root=Path('/workspace/market-history-handoff/.task-evidence/market-history-coverage-2232');root.mkdir(parents=True,exist_ok=True)
assert not (root/'manifest.json').exists(),'Preserve an already finalized handoff'
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());pub=json.loads((b/'publication-verified.json').read_text());plan=json.loads(Path('/workspace/dtos-publisher-2232/.github/release-plans/2232.json').read_text())
assert smoke['production_ready']['deployment']['commit']==merged['merge_commit'] and pub['release']['immutable'] and not pub['release']['draft']
assert local['candidate']==host['candidate']==s['candidate'] and local['tree']==host['tree']==s['tree'] and local['tests']==host['tests']==4152
names=['source.json','source-integrity.json','candidate-production.patch','baseline.json','preservation.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','focused-exact.log','commands.md','run-clean.py','run-constrained.py','invocation.json','local-console.log','local-preflight-console.log','render-deployed.json','merged-source.json','publication-verified.json','production-readonly-smoke.json','publisher-production-smoke.json','SCOUT_HANDOFF.md','package-final.py','package-final.log','package-prior-report.json','harness-preservation.json','finalize-plan.py','verify-host-canonical.py','verify-production.py','publish-evidence.py','publisher-focused.log','publisher-focused-expanded.log','publisher-lint.log','publisher-final.log','publisher-final-lint.log','publisher-source.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','preparation-certificate.zip','publication-certificate.zip','checkout-reuse.json','decoded-log-transport.json','resource-verified.json','lifecycle-verified.json','offline-publication-guards.json','verify-readable-publication.py','preparation-certificate-metadata.json','publication-certificate-metadata.json','prepare-original-failure.log','prepare-original-failure.zip','original-preparation-run.json','prepare-draft-tag-failure-metadata.json','draft-tag-repair-confirmed.json','draft-notes-scope-note.json']
for n in names:shutil.copyfile(b/n,root/n)
for n in ['browser-final','local-preflight','readable-console','hosted-logs']:shutil.copytree(b/n,root/n,dirs_exist_ok=True)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir(exist_ok=True)
 for n in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copyfile(source/n,d/n)
for n in ['2232-recovery.zip','2232-prior.zip','2232.json']:shutil.copyfile(Path('/workspace/dtos-publisher-2232/.github/release-plans')/n,root/n)
with zipfile.ZipFile(root/'2232-prior.zip') as z:
 for n in z.namelist():
  assert not n.startswith('/') and '..' not in Path(n).parts
  p=root/'prior-originals'/n;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(z.read(n))
d=root/'hosted-resource';d.mkdir(exist_ok=True)
for a in ['market-history-coverage-browser','trade-resource-2g','league-entry-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(a+'.zip')) as z:
  for n in ['browser.json','result.json','summary.json']:
   if n in z.namelist():(d/(a+'-'+n)).write_bytes(z.read(n))
def split(source,dest,prefix):
 dest.mkdir(exist_ok=True);data=source.read_bytes();parts=[];block=bytearray()
 for line in data.splitlines(keepends=True):
  if block and len(block)+len(line)>400000:parts.append(bytes(block));block.clear()
  block.extend(line)
 if block:parts.append(bytes(block))
 assert b''.join(parts)==data
 for i,part in enumerate(parts,1):(dest/f'{prefix}-{i:03d}.log').write_bytes(part)
 (dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(part).hexdigest()+f'  {prefix}-{i:03d}.log\n' for i,part in enumerate(parts,1)))
split(b/'host-canonical-readable/unittest-console.log',root/'readable-host-console','host-console')
for log in (root/'hosted-logs').glob('*.log'):
 if log.stat().st_size>400000:split(log,root/('readable-job-'+log.stem),'job-'+log.stem)
for log in (root/'prior-originals').rglob('*.log'):
 if log.stat().st_size>400000:
  label=hashlib.sha256(str(log.relative_to(root)).encode()).hexdigest()[:12]
  split(log,root/('readable-prior-'+label),'prior-'+label)
index=['# Readable original validation logs','','Each numbered collection concatenates byte-identically to its full original. GitHub decoded job logs are labelled separately from original canonical ZIP payloads.','']
for folder in sorted([root/'readable-console',root/'readable-host-console',*root.glob('readable-job-*'),*root.glob('readable-prior-*')]):
 index+=['## '+folder.name,'','| Download | Bytes | SHA256 |','|---|---:|---|']
 for p in sorted(folder.glob('*.log')):
  index.append(f'| [{p.name}]({p.relative_to(root)}?raw=1) | {p.stat().st_size} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |')
 index.append('')
index+=['[Full local console](original-local-canonical/unittest-console.log?raw=1) · [Full hosted console](original-host-canonical/unittest-console.log?raw=1) · [Original prior attempts](prior-originals)']
(root/'LOG_INDEX.md').write_text('\n'.join(index)+'\n')
(root/'README.md').write_text(f'''# Market history coverage — v1.22.17 / build2232

Released through [PR321](https://github.com/Richarddavis47/dtos/pull/321) and the [immutable release]({pub['release']['html_url']}). Candidate `{s['candidate']}`; validated tree `{s['tree']}`; deployed merge `{merged['merge_commit']}`. [Complete patch](candidate-production.patch), [source/patch integrity](source-integrity.json), [production smoke](production-readonly-smoke.json), [Render live deploy](render-deployed.json), [verified attachments](publication-verified.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Outcome and confirmed defects

The existing compact observation store and v2 trend engine already supplied compatible sparse comparison values, dates, scope and qualifications to APIs. No upstream source-loss defect was established. A matched baseline reproduction warms selected HTML at two historical checkpoints/+100, admits an earlier compatible80checkpoint with the same current200publication, and observes APIs correctly advancing to three/+120 while cached HTML remains byte-identical and stale. Adding an incompatible format similarly leaves obsolete HTML movement. Reference-only milestones and the existing UTC-day age rule were also absent from HTML cache dependencies.

The corrected bounded read-only revision invalidates both HTML caches on observation/reference/checkpoint revisions and existing UTC aging. It does not change price identity, freshness or compatibility policy. The selected disclosure exposes up to12prepared checkpoints with honest omission wording and a separately labelled current endpoint; all admitted evidence still drives the original comparison. Missing/unknown/incompatible numerical rows remain withheld. A genuine+0comparison remains separate from insufficient trend classification. Selected current providers are correctly distinguished from the provider catalogue.

Sparse observations are not a daily series. No interpolation, imported history, historical price fabrication, recommendation, future return or decision grade is inferred from price movement. Raw-provider30day movement remains independently labelled in player dossiers and links to canonical Market comparison. Observation, publication and retrieval clocks retain distinct meaning. Exact pick originals cannot substitute each other's history. Custom rankings do not contaminate neutral history.

## Final validation

| Evidence | Result |
|---|---|
| Original existing focused source/store/compatibility controls |69passed|
| Broad intermediate focused controls |102passed43.409s|
| Exact-candidate new source/render/browser controls |16passed31.985s;8viewport/league records and24screenshots|
| Local mandatory regression |4152passed;all10canonical gates passed|
| Hosted mandatory regression |4152passed;all10canonical gates passed|
| Required hosted jobs |12of12passed|
| Main Product test executions |{plan['product_tests']}passed|
| Separate publisher integrity/security controls |43passed|
| Canonical verified manifest payloads |{local['local_manifest_entries']}local / {host['entries']}hosted|

[Readable original logs and byte checksums](LOG_INDEX.md), [local result](local-verified.json), [hosted result](host-canonical-verified.json), [hosted jobs/artifacts](hosted-final-records.json), [exact-source browser records](browser-final/browser.json), [original baseline cache failure](prior-originals/investigation/baseline-cache-probe.log?raw=1). Prior baseline assertion failures, fixture setup errors and intermediate attempts remain separate in [prior-originals](prior-originals) and [2232-prior.zip](2232-prior.zip). No incomplete, deferred or unexecuted work is counted as completion.

Both canonical runs enforce2147483648bytes/no swap/two CPUs/network none. Local kernel peak{local['kernel_peak']}bytes; hosted{host['kernel_peak']}bytes; no OOM/OOM-kill. Existing Trade/FOIS/sync/league-entry execution, safe deferral, recovery, cancellation and cleanup guards pass. Five-case local preflight protects FOIS reserves; snapshots are advisory and process-local coordination does not prove other-worker idleness. Deliberately pressured fixture peaks are not ordinary-navigation memory demand. Cleanup observations do not prove long-term leak freedom. The unchanged8GiB diagnostic scratch gate remains intact; cleanup removed only a checksum-verified redundant public download, recorded clean completed duplicate checkouts and ignored regenerable bytecode. Git compaction retained unreachable objects and preserved all refs, source and original logs.

## Evidence categories and remaining limitations

Production baseline/readiness, authorized Render deployment metadata, immutable publication and bounded guest smoke are live observations. Authenticated private Market history was not inspected: this session has no associated owner-browser or Render Shell/SSH capability, and the prior external inspection401was not repeated. Fixture league IDs are independent scope controls using an admitted global Market reference, not proof of current live scoring settings or owner checkpoint coverage. No production sync, Trade search, FOIS rebuild, cache clear, restart or saved-data/settings mutation was initiated.

Multiple/one/no checkpoints, genuine zero, future exclusions, stale observations, reference-only milestones, source/context changes, native/incompatible units, exact picks and player-dossier links are deterministic disposable controls. All four viewports320x432,375x667,390x844,1280x900passed keyboard/touch emulation, focus, document overflow and disclosure-request controls. Physical iPhone/Safari and comprehensive screen-reader acceptance remain unverified. Absent upstream periods remain absent; shipping this rendering correction does not create new source history or establish Granite recovery.

The original baseline test run had two fixture errors (premature datetime annotation patch and a nonexistent cache build method); corrected fixture setup demonstrated six assertion-only baseline failures. A subsequent provider-label mismatch was corrected consistently for dictionary/string catalogue entries. An expired disposable pick quote was correctly rejected, then its retrieval clock corrected without weakening age rules. The first publisher setup command was rejected before execution because its requested new working directory did not exist; setup then ran from the existing repository. All original errors remain preserved, without rewriting immutable historical evidence. Initial guarded preparation42153745141passed evidence collection but correctly refused the draft after a notes-only GitHub PATCH changed its tag to an untagged placeholder. The same draft was repaired with explicit tag and target; no application or publisher code changed. The original failed job log/artifact and before/after metadata are preserved separately. Only the subsequent successful preparation permits merge/publication.

[Complete Scout acceptance prompt](SCOUT_HANDOFF.md) · [SHA256SUMS](SHA256SUMS) · [Manifest](manifest.json).
''')
pattern=re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)');rows=[]
for p in sorted(root.rglob('*')):
 if not p.is_file():continue
 data=p.read_bytes()
 if p.suffix in {'.json','.jsonl','.log','.txt','.md','.py','.patch','.html','.js'}:assert not pattern.search(data),str(p)
 rows.append(dict(name=str(p.relative_to(root)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
(root/'manifest.json').write_text(json.dumps(dict(candidate=s['candidate'],tree=s['tree'],merge=merged['merge_commit'],status='RELEASED',files=rows),indent=2)+'\n')
(root/'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in rows))
print('Sanitized payloads',len(rows),'bytes',sum(r['bytes'] for r in rows),'manifest',hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest())
