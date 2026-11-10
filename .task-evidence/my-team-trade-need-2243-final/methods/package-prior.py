"""Package original prior outcomes separately; no passing-outcome inference."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

base = Path('/workspace/2243-my-team-trade-need')
target = Path('/workspace/dtos-publisher-2243/.github/release-plans/2243-prior.zip')
excluded = {'prior-completed-local-validation-originals.zip', 'prior-earlier-local-validation-originals.zip'}
published = json.loads((base / 'prior-originals-publication.json').read_text())
readback = json.loads((base / 'prior-originals-readback.json').read_text())
assert readback['all_published_bytes_read_back'] and readback['commit'] == published['commit']
excluded.update(row['name'] for row in published['files'] if row['name'].endswith('.zip'))
files = {}
for path in base.iterdir():
    if not path.is_file() or path.name in excluded:
        continue
    if (path.name.startswith(('candidate', 'CANDIDATE', 'C6_', 'source-candidate', 'd30-', 'c6-', 'focused-', 'lint-', 'initial-', 'prepared-need-', 'linux-ordinary-', 'local-scratch-', 'fa-missing-', 'type-filter-', 'stale-manual-', 'explicit-reset-', 'filter-transitions-', 'precommit-', 'canonical-attempt1-', 'canonical-final-attempt1-', 'publisher-composition-', 'publisher-preliminary-', 'publisher-e891-local-'))
            or path.name in {'PRIOR_ATTEMPTS.md', 'superseded-local-canonical-originals.zip', 'superseded-local-canonical-archival.json', 'busy-filter-correction-focused-original.log', 'prior-hosted-job-queue.json'}):
        if path.name != 'candidate-production.patch':
            files[path.name] = path
for folder in base.iterdir():
    if not folder.is_dir():
        continue
    if folder.name in {'prior-hosted-decoded-originals', 'hosted-decoded-originals-candidatefa', 'e891-scratch-prerequisite-attempt1'} or (folder.name.startswith(('browser-final-source-', 'history-browser-final-source-', 'position-filter-layout-'))):
        for path in folder.rglob('*'):
            if path.is_file():
                files[str(path.relative_to(base))] = path
for folder in ['canonical-candidatefa', 'host-canonical-attempt1-readable']:
    for name in ['result.json', 'manifest.json', 'SHA256SUMS', 'canonical.log', 'canonical-trace.jsonl', 'unittest-console.log', 'tests.jsonl', 'memory.jsonl']:
        path = base / folder / name
        assert path.is_file(), path
        files[folder + '/' + name] = path
index = dict(commit=published['commit'], manifest_sha256=published['manifest_sha256'], readback_verified=True,
             scope='Original full prior archives remain intact at pinned, byte-verified existing Git handoff; not final-source passing validation.',
             originals=[dict(row, url='https://raw.githubusercontent.com/Richarddavis47/dtos/' + published['commit'] + '/' + published['prefix'] + '/' + row['name'])
                        for row in published['files'] if row['name'].endswith('.zip')])
index_path = base / 'PRIOR_ORIGINALS_INDEX.json'
index_path.write_text(json.dumps(index, indent=2) + '\n')
files[index_path.name] = index_path
secret = re.compile(rb'(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
rows = []
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for name, path in sorted(files.items()):
        raw = path.read_bytes()
        assert not secret.search(raw), name
        archive.writestr(name, raw)
        rows.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    source = json.loads((base / 'source.json').read_text())
    record = dict(candidate=source['candidate'], tree=source['tree'], scope='prior-attempts-only', files=rows,
                  source_boundary='Each original retains its actual prior source identity. Archive association to the final candidate does not relabel prior outcomes as final-source validation.',
                  omissions='Older completed releases remain in their original immutable public packages and round-trip verified local maintenance archives; their 278MB/145MB archives are not duplicated here.')
    archive.writestr('prior-manifest.json', json.dumps(record, indent=2) + '\n')
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    for row in rows:
        raw = archive.read(row['name'])
        assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
assert target.stat().st_size < 100 * 1024**2
receipt = dict(files=len(rows), bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest(), original_bytes_verified=True)
(base / 'prior-package.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
