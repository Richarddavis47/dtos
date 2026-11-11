"""Future reviewed prior-only b602 history; no top-level I/O or remote actions.

Preserve the failed hosted689-member original and canceled local258-member
original. Embed selected core bytes, link the full 94MB hosted ZIP only after an
actual immutable failed-b602 publication and complete anonymous byte receipt.
Never apply a successful-canonical guard to these failed/incomplete attempts.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import quote
import zipfile
from fixture_url import has_disallowed_sensitive_url

R2 = Path('/workspace/2246-granite-activation/expansion/final-r2')
PUBLIC_REPO = Path('/workspace/cache-sharing-handoff')
HEAD = 'b602d6acd03cc1c95d85ee734d2d7f28658885cf'
TREE = '8a687ea0256d6e0031b57e08e2a1a38a90a1a535'
RUN = 42991843827
JOB = 130426505856
HOST_ZIP_BYTES = 93758581
HOST_ZIP_SHA = '9a51b7ffb0b4c4e07112e59d2f393ffb37489f5afe75563f661c9ae1ea766e9d'
PUBLIC_PREFIX = '.task-evidence/front-office-decision-2246/failed-b602'
PUBLIC_ZIP = 'hosted/failed-canonical-original.zip'
PUBLIC_COMMIT = '0b88822e9da91205f092dcce07afe0200e0546a8'
PUBLIC_MANIFEST_SHA = 'c9c688ef6e706ac5afad56d2eb25c7f70d0b8ccc65365e1ce8a518fd030146dd'
PUBLIC_RECEIPT_SHA = 'e0335816d41c8ad6bdc3ee6c49762c8efeb2e99149a58cf91464753cd94aa5b7'
PUBLIC_LINKS_SHA = 'c8e70eb8aef41c54a423e6530b22fa20b1ea5cb4efb5a9ec11f449df91b3432a'
CORE = ('result.json', 'manifest.json', 'SHA256SUMS', 'tests.jsonl',
        'canonical-trace.jsonl', 'canonical.log', 'unittest-console.log', 'memory.jsonl')
SIGNED = re.compile(rb'https?://[^\s"<>]*[?&](?:sig|signature|token|access_token|X-Amz-Signature|X-Amz-Credential|X-Goog-Signature|X-Goog-Credential)=', re.I)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def checked(name):
    path = PurePosixPath(name)
    require(name and not path.is_absolute() and '..' not in path.parts and '\\' not in name
            and str(path) == name and not any(ord(char) < 32 for char in name), 'Unsafe prior evidence path')
    require(not set(path.parts).intersection({'.env', 'private', 'local-resource-inputs', '__pycache__'}), 'Excluded prior path')


def raw_file(root, name):
    checked(name)
    path = root / name
    require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents)
            and path.resolve().is_relative_to(root.resolve()), 'Missing/unsafe retained prior original: ' + name)
    return path.read_bytes()


def exact(raw, row, label):
    require(len(raw) == row['bytes'] and digest(raw) == row['sha256'], 'Historical original bytes changed: ' + label)


def verify_publication_receipt_metadata(receipt_raw, links_raw, manifest_raw, sums_raw):
    """Check retained observed HTTPS receipt metadata; perform no fresh readback."""
    require(digest(receipt_raw) == PUBLIC_RECEIPT_SHA and digest(links_raw) == PUBLIC_LINKS_SHA
            and digest(manifest_raw) == PUBLIC_MANIFEST_SHA, 'Reviewed historical publication metadata changed')
    receipt, links, manifest = (json.loads(raw) for raw in (receipt_raw, links_raw, manifest_raw))
    require(receipt['publication_commit'] == PUBLIC_COMMIT and receipt['prefix'] == PUBLIC_PREFIX
            and receipt['source']['candidate'] == HEAD and receipt['source']['tree'] == TREE
            and receipt['manifest_sha256'] == PUBLIC_MANIFEST_SHA and receipt['all_bytes_verified'] is True,
            'Historical immutable failed-source publication/readback identity mismatch')
    require(links['receipt_sha256'] == digest(receipt_raw), 'Historical link index is not bound to the original readback receipt')
    for key in ('source', 'prefix', 'publication_commit', 'publication_tree', 'manifest_sha256',
                'all_bytes_verified', 'all_published_files_including_manifest_and_sidecar', 'all_published_bytes'):
        require(links[key] == receipt[key], 'Historical publication link/receipt disagreement: ' + key)
    require(manifest['source'] == receipt['source'] and manifest['prefix'] == PUBLIC_PREFIX,
            'Historical public manifest source/prefix disagreement')
    payload = manifest['files']
    public_files = {row['name']: row for row in payload}
    require(len(public_files) == len(payload) == manifest['payload_files']
            and sum(row['bytes'] for row in payload) == manifest['payload_bytes'], 'Historical payload population disagreement')
    expected = {name: {'bytes': row['bytes'], 'sha256': row['sha256']} for name, row in public_files.items()}
    require(not {'publication-manifest.json', 'SHA256SUMS'} & set(expected), 'Historical manifest contains its own control rows')
    expected['publication-manifest.json'] = {'bytes': len(manifest_raw), 'sha256': digest(manifest_raw)}
    sum_rows = [line.split('  ', 1) for line in sums_raw.decode('utf-8').splitlines()]
    require(all(len(row) == 2 for row in sum_rows), 'Malformed historical public checksum sidecar')
    sums = {name: checksum for checksum, name in sum_rows}
    require(len(sum_rows) == len(sums) and sums == {name: row['sha256'] for name, row in expected.items()},
            'Historical public checksum sidecar population/hash disagreement')
    expected['SHA256SUMS'] = {'bytes': len(sums_raw), 'sha256': digest(sums_raw)}
    observed = {row['name']: row for row in receipt['files']}
    require(len(observed) == len(receipt['files']) and set(observed) == set(expected),
            'Historical HTTPS receipt must cover exactly every payload, manifest and checksum sidecar')
    url_base = 'https://raw.githubusercontent.com/Richarddavis47/dtos/' + PUBLIC_COMMIT + '/' + PUBLIC_PREFIX + '/'
    for name, row in expected.items():
        checked(name)
        retained = observed[name]
        require(retained['bytes'] == retained['https_bytes_verified'] == row['bytes']
                and retained['sha256'] == retained['https_sha256_verified'] == row['sha256']
                and retained['url'] == url_base + quote(name, safe='/')
                and any(attempt.get('passed') is True and attempt.get('status') == 200 for attempt in retained['attempts']),
                'Historical observed HTTPS bytes/hash/URL disagreement: ' + name)
    require(receipt['all_published_files_including_manifest_and_sidecar'] == len(expected)
            and receipt['all_published_bytes'] == sum(row['bytes'] for row in expected.values()),
            'Historical complete HTTPS receipt totals disagree with actual rows')
    descriptor_keys = {'original_failed_hosted_archive', 'local_cancelled_originals_archive'}
    if 'earlier_local_cancelled_originals_archive' in receipt:
        descriptor_keys.add('earlier_local_cancelled_originals_archive')
    require(set(links['archives']) == descriptor_keys, 'Historical archive link descriptor population changed')
    for key in descriptor_keys:
        descriptor, link = receipt[key], links['archives'][key]
        require(all(link.get(name) == value for name, value in descriptor.items()),
                'Historical original/authored descriptor link disagreement: ' + key)
        member = descriptor['member']
        require(member in expected and descriptor['bytes'] == expected[member]['bytes']
                and descriptor['sha256'] == expected[member]['sha256']
                and link['url'] == url_base + quote(member, safe='/'), 'Historical archive descriptor is not an observed published file')
    return receipt, public_files


def manifest_check(read, expected_members):
    manifest = json.loads(read('manifest.json'))
    sums_rows = [line.split('  ', 1) for line in read('SHA256SUMS').decode().splitlines()]
    require(all(len(row) == 2 for row in sums_rows), 'Malformed historical native checksums')
    sums = {name: sha for sha, name in sums_rows}
    require(len(manifest) == expected_members and len({row['name'] for row in manifest}) == len(manifest)
            and len(sums_rows) == len(sums) == len(manifest), 'Historical native population changed')
    for row in manifest:
        # Complete original population is verified; only selected core is embedded.
        name = row['name']
        parsed = PurePosixPath(name)
        require(not parsed.is_absolute() and '..' not in parsed.parts and '\\' not in name, 'Unsafe native member')
        require(sums[name] == row['sha256'], 'Historical native checksum disagreement')
        exact(read(name), row, name)
    return manifest


def append_b602_history(base, source, add, guards):
    """Called only by reviewed R3 packaging after actual publication inputs exist."""
    require(source['candidate'] != HEAD and source['supersedes'] == HEAD, 'R3 must retain b602 as historical source')
    retained_source = json.loads(raw_file(R2, 'source.json'))
    require(retained_source['candidate'] == HEAD and retained_source['tree'] == TREE, 'Historical R2 source changed')
    rows = []

    def original(root, relative, member):
        raw = raw_file(root, relative)
        require(PurePosixPath(relative).suffix.lower() not in {'.zip', '.db', '.sqlite3', '.env'}, 'Never embed full ZIP/database/env in b602 supplement')
        require(not has_disallowed_sensitive_url(raw, legacy_pattern=SIGNED), 'Signed URL excluded from prior supplement')
        if relative.endswith('.json'):
            value = json.loads(raw)
            values = value if isinstance(value, list) else [value]
            require(not any(isinstance(item, dict) and isinstance(item.get('Config'), dict)
                            and 'Env' in item['Config'] for item in values), 'Full Docker Config.Env excluded')
        add(member, raw, 'Byte-original prior-only b602 file: ' + str(root / relative))
        rows.append({'name': member, 'bytes': len(raw), 'sha256': digest(raw), 'source_file': str(root / relative)})
        return raw

    receipt_raw = raw_file(R2, 'failed-b602-publication-receipt.json')
    links_raw = raw_file(R2, 'failed-b602-publication-links.json')
    public_root = PUBLIC_REPO / PUBLIC_PREFIX
    public_manifest_raw = raw_file(public_root, 'publication-manifest.json')
    public_sums_raw = raw_file(public_root, 'SHA256SUMS')
    receipt, public_files = verify_publication_receipt_metadata(receipt_raw, links_raw, public_manifest_raw, public_sums_raw)
    identity = receipt['source']
    require(identity['candidate'] == HEAD and identity['tree'] == TREE and receipt['prefix'] == PUBLIC_PREFIX
            and receipt['all_bytes_verified'] is True, 'Actual complete failed-b602 publication/readback receipt required')
    commit = receipt['publication_commit']
    require(re.fullmatch(r'[a-f0-9]{40}', commit) is not None, 'Actual immutable failed-b602 evidence commit required')
    url_base = 'https://raw.githubusercontent.com/Richarddavis47/dtos/' + commit + '/' + PUBLIC_PREFIX + '/'
    archive_row = public_files[PUBLIC_ZIP]
    require(archive_row['bytes'] == HOST_ZIP_BYTES and archive_row['sha256'] == HOST_ZIP_SHA, 'Failed hosted original ZIP changed')
    retained_archive = receipt['original_failed_hosted_archive']
    require(retained_archive['member'] == PUBLIC_ZIP and retained_archive['bytes'] == HOST_ZIP_BYTES
            and retained_archive['sha256'] == HOST_ZIP_SHA and retained_archive['manifest_entries'] == 689,
            'Failed-b602 public original archive association changed')
    hosted = R2 / 'failed-final-canonical'
    zip_path = hosted / 'failed-canonical-original.zip'
    exact(raw_file(hosted, 'failed-canonical-original.zip'), archive_row, 'Full failed hosted original ZIP')
    guards.verify_zip(zip_path)  # CRC/integrity only, no successful native guard.
    with zipfile.ZipFile(zip_path) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate failed native ZIP members')
        manifest_check(archive.read, 689)
        result = json.loads(archive.read('result.json'))
        events = Counter(json.loads(line)['event'] for line in archive.read('tests.jsonl').splitlines())
        console = archive.read('unittest-console.log')
        require(result['head'] == HEAD and result['tree'] == TREE and result['passed'] is False and result['exit_code'] == 1
                and events == Counter(start=4364, stop=4364, failure=1)
                and re.search(rb'Ran 4364 tests in [0-9.]+s\s+FAILED \(failures=1\)\s*$', console), 'Failed hosted source/outcome changed')
        for name in CORE:
            raw = raw_file(hosted / 'core-originals', name)
            require(raw == archive.read(name), 'Retained failed hosted core differs from native ZIP')
            original(hosted / 'core-originals', name, 'superseded-b602/hosted/core-originals/' + name)
    integrity = json.loads(raw_file(hosted, 'artifact-integrity.json'))
    require(integrity['candidate'] == HEAD and integrity['tree'] == TREE and integrity['run'] == RUN and integrity['job'] == JOB
            and integrity['manifest_entries'] == 689 and integrity['all_manifest_bytes_verified'] is True
            and integrity['native_pass_guard_applied'] is False, 'Failed hosted integrity receipt changed')
    run_api = json.loads(raw_file(hosted, 'run-api.json'))
    job_api = json.loads(raw_file(hosted, 'job-api.json'))
    require(run_api['id'] == RUN and run_api['run_attempt'] == 1 and run_api['head_sha'] == HEAD
            and run_api['head_commit']['tree_id'] == TREE and run_api['event'] == 'pull_request'
            and run_api['path'] == '.github/workflows/canonical-release-recovery.yml'
            and run_api['status'] == 'completed' and run_api['conclusion'] == 'failure'
            and job_api['id'] == JOB and job_api['run_id'] == RUN and job_api['run_attempt'] == 1
            and job_api['head_sha'] == HEAD and job_api['name'] == 'canonical-release'
            and job_api['status'] == 'completed' and job_api['conclusion'] == 'failure', 'Failed hosted terminal API provenance changed')
    artifacts_api = json.loads(raw_file(hosted, 'artifacts-api.json'))
    artifacts = [row for row in artifacts_api['artifacts'] if row['id'] == integrity['artifact']['id']]
    require(len(artifacts) == 1, 'Failed hosted original artifact API entry missing')
    artifact = artifacts[0]
    require(artifact['name'] == integrity['artifact']['name'] and artifact['size_in_bytes'] == HOST_ZIP_BYTES
            and artifact['digest'] == 'sha256:' + HOST_ZIP_SHA and artifact['workflow_run']['id'] == RUN
            and artifact['workflow_run']['head_sha'] == HEAD, 'Failed hosted original API digest/source changed')
    transfer = json.loads(raw_file(hosted, 'job-log-transfer.json'))
    decoded = raw_file(hosted, 'job-console-original.log')
    require(transfer['candidate'] == HEAD and transfer['tree'] == TREE and transfer['job_id'] == JOB
            and transfer['passed'] is False and transfer['utf8_bytes'] == transfer['original_bytes'] == len(decoded)
            and transfer['original_sha256'] == digest(decoded)
            and transfer['utf16_length'] == len(decoded.decode('utf-8').encode('utf-16-le')) // 2
            and transfer['part_count'] == len(transfer['parts']), 'Failed hosted decoded console/transfer changed')
    decoded_parts = []
    for row in transfer['parts']:
        require(PurePosixPath(row['name']).name == row['name'], 'Unsafe original decoded console part')
        raw = raw_file(hosted / 'job-console.parts', row['name'])
        exact(raw, row, 'Failed hosted decoded console part')
        decoded_parts.append(raw)
    require(b''.join(decoded_parts) == decoded, 'Failed hosted decoded console original join differs')
    for name in ('artifact-integrity.json', 'artifacts-api.json', 'run-api.json', 'job-api.json',
                 'failure-classification.json', 'projection-audit-failure-window.json', 'job-log-transfer.json', 'job-console-original.log'):
        original(hosted, name, 'superseded-b602/hosted/' + name)

    local = R2 / 'local-canonical'
    local_manifest = manifest_check(lambda name: raw_file(local, name), 258)
    require({p.relative_to(local).as_posix() for p in local.rglob('*') if p.is_file()}
            == {row['name'] for row in local_manifest} | {'manifest.json', 'SHA256SUMS'}, 'Canceled local native population changed')
    local_result = json.loads(raw_file(local, 'result.json'))
    local_events = Counter(json.loads(line)['event'] for line in raw_file(local, 'tests.jsonl').splitlines())
    cancellation = json.loads(raw_file(R2, 'superseded-cancellation-result.json'))
    verified = json.loads(raw_file(R2, 'superseded-local-original-verified.json'))
    require(local_result['head'] == HEAD and local_result['tree'] == TREE and local_result['passed'] is False
            and local_result['exit_code'] == -15 and local_events == Counter(start=2555, stop=2554)
            and cancellation['candidate'] == HEAD and cancellation['tree'] == TREE
            and cancellation['intentional_superseded_cancellation'] is True and cancellation['not_a_passing_gate'] is True
            and cancellation['state_after']['Running'] is False and cancellation['state_after']['Pid'] == 0
            and cancellation['state_after']['OOMKilled'] is False and cancellation['state_after']['ExitCode'] == 241
            and verified['all_original_manifest_bytes_verified'] is True and verified['manifest_members'] == 258
            and verified['stdout_sha256'] == digest(raw_file(R2, 'superseded-container-stdout-original.log')),
            'Canceled local historical source/outcome changed')
    for name in CORE + ('module-cleanup.jsonl', 'runner.py', 'observer/sitecustomize.py', 'observer/fixture_cleanup.py'):
        original(local, name, 'superseded-b602/local-cancelled/core-originals/' + name)
    for name in ('source.json', 'canonical-invocation.json', 'superseded-cancellation-request.json',
                 'superseded-cancellation-result.json', 'superseded-container-state-original.json',
                 'superseded-container-stdout-original.log', 'superseded-local-original-verified.json',
                 'hosted-reconciliation-stopped.json', 'hosted-failure-summary.json',
                 'source-review/failed-canonical-followup.json', 'source-review/failed-canonical-followup.md'):
        original(R2, name, 'superseded-b602/' + name)
    original(R2, 'failed-b602-publication-receipt.json', 'superseded-b602/publication-readback-receipt.json')
    original(R2, 'failed-b602-publication-links.json', 'superseded-b602/publication-links.json')
    original(public_root, 'publication-manifest.json', 'superseded-b602/publication-manifest.json')
    original(public_root, 'SHA256SUMS', 'superseded-b602/publication-SHA256SUMS')

    linked = {'attempt': 'failed-hosted-b602-canonical', 'file': PUBLIC_ZIP, 'bytes': HOST_ZIP_BYTES, 'sha256': HOST_ZIP_SHA,
              'commit': commit, 'prefix': PUBLIC_PREFIX, 'raw_url': url_base + quote(PUBLIC_ZIP, safe='/'),
              'browser_url': 'https://github.com/Richarddavis47/dtos/blob/' + commit + '/' + PUBLIC_PREFIX + '/' + quote(PUBLIC_ZIP, safe='/'),
              'original_archive_rebuilt': False, 'complete_original_archive_embedded': False,
              'original_archive_verified_locally': True, 'original_remote_readback_receipt': 'superseded-b602/publication-readback-receipt.json',
              'historical_source': {'candidate': HEAD, 'tree': TREE},
              'canonical_outcome': {'passed': False, 'canonical_manifest_entries': 689, 'events': dict(events),
                                    'native_success_guard_applied': False, 'scope': 'Prior failed run; not R3 acceptance'}}
    linked_originals = [linked]
    authored_sources = (
        ('local_cancelled_originals_archive', R2, HEAD, TREE, 258, Counter(start=2555, stop=2554)),
        ('earlier_local_cancelled_originals_archive', R2.parent / 'final',
         '3a19eec0a00def82418d9658414f13e090d11b14', '041cfe403ca499c99b2be93a67d8e440c304be6b', 138,
         Counter(start=1145, stop=1144)),
    )
    for key, historical_root, historical_head, historical_tree, population, expected_events in authored_sources:
        if key not in receipt:
            require(key != 'local_cancelled_originals_archive', 'Complete canceled R2 member-container publication is required')
            continue
        descriptor = receipt[key]
        member = descriptor['member']
        checked(member)
        require(descriptor['newly_authored'] is True and descriptor['original_runtime_archive'] is False
                and descriptor['all_original_member_bytes_verified'] is True
                and descriptor['original_manifest_entries'] == population, 'Authored canceled archive provenance changed')
        if 'source' in descriptor:
            require(descriptor['source']['candidate'] == historical_head and descriptor['source']['tree'] == historical_tree,
                    'Authored canceled archive source changed')
        public_row = public_files[member]
        require(public_row['bytes'] == descriptor['bytes'] and public_row['sha256'] == descriptor['sha256'],
                'Authored canceled archive public identity changed')
        raw = raw_file(public_root, member)
        exact(raw, descriptor, 'Complete authored canceled member container')
        archive_path = public_root / member
        guards.verify_zip(archive_path)  # New container integrity only, never a runtime successful-canonical guard.
        with zipfile.ZipFile(archive_path) as complete:
            require(len(complete.namelist()) == len(set(complete.namelist())), 'Duplicate authored member-container entries')
            members = manifest_check(complete.read, population)
            require(set(complete.namelist()) == {row['name'] for row in members} | {'manifest.json', 'SHA256SUMS'},
                    'Authored member-container population differs from complete original native manifest')
            for name in complete.namelist():
                require(complete.read(name) == raw_file(historical_root / 'local-canonical', name),
                        'Authored container changed an original member: ' + name)
            outcome = json.loads(complete.read('result.json'))
            actual_events = Counter(json.loads(line)['event'] for line in complete.read('tests.jsonl').splitlines())
            require(outcome['head'] == historical_head and outcome['tree'] == historical_tree and outcome['passed'] is False
                    and outcome['exit_code'] == -15 and actual_events == expected_events,
                    'Authored canceled container relabeled incomplete source/outcome')
        linked_originals.append({
            'attempt': 'canceled-local-member-container-' + historical_head[:4], 'file': member, 'member': member,
            'bytes': descriptor['bytes'], 'sha256': descriptor['sha256'], 'commit': commit, 'prefix': PUBLIC_PREFIX,
            'raw_url': url_base + quote(member, safe='/'),
            'browser_url': 'https://github.com/Richarddavis47/dtos/blob/' + commit + '/' + PUBLIC_PREFIX + '/' + quote(member, safe='/'),
            'historical_source': {'candidate': historical_head, 'tree': historical_tree},
            'newly_authored': True, 'original_runtime_archive': False, 'all_original_member_bytes_verified': True,
            'original_manifest_entries': population, 'original_archive_rebuilt': False,
            'complete_original_archive_embedded': False, 'original_archive_verified_locally': True,
            'original_remote_readback_receipt': 'superseded-b602/publication-readback-receipt.json',
            'canonical_outcome': {'passed': False, 'incomplete': True, 'canonical_manifest_entries': population,
                                  'events': dict(actual_events), 'validator_exit': -15, 'native_success_guard_applied': False},
            'scope': 'Newly authored ZIP container of complete byte-original native members, not an original runtime ZIP. Incomplete cancellation remains incomplete.',
        })
    summary = {'scope': 'prior-attempts-only', 'candidate': HEAD, 'tree': TREE,
               'hosted_run': RUN, 'hosted_job': JOB, 'hosted_tests': 4364, 'hosted_failures': 1,
               'hosted_manifest_members': 689, 'full_hosted_zip_linked_not_embedded': True,
               'local_status': 'CANCELLED_SUPERSEDED_INCOMPLETE', 'local_manifest_members_verified': 258,
               'local_events': dict(local_events), 'local_validator_exit': -15, 'local_container_exit': 241,
               'b602_publication_readback_verified': True, 'linked_original': linked, 'linked_originals': linked_originals,
               'failure_scope': 'Actual held-worker release.wait(2.0) setup precondition failed; unchanged100ms latency assertion was not reached. Exact GC duration is unproven.',
               'files': rows}
    add('B602_PRIOR_SUPPLEMENT_INDEX.json', encoded(summary), 'Authored prior-only index; original failed/incomplete outcomes remain unchanged')
    return summary
