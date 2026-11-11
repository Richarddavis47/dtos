"""Stage byte-original failed packaging evidence; no publication or app work."""
from pathlib import Path, PurePosixPath
from datetime import datetime, UTC
import difflib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import sys
import zipfile

sys.dont_write_bytecode = True

BASE = Path('/workspace/2246-granite-activation/expansion/final-r3')
OUT = BASE / 'evidence-staging/packaging-failures'
SOURCE = dict(candidate='4cf524c488efb36c77defd78bfd7acf84a3f6ddd',
              tree='79fe9268fb3394604559bbcbe1119616a080b71b')
MIN_FREE = 8 * 1024**3
PART_SIZE = 60 * 1024**2
MAX_FILE = 64 * 1024**2
MAX_RAW = 512 * 1024**2
records = {}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and '\\' not in name,
            'Unsafe relative evidence path')
    require(not set(path.parts).intersection({'private', '.git', '.env'}),
            'Private/environment path excluded')
    require(path.name not in {'id_rsa', 'id_ed25519'} and path.suffix.lower() not in {'.pem', '.key'},
            'Key material path excluded')


controls = json.loads((BASE / 'fixture-url-controls-v5-final.json').read_text())
require(controls['all_controls_passed'], 'Public fixture URL controls missing')
helper = BASE / 'fixture_url.py'
require(digest(helper) == controls['classifier_sha256'], 'Reviewed URL classifier changed')
spec = importlib.util.spec_from_file_location('packaging_privacy_fixture_url', helper)
classifier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = classifier
spec.loader.exec_module(classifier)
credential = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,})')
bearer = re.compile(rb'Authorization\s*:\s*Bearer\s+[A-Za-z0-9._-]{24,}', re.I)
audit_counts = dict(archives=0, members=0, raw_bytes=0, text_members=0, json_documents=0,
                    nested_archives=0, exact_public_fixture_urls=0)


def inspect_json(value):
    audit_counts['json_documents'] += 1
    pending = [value]
    while pending:
        row = pending.pop()
        if isinstance(row, dict):
            require(not (isinstance(row.get('Config'), dict) and 'Env' in row['Config']),
                    'Full Docker Config/Env excluded')
            for key in ('GITHUB_TOKEN', 'GH_TOKEN', 'RENDER_API_KEY', 'DTOS_INSPECTION_AUTH_TOKEN'):
                if key in row:
                    require(row[key] in (None, '', '[REDACTED]', 'REDACTED'),
                            'Credential-valued environment field excluded')
            pending.extend(row.values())
        elif isinstance(row, list):
            pending.extend(row)


def privacy(name, raw):
    require(not credential.search(raw) and not bearer.search(raw),
            'Credential-shaped evidence excluded: ' + name)
    if name.endswith('.zip'):
        return
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return
    audit_counts['text_members'] += 1
    require(not classifier.has_disallowed_sensitive_url(raw),
            'Unapproved sensitive/capability URL excluded: ' + name)
    for match in classifier.URL.finditer(raw):
        try:
            value = match.group().decode('utf-8')
        except UnicodeDecodeError:
            continue
        if classifier.is_exact_disposable_fixture_url(value):
            audit_counts['exact_public_fixture_urls'] += 1
    if name.endswith('.json'):
        inspect_json(json.loads(text))
    elif name.endswith('.jsonl'):
        for line in text.splitlines():
            if line.strip():
                inspect_json(json.loads(line))


def audit_archive(value, label, depth=0):
    require(depth <= 2, 'Nested archive privacy depth exceeded')
    with zipfile.ZipFile(value) as archive:
        members = archive.infolist()
        require(len(members) <= 2000 and len({r.filename for r in members}) == len(members),
                'Unexpected/duplicate archive population')
        require(sum(r.file_size for r in members) <= MAX_RAW, 'Archive privacy budget exceeded')
        audit_counts['archives'] += 1
        for row in members:
            safe_name(row.filename)
            require(not row.flag_bits & 1 and (row.external_attr >> 16) & 0o170000 != 0o120000,
                    'Encrypted/symlink evidence excluded')
            if row.is_dir():
                continue
            require(row.file_size <= MAX_FILE, 'Evidence member exceeds bounded privacy read')
            raw = archive.read(row.filename)  # CRC is checked by the standard reader.
            audit_counts['members'] += 1
            audit_counts['raw_bytes'] += len(raw)
            privacy(label + ':' + row.filename, raw)
            if row.filename.endswith('.zip'):
                audit_counts['nested_archives'] += 1
                audit_archive(io.BytesIO(raw), label + ':' + row.filename, depth + 1)


def add_bytes(destination, raw, kind, origin, purpose):
    safe_name(destination)
    target = OUT / destination
    require(not target.exists() and not target.is_symlink(), 'Preserve existing staged file: ' + destination)
    privacy(destination, raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(raw)
    records[destination] = dict(kind=kind, origin=origin, purpose=purpose)


def copy_file(relative, destination, kind, purpose):
    original = BASE / relative
    require(original.is_file() and not original.is_symlink(), 'Original file missing/unsafe: ' + relative)
    add_bytes(destination, original.read_bytes(), kind, relative, purpose)
    require(digest(OUT / destination) == digest(original), 'Original copy bytes changed')


def main():
    require(shutil.disk_usage('/workspace').free > MIN_FREE + 240 * 1024**2,
            'Insufficient disk budget for staging while retaining originals')
    source = json.loads((BASE / 'source.json').read_text())
    require(all(source[k] == v for k, v in SOURCE.items()), 'Unexpected application source')
    originals = [
        dict(name='recovery-size-114866370-original.zip', bytes=114866370,
             sha256='5548273f038280b792c9b392d480ba979ed8639e683f84b033ddfd88ba4c62a3'),
        dict(name='recovery-missing-focused-proof-103289480-original.zip', bytes=103289480,
             sha256='0e965c50af57d41e606cdf9c162ce249ec3f508fac875a75e538fa79b7be6b7f'),
    ]
    for row in originals:
        path = BASE / 'packaging-failures' / row['name']
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == row['bytes']
                and digest(path) == row['sha256'], 'Preserved original identity mismatch')
        audit_archive(path, row['name'])
    print('Bounded original archive privacy/path/CRC audit passed.', flush=True)

    first = originals[0]
    whole = hashlib.sha256()
    parts = []
    offset = 0
    with (BASE / 'packaging-failures' / first['name']).open('rb') as stream:
        index = 0
        while True:
            raw = stream.read(PART_SIZE)
            if not raw:
                break
            index += 1
            name = 'originals/' + first['name'] + f'.part-{index:03d}'
            add_bytes(name, raw, 'original-byte-range', 'packaging-failures/' + first['name'],
                      'Exact ordered byte range; neither an independent ZIP nor recreated evidence')
            parts.append(dict(name=name, offset=offset, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            whole.update(raw)
            offset += len(raw)
    require(offset == first['bytes'] and whole.hexdigest() == first['sha256'], 'Split did not preserve original')
    joined = hashlib.sha256()
    for part in parts:
        path = OUT / part['name']
        require(path.stat().st_size == part['bytes'] and digest(path) == part['sha256'], 'Part bytes changed')
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                joined.update(chunk)
    require(joined.hexdigest() == first['sha256'], 'Independent staged-part rejoin hash mismatch')
    second = originals[1]
    second_name = 'originals/' + second['name']
    second_target = OUT / second_name
    require(not second_target.exists() and not second_target.is_symlink(), 'Preserve existing staged original ZIP')
    second_target.parent.mkdir(parents=True, exist_ok=True)
    with (BASE / 'packaging-failures' / second['name']).open('rb') as original, second_target.open('xb') as target:
        shutil.copyfileobj(original, target, length=1024 * 1024)
    require(second_target.stat().st_size == second['bytes'] and digest(second_target) == second['sha256'],
            'Exact standalone original copy changed')
    records[second_name] = dict(kind='original-archive', origin='packaging-failures/' + second['name'],
                                purpose='Byte-exact original failed offline-verification package; never a passing release input')

    for name in ('recovery-seal-original.log', 'recovery-seal-reconciled-provenance-original.log',
                 'recovery-offline-original.log'):
        copy_file(name, 'original-logs/' + name, 'original-log', 'Unchanged original packaging/offline failure output')
    for name in ('preservation.json', 'missing-focused-proof-2246-finalized-plan.json',
                 'missing-focused-proof-recovery-package.json'):
        copy_file('packaging-failures/' + name, 'preserved-metadata/' + name,
                  'original-metadata', 'Unchanged metadata retained with the failed archive, not current release acceptance')
    for name in ('harness-origins.json', 'focused-proof-inclusion-revision-v7.json', 'capture-source-reuse.json',
                 'offer-artifact-reuse-revision-v6.json', 'recovery-offer-reuse-readonly-audit.json',
                 'recovery-offer-reuse-readonly-audit.md', 'recovery-offer-reuse-method-peer-review.json'):
        copy_file(name, 'derived-indexes/' + name, 'derived-index',
                  'Clearly late-authored source/integrity reconciliation; not an original execution log or live observation')
    copy_file('inherited-harness-origins-original.json', 'preserved-metadata/inherited-harness-origins-original.json',
              'original-metadata', 'Byte-identical predecessor harness origin record; not relabeled as current execution')

    before_offer = BASE / 'method-revisions/pre-offer-artifact-reuse'
    before_focus = BASE / 'method-revisions/pre-focused-proof-inclusion'
    pairs = [
        ('offer-reuse', 'make-recovery.py', before_offer / 'make-recovery.py', before_focus / 'make-recovery.py'),
        ('offer-reuse', 'verify-recovery-offline.py', before_offer / 'verify-recovery-offline.py', BASE / 'verify-recovery-offline.py'),
        ('offer-reuse', 'PACKAGING_AND_PUBLICATION.md', before_offer / 'PACKAGING_AND_PUBLICATION.md', BASE / 'PACKAGING_AND_PUBLICATION.md'),
        ('focused-proof-inclusion', 'make-recovery.py', before_focus / 'make-recovery.py', BASE / 'make-recovery.py'),
    ]
    for phase, name, before, after in pairs:
        for which, path in [('before', before), ('after', after)]:
            add_bytes(f'methods/{phase}/{which}/{name}', path.read_bytes(), 'method-source', str(path.relative_to(BASE)),
                      'Exact before/after packaging-method bytes; no application or controller code')
        patch = ''.join(difflib.unified_diff(before.read_text().splitlines(True), after.read_text().splitlines(True),
                                          fromfile=phase + '/before/' + name, tofile=phase + '/after/' + name))
        add_bytes(f'methods/{phase}/{name}.patch', patch.encode(), 'derived-diff',
                  'Derived from the two byte-original method snapshots included alongside this diff',
                  'Readable change only; not a recreated execution')
    copy_file('fixture_url.py', 'methods/fixture_url.py', 'method-source',
              'Exact reviewed source-pinned public disposable URL classifier used by the bounded privacy audit')
    copy_file('fixture-url-controls-v5-final.json', 'derived-indexes/fixture-url-controls-v5-final.json',
              'derived-index', 'Existing22metadata-only controls, not application or production authentication tests')

    structure = dict(schema='dtos-byte-original-split-v1', candidate=SOURCE['candidate'], tree=SOURCE['tree'],
                     original=first, parts=parts, joined_sha256=joined.hexdigest(),
                     ordered_parts_verified=True, part_maximum_bytes=PART_SIZE,
                     scope='Exact contiguous byte split of preserved original ZIP; original remains unchanged. No recompression, rewriting or recreated evidence.')
    add_bytes('archive-parts.json', (json.dumps(structure, indent=2) + '\n').encode(), 'derived-index',
              'New byte-range/index metadata', 'Offsets and hashes for byte-exact reassembly of the oversized original')
    audit = dict(schema='dtos-packaging-failure-staging-audit-v1', observed_at=datetime.now(UTC).isoformat(),
                 **SOURCE, original_archives=originals, audit_counts=audit_counts.copy(),
                 credential_shape_scan=True, signed_sensitive_url_scan=True,
                 source_pinned_public_fixture_exception_only=True, full_Docker_Config_Env_excluded=True,
                 path_safety_and_CRC_checked=True, archive_member_limit=2000, member_byte_limit=MAX_FILE,
                 per_archive_uncompressed_limit=MAX_RAW, nested_depth_limit=2,
                 no_production_private_payload_acquired=True, no_network_or_provider_reads=True,
                 no_application_or_controller_changes=True, no_tests_or_production_work=True,
                 original_split_rejoin_verified=True, exact_second_archive_copy_verified=True,
                 source_fixture_classifier_sha256=digest(helper),
                 source_fixture_classifier_controls_sha256=digest(BASE / 'fixture-url-controls-v5-final.json'),
                 method='methods/stage_original_packaging_failures.py',
                 scope='Bounded authored privacy/path/integrity staging audit only. Public fixture exception is proven from pinned public source; no credential values emitted. This is not application validation, independent Scout acceptance, publication or production recovery.')
    add_bytes('privacy-and-staging-audit.json', (json.dumps(audit, indent=2) + '\n').encode(), 'derived-index',
              'New staging audit', 'Method, limits and original-versus-derived provenance')
    readme = '''# Preserved failed Recovery packaging evidence — staged, not published

These are **packaging failures, not application-test failures**. Candidate `4cf524c488efb36c77defd78bfd7acf84a3f6ddd`, tree `79fe9268fb3394604559bbcbe1119616a080b71b`, passed the complete local and hosted application suites on unchanged source:4,364tests/all10gates each,13requiredhostedjobs. This staging package claims no release, merge, deployment, live Granite recovery or Scout acceptance.

The original three failed operations were: a missing harness provenance index, an archive exceeding the unchanged100MiB cap, and a missing `focused-ready.json` inclusion. The original source evidence existed; late-authored indexes and packager corrections do not recreate tests or convert these packaging attempts into passing release inputs.

`original-logs/` contains the three exact original failures. `preserved-metadata/` contains original old-plan/archive receipts. `derived-indexes/` contains clearly labeled later reconciliation and audit records. `methods/` contains byte-original before/after packaging-method sources, derived readable diffs, and the bounded staging method; none is application code or an executed application test. No private production Granite payload was acquired. No provider, sync, FOIS, Trade search, account mutation, credentials, fullDockerConfig/environment dump or new access mechanism is included.

The oversized114,866,370-byte original remains unchanged at its retained source and is represented here by two contiguous ordered parts, each at most60MiB. These parts are not independent ZIP files. `archive-parts.json` gives whole/part hashes, offsets and sizes. Reassemble in a new local directory:

```sh
cat originals/recovery-size-114866370-original.zip.part-001 originals/recovery-size-114866370-original.zip.part-002 > recovery-size-114866370-original.zip
sha256sum recovery-size-114866370-original.zip
```

Expected wholeSHA256: `5548273f038280b792c9b392d480ba979ed8639e683f84b033ddfd88ba4c62a3`.

The second original ZIP is an exact103,289,480-byte copy, SHA256 `0e965c50af57d41e606cdf9c162ce249ec3f508fac875a75e538fa79b7be6b7f`. Do not use either failed archive as a release package. Their original bytes and all failure outcomes are preserved.

Verify the staged files with `sha256sum -c SHA256SUMS`; `publication-manifest.json` lists every payload's provenance, byte count and hash. The checksum file covers all payloads and that manifest; it excludes only itself. Root must independently review this staging selection, publish through the established existing evidence branch to `.task-evidence/front-office-decision-2246/packaging-failures`, and verify the published bytes. No network/commit/push/publication occurred while staging. No checksums or future links prove publication until that actual readback succeeds.
'''
    add_bytes('README.md', readme.encode(), 'authored-document', 'New staging handoff explanation',
              'Status, provenance, byte reassembly and explicit limitations')
    method = 'methods/stage_original_packaging_failures.py'
    records[method] = dict(kind='method-source', origin='New bounded evidence-staging method',
                           purpose='Exact source executed to stage and audit existing original evidence; no app/production operations')

    files = []
    for path in sorted(OUT.rglob('*')):
        if path.is_file():
            name = path.relative_to(OUT).as_posix()
            require(name in records and not path.is_symlink(), 'Unlisted staging file')
            require(path.stat().st_size < 100 * 1024**2, 'Staged Git evidence file exceeds unchanged100MiB')
            files.append(dict(name=name, bytes=path.stat().st_size, sha256=digest(path), **records[name]))
    manifest = dict(schema='dtos-packaging-failure-publication-manifest-v1', **SOURCE,
                    scope='Staging only: byte-original failed packaging evidence and labeled derived methodology; not publication or application acceptance',
                    intended_prefix='.task-evidence/front-office-decision-2246/packaging-failures',
                    files=files)
    manifest_path = OUT / 'publication-manifest.json'
    with manifest_path.open('x') as stream:
        stream.write(json.dumps(manifest, indent=2) + '\n')
    sums = [(row['name'], row['sha256']) for row in files]
    sums.append(('publication-manifest.json', digest(manifest_path)))
    with (OUT / 'SHA256SUMS').open('x') as stream:
        stream.write(''.join(value + '  ' + name + '\n' for name, value in sums))
    actual = {path.relative_to(OUT).as_posix() for path in OUT.rglob('*') if path.is_file()}
    require(actual == {row['name'] for row in files} | {'publication-manifest.json', 'SHA256SUMS'},
            'Strict staged population mismatch')
    for name, expected in sums:
        require(digest(OUT / name) == expected, 'Final staging checksum mismatch')
    require(digest(BASE / 'packaging-failures' / first['name']) == first['sha256']
            and digest(BASE / 'packaging-failures' / second['name']) == second['sha256'],
            'Original source archives changed')
    require(shutil.disk_usage('/workspace').free > MIN_FREE, 'Disk budget violated')
    print(json.dumps(dict(staging_complete=True, payloads=len(files), total_payload_bytes=sum(r['bytes'] for r in files),
                          manifest_sha256=digest(manifest_path), checksums_sha256=digest(OUT / 'SHA256SUMS'),
                          original_rejoin_and_copy_verified=True, publication_performed=False,
                          free_bytes=shutil.disk_usage('/workspace').free)), flush=True)


if __name__ == '__main__':
    main()
