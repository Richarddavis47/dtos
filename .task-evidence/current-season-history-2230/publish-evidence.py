"""Publish original source-pinned current-season evidence without rewriting history."""
from pathlib import Path
import hashlib,json,re,shutil,zipfile
b=Path('/workspace/2230-release');root=Path('/workspace/team-assessment-handoff/.task-evidence/current-season-history-2230');root.mkdir(exist_ok=True,parents=True)
s=json.loads((b/'source.json').read_text());local=json.loads((b/'local-verified.json').read_text());host=json.loads((b/'host-canonical-verified.json').read_text());merged=json.loads((b/'merged-source.json').read_text());smoke=json.loads((b/'production-readonly-smoke.json').read_text());published=json.loads((b/'publication-verified.json').read_text())
assert smoke['production_ready']['deployment']['commit']==merged['merge_commit'] and published['release']['immutable'] and not published['release']['draft']
assert local['candidate']==host['candidate']==s['candidate'] and local['tree']==host['tree']==s['tree']
names=['source.json','source-integrity.json','candidate-production.patch','patch-verified.json','baseline.json','preservation.json','resource-verified.json','local-verified.json','host-canonical-verified.json','hosted-final-records.json','focused-exact.log','commands.md','run-clean.py','run-constrained.py','invocation.json','local-console.log','local-preflight-console.log','production-before-release.json','render-baseline-0.json','render-baseline-1.json','render-deployed.json','publisher-production-smoke.json','merged-source.json','publication-verified.json','production-readonly-smoke.json','SCOUT_HANDOFF.md','package-final.py','package-final.log','package-prior-report.json','finalize-plan.py','verify-host-canonical.py','verify-production.py','publish-evidence.py','publisher-focused-final.log','publisher-lint-final.log','publisher-final.log','publisher-final-lint.log','publisher-source.json','evidence-packaging-setup-note.json','release-admission-before-draft.json','publisher-index-recovery.json','preparation-run.json','publication-run.json','prepared-publication.json','published-publication.json','preparation-certificate.zip','publication-certificate.zip','scratch-reclamation.json','scratch-publisher-static.json']
for name in names:shutil.copy2(b/name,root/name)
for name in ['current-history-browser','local-preflight','readable-console','hosted-logs']:
 shutil.copytree(b/name,root/name)
for label,source in [('original-local-canonical',b/'canonical'),('original-host-canonical',b/'host-canonical-readable')]:
 d=root/label;d.mkdir()
 for name in ['unittest-console.log','canonical.log','tests.jsonl','memory.jsonl','canonical-trace.jsonl','result.json','manifest.json','SHA256SUMS']:shutil.copy2(source/name,d/name)
for name in ['2230-recovery.zip','2230-prior.zip','2230.json']:shutil.copy2(Path('/workspace/dtos-publisher-2230/.github/release-plans')/name,root/name)
with zipfile.ZipFile(root/'2230-prior.zip') as z:
 d=root/'prior-original-logs';d.mkdir()
 for name in z.namelist():
  if '/' not in name and Path(name).suffix in ['.log','.py','.json','.md']:(d/name).write_bytes(z.read(name))
d=root/'hosted-resource';d.mkdir()
for artifact in ['trade-resource-2g','league-entry-2g','linux-market-lifecycle-ordinary-summary','linux-market-lifecycle-archive-warmed-summary','linux-market-lifecycle-combined-read-summary']:
 with zipfile.ZipFile(b/'hosted-originals'/(artifact+'.zip')) as z:
  for name in ['result.json','summary.json']:
   if name in z.namelist():(d/(artifact+'-'+name)).write_bytes(z.read(name))
def split(source,dest,prefix):
 dest.mkdir();data=source.read_bytes();chunks=[];current=bytearray()
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
split(b/'hosted-logs/127485496255.log',root/'readable-product-console','product-console')
for log in (root/'hosted-logs').glob('*.log'):
 if log.stat().st_size>400000:split(log,root/('readable-job-'+log.stem),'job-'+log.stem)
release=published['release']['html_url']
(root/'README.md').write_text(f'''# Current-season franchise history — v1.22.15 / build2230

Released via [PR319](https://github.com/Richarddavis47/dtos/pull/319) and the [immutable release]({release}). Candidate `{s['candidate']}`; validated tree `{s['tree']}`; deployed merge `{merged['merge_commit']}`. [Complete patch](candidate-production.patch), [patch/tree reproduction](patch-verified.json), [source identity](source-integrity.json), [deployment/readiness](production-readonly-smoke.json), [Render live deploy](render-deployed.json), [publication and verified attachments](publication-verified.json), [complete Scout prompt](SCOUT_HANDOFF.md).

## Confirmed cause and correction

Saved-runtime restoration and cached default startup published compatible source data without registering that owned reference with canonical current-season history. Fresh sync did register it. The actual baseline source tree failed all three matched restoration controls despite retained Weeks1–8 and a completed trade. The shared publication hook fixes both restored entry paths. Owned eviction releases the same source reference; a late old close cannot remove a replacement. No provider request or historical backfill runs merely to render history.

Acquisition metadata was also discarded: failed prior-week requests could retain old evidence without retaining the acquisition/failure qualification. The same bounded source requests now record compatible per-period observations and actual completion timestamps, keeping observed-empty, failed, unavailable, malformed and unacquired separate. Retained rows stay usable and truthfully qualified. Legacy dates remain unknown. A foreign league or season cannot supply fallback evidence. Coverage/freshness participates in the canonical view fingerprint. Current seasons remain Partial when evidence exists and Unknown when no acquisition is established, never Complete merely because they are ongoing.

## Final exact-source acceptance

| Evidence | Outcome |
|---|---|
| Focused history/source/runtime/render checks |117passed,49.022s|
| Local complete regression |4129passed,all10canonical gates passed|
| Hosted complete canonical |4129passed,all10canonical gates passed|
| Required hosted jobs |12of12passed|
| Main Product job |658executions passed,including22new current-history controls|
| Separate publisher integrity/security controls |41passed|
| Canonical manifest payloads |{local['local_manifest_entries']}local / {host['entries']}hosted; every byte/checksum verified|
| Responsive current-history controls |12:3independent league shapes×320x432,375x667,390x844,1280x900; keyboard/touch emulation,nooverflow or extra disclosure requests|

[Local result](local-verified.json), [original full local console](original-local-canonical/unittest-console.log), [readable local parts](readable-console), [original full hosted console](original-host-canonical/unittest-console.log), [readable hosted parts](readable-host-console), [Product decoded original](hosted-logs/127485496255.log), [readable Product parts](readable-product-console), [all hosted records](hosted-final-records.json). Each split concatenates byte-identically to the original. Additional large decoded job logs also have readable-job directories. Native Actions release archives preserve original downloaded ZIPs and verified digests.

Local kernel peak{local['kernel_peak']}bytes; hosted kernel peak{host['kernel_peak']}bytes. Both run under actual2147483648-byte memory/no swap/two CPUs/network none; no OOM/OOM-kill. Dedicated existing Trade, league-entry and FOIS lifecycle controls remain mandatory and independently verified. Full-suite pressure-test peaks are not normal navigation demand or a production worst-case profile. Cleanup observations do not establish indefinite leak freedom.

## Preserved behavior and limitations

Controls exercise real sync/save/restore/render, manager eviction/reopening, default startup, isolated accounts/leagues, source mismatch, legacy caches, current-only refresh and retained failures. Existing completed-season pagination, deduplication, pending/rejected separation, exact moved-pick original franchise/year/round, qualified ownership and FOIS RETAINED / NOT REVALIDATED remain covered. [Preserved object identities](preservation.json) establish unchanged Trade/valuation/scoring/resource source. No saved settings, rankings, goals, valuation methods, lineups or trades were modified.

Granite-shaped1QB/K/DEF and Day/Arkham-shaped Superflex evidence is disposable, not authenticated live history or an exported production cache. Supplied live build2229 Granite Unknown2026 coverage did not establish which weeks had been acquired. This release fixes a demonstrated reusable source path but does not retrospectively prove that particular live cause. This session lacks an authorized owner-browser or Render Shell execution surface; the prior external Cloud inspection401 was not repeated. Public production smoke proves deployed identity and authentication boundaries, not private season completeness. Physical iPhone/Safari is untested. No live sync, FOIS rebuild, Trade search, cache clear, restart or user-data write was used.

[Original prior logs](prior-original-logs) and [separate prior archive](2230-prior.zip) preserve every intermediate failure and setup limitation. The first nonnumeric-ID probe is distinct from the matched baseline reproduction. An intermediate timestamp-placement serialization defect and Playwright-loop fixture setup error were corrected and rerun; no admission guard or assertion was weakened. Earlier release evidence and immutable histories remain untouched.

[SHA256SUMS](SHA256SUMS) · [Full manifest](manifest.json) · [Complete Scout acceptance prompt](SCOUT_HANDOFF.md).
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
