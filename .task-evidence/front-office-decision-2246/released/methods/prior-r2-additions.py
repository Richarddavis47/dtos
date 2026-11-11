"""Reviewed allowlist for prior-only R1/fixture history; no network or execution."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

R1 = Path('/workspace/2246-granite-activation/expansion/final')
EXPANSION = R1.parent
REVIEW = Path('/workspace/cache-sharing-handoff/.task-evidence/front-office-decision-2246/review')
R1_HEAD = '3a19eec0a00def82418d9658414f13e090d11b14'
R1_TREE = '041cfe403ca499c99b2be93a67d8e440c304be6b'
R2_HEAD = 'b602d6acd03cc1c95d85ee734d2d7f28658885cf'
R2_TREE = '8a687ea0256d6e0031b57e08e2a1a38a90a1a535'
PRODUCT_SHA = 'caa378a86fef09ed5cea2638757de1293c349d5bf6f9f591de866200edd9af03'
PRODUCT_ZIP_SHA = '7526340587f981c92af7882ba1ffa5e87b49f626ff2b4647033b2c4132ed6921'
REVIEW_COMMIT = 'fc0b01e3de3164e13855aec495e98e425b75777a'
REVIEW_PREFIX = '.task-evidence/front-office-decision-2246/review'
REVIEW_MANIFEST_SHA = 'e7d20a00e8d3890fc244a934445c1f9fca15fb76aa94a28fb0fcd959d6717d98'
REVIEW_RECEIPT_SHA = '5d64988c98903e74e73040acadfc3467d35987f7bc541ecbd09877cc0b7f4c9e'
SIGNED_URL = re.compile(rb'https?://[^\s"<>]*[?&](?:sig|token|access_token|X-Amz-Signature|X-Amz-Credential)=', re.I)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def append_prior_history(base, source, add, guards):
    """Call only from reviewed packaging; failed/canceled artifacts stay prior-only."""
    if source['candidate'] != R2_HEAD or source['tree'] != R2_TREE or source.get('supersedes') != R1_HEAD:
        raise RuntimeError('R2 prior supplement source association changed; review required')
    rows = []

    def original(root, relative, member=None, *, sha=None, size=None):
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('Required prior original unavailable: ' + str(path))
        raw = path.read_bytes()
        if (sha is not None and digest(raw) != sha) or (size is not None and len(raw) != size):
            raise RuntimeError('Prior original bytes changed: ' + str(path))
        if path.suffix != '.zip' and SIGNED_URL.search(raw):
            raise RuntimeError('Signed URL requires private retention, not packaging: ' + str(path))
        member = member or 'superseded-3a19/' + relative
        add(member, raw, 'Byte-original prior-only file: ' + str(path))
        rows.append({'name': member, 'bytes': len(raw), 'sha256': digest(raw), 'source_file': str(path)})
        return raw

    def derived(member, value, origin):
        raw = encoded(value)
        add(member, raw, origin)
        rows.append({'name': member, 'bytes': len(raw), 'sha256': digest(raw), 'derived': True})

    r1_source = json.loads(original(R1, 'source.json'))
    if r1_source['candidate'] != R1_HEAD or r1_source['tree'] != R1_TREE:
        raise RuntimeError('Superseded source changed')
    log_receipt = json.loads(original(R1, 'product-failure-log-receipt.json'))
    if log_receipt['candidate'] != R1_HEAD or log_receipt['job_id'] != 130410273016:
        raise RuntimeError('Failed Product log source changed')
    product = original(R1, 'product-failed-original.log', sha=PRODUCT_SHA, size=3_618_718)
    if log_receipt['sha256'] != PRODUCT_SHA or log_receipt['bytes'] != len(product) \
            or b'Ran 687 tests in 1142.604s' not in product or b'FAILED (errors=1)' not in product:
        raise RuntimeError('Failed Product outcome changed')
    artifact = json.loads(original(R1, 'product-failure-audit/artifact-original.json'))
    if artifact['head'] != R1_HEAD or artifact['run_id'] != 42986949235 \
            or artifact['sha256'] != PRODUCT_ZIP_SHA or artifact['github_digest_matches'] is not True:
        raise RuntimeError('Failed Product native archive association changed')
    failed_zip = R1 / 'product-failure-audit/trade-resource-3a19-failed-original.zip'
    guards.verify_zip(failed_zip)  # Integrity/CRC only; never a successful Product guard.
    original(R1, 'product-failure-audit/trade-resource-3a19-failed-original.zip',
             sha=PRODUCT_ZIP_SHA, size=25_288_327)
    for name in ('artifact-member-inventory.json', 'protection-checkpoint-manifest.json'):
        original(R1, 'product-failure-audit/' + name)
    for name in ('hosted-reconciliation-stopped.json', 'superseded-cancellation-request.json',
                 'superseded-cancellation-result.json', 'superseded-local-original-verified.json',
                 'cancel-superseded-original.log', 'canonical-invocation.json',
                 'product-log-download-failed-sanitized.log', 'product-log-transfer-initial-attempt.txt'):
        original(R1, name)

    # Verify every stopped local manifest byte, but embed only the requested
    # core originals. Omitted PNG/partial feature records remain on original disk.
    local = R1 / 'local-canonical'
    manifest_raw = (local / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    if len(manifest) != 138 or len({r['name'] for r in manifest}) != len(manifest):
        raise RuntimeError('Canceled local manifest population changed')
    sums_raw = (local / 'SHA256SUMS').read_bytes()
    sums = [line.split('  ', 1) for line in sums_raw.decode().splitlines()]
    if any(len(row) != 2 for row in sums) or len(sums) != len(manifest) \
            or {name: sha for sha, name in sums} != {r['name']: r['sha256'] for r in manifest}:
        raise RuntimeError('Canceled local original checksums changed')
    for row in manifest:
        path = local / row['name']
        if path.is_symlink() or not path.is_file() or '..' in Path(row['name']).parts \
                or Path(row['name']).is_absolute() or '\\' in row['name']:
            raise RuntimeError('Unsafe canceled original member')
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or digest(raw) != row['sha256']:
            raise RuntimeError('Canceled local original bytes changed: ' + row['name'])
    result = json.loads((local / 'result.json').read_bytes())
    events = Counter(json.loads(line)['event'] for line in (local / 'tests.jsonl').read_bytes().splitlines())
    cancel = json.loads((R1 / 'superseded-cancellation-result.json').read_bytes())
    if result['head'] != R1_HEAD or result['tree'] != R1_TREE or result['passed'] is not False \
            or result['exit_code'] != -15 or events != Counter(start=1145, stop=1144) \
            or cancel['intentional_superseded_cancellation'] is not True or cancel['not_a_passing_gate'] is not True \
            or cancel['state_after']['Running'] is not False or cancel['state_after']['Pid'] != 0 \
            or cancel['state_after']['OOMKilled'] is not False or cancel['state_after']['ExitCode'] != 241:
        raise RuntimeError('Canceled local outcome/source changed')
    local_rows = {row['name']: row for row in manifest}
    local_rows.update({name: {'sha256': digest(raw), 'bytes': len(raw)}
                       for name, raw in (('manifest.json', manifest_raw), ('SHA256SUMS', sums_raw))})
    for name in ('result.json', 'manifest.json', 'SHA256SUMS', 'tests.jsonl', 'canonical-trace.jsonl',
                 'canonical.log', 'unittest-console.log', 'memory.jsonl', 'module-cleanup.jsonl', 'runner.py',
                 'observer/sitecustomize.py', 'observer/fixture_cleanup.py'):
        original(local, name, 'superseded-3a19/local-canonical/' + name,
                 sha=local_rows[name]['sha256'], size=local_rows[name]['bytes'])

    api_manifest = json.loads(original(base, 'prior-3a19/attempt-api-original-manifest.json'))
    if api_manifest['candidate'] != R1_HEAD or api_manifest['tree'] != R1_TREE:
        raise RuntimeError('Prior attempt API index source changed')
    expected = {42986949235: 'failure', 42986949262: 'cancelled'}
    if len(api_manifest['files']) != 2:
        raise RuntimeError('Prior attempt API population changed')
    for row in api_manifest['files']:
        raw = original(base / 'prior-3a19', row['name'], 'superseded-3a19/api/' + row['name'],
                       sha=row['sha256'], size=row['bytes'])
        record = json.loads(raw)
        if record['id'] not in expected or record['head_sha'] != R1_HEAD or record['run_attempt'] != 1 \
                or record['status'] != 'completed' or record['conclusion'] != expected[record['id']]:
            raise RuntimeError('Prior attempt API source/outcome changed')

    # This receipt is supplied separately by the release agent. An earlier
    # in-progress snapshot cannot certify the canceled hosted artifact's state.
    host = json.loads(original(base, 'prior-3a19/hosted-canonical-cancelled.json'))
    receipt = json.loads(original(base, 'prior-3a19/hosted-canonical-cancelled-receipt.json'))
    transfer = json.loads(original(base, 'prior-3a19/hosted-canonical-cancelled-log-transfer.json'))
    job_source = json.loads(original(base, 'prior-3a19/hosted-canonical-cancelled-job-source.json'))
    console = original(base, 'prior-3a19/hosted-canonical-cancelled-console.log',
                       sha=transfer['original_sha256'], size=transfer['original_bytes'])
    if transfer['candidate'] != R1_HEAD or transfer['tree'] != R1_TREE \
            or transfer['scope'] != 'prior-attempts-only' or transfer['job_id'] != 130410273395 \
            or transfer['utf8_bytes'] != len(console) \
            or transfer['utf16_length'] != len(console.decode().encode('utf-16-le')) // 2 \
            or job_source['head_sha'] != R1_HEAD or job_source['run_id'] != 42986949262 \
            or job_source['id'] != 130410273395 or job_source['conclusion'] != 'cancelled':
        raise RuntimeError('Canceled hosted decoded console source/transfer changed')
    parts = []
    if len(transfer['parts']) != transfer['part_count']:
        raise RuntimeError('Canceled hosted console parts incomplete')
    for row in transfer['parts']:
        name = row['name']
        if Path(name).name != name or '\\' in name:
            raise RuntimeError('Unsafe original console part name')
        path = base / 'prior-3a19/hosted-canonical-cancelled-console.parts' / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Canceled hosted console part unavailable')
        raw = path.read_bytes()
        if len(raw) != row['bytes'] or digest(raw) != row['sha256']:
            raise RuntimeError('Canceled hosted console original part changed')
        parts.append(raw)
    if b''.join(parts) != console:
        raise RuntimeError('Canceled hosted console original join differs')
    for name in ('hosted-canonical-cancelled-run-api.json', 'hosted-canonical-cancelled-artifacts-api.json'):
        original(base, 'prior-3a19/' + name)
    if host['candidate'] != R1_HEAD or host['tree'] != R1_TREE \
            or host['run']['id'] != 42986949262 or host['run']['head_sha'] != R1_HEAD \
            or host['run']['status'] != 'completed' or host['run']['conclusion'] != 'cancelled' \
            or receipt['candidate'] != R1_HEAD or receipt['tree'] != R1_TREE \
            or receipt['scope'] != 'prior-attempts-only' or receipt['run'] != 42986949262 \
            or receipt['job'] != 130410273395 or receipt['native_pass_guard_applied'] is not False \
            or receipt['final_source_acceptance'] is not False:
        raise RuntimeError('Canceled hosted canonical original association changed')
    if receipt['artifact_available'] is True:
        row = receipt['artifact']
        api_artifact = host.get('artifact') or {}
        workflow = api_artifact.get('workflow_run') or {}
        if api_artifact.get('id') != row['id'] or api_artifact.get('name') != row['name'] \
                or api_artifact.get('size_in_bytes') != row['bytes'] \
                or api_artifact.get('digest') != 'sha256:' + row['sha256'] \
                or workflow.get('id') != 42986949262 or workflow.get('head_sha') != R1_HEAD:
            raise RuntimeError('Canceled hosted artifact API identity/digest changed')
        archive = base / 'prior-3a19/hosted-canonical-cancelled-original.zip'
        if receipt['original_bytes_verified'] is not True or receipt['crc_verified'] is not True:
            raise RuntimeError('Canceled hosted artifact lacks original integrity verification')
        guards.verify_zip(archive)
        original(base, 'prior-3a19/hosted-canonical-cancelled-original.zip',
                 sha=row['sha256'], size=row['bytes'])
        with zipfile.ZipFile(archive) as native:
            native_names = set(native.namelist())
            native_events = Counter(json.loads(line)['event'] for line in native.read('tests.jsonl').splitlines())
            if dict(native_events) != receipt['test_events'] or native_events != Counter(start=2500, stop=2499) \
                    or {'result.json', 'manifest.json'} & native_names \
                    or receipt['manifest_verified_if_present'] is not None or receipt['native_result'] is not None:
                raise RuntimeError('Canceled hosted partial population/outcome changed')
    elif receipt['artifact_available'] is not False:
        raise RuntimeError('Canceled hosted artifact availability must be explicit')
    elif host.get('artifact') is not None or (base / 'prior-3a19/hosted-canonical-cancelled-original.zip').exists():
        raise RuntimeError('Cannot label a retained available canceled artifact as unavailable')

    proof = R1 / 'product-failure-audit/resize-proof'
    for name in ('baseline-probe-result.json', 'baseline-probe-source.json', 'baseline-probe-original.log',
                 'baseline-probe-exit.json', 'corrected-original-test-source.json',
                 'corrected-original-test-original.log', 'corrected-original-test-exit.json',
                 'attempt1-import-baseline-probe-original.log', 'attempt1-import-baseline-probe-exit.json',
                 'fixture-candidate.patch', 'commit-provenance.json', 'commit-provenance.sha256', 'probe_runner.py'):
        original(proof, name, 'viewport-proof/' + name)
    provenance = json.loads((proof / 'commit-provenance.json').read_bytes())
    baseline = json.loads((proof / 'baseline-probe-result.json').read_bytes())
    if provenance['commit'] != R2_HEAD or provenance['tree'] != R2_TREE \
            or provenance['tested_bytes_match_commit'] is not True or provenance['native_test_passed'] is not True \
            or provenance['original_height_assertion_unchanged'] != 44 or provenance['negative_30px_control_rejected'] is not True \
            or baseline['source']['head'] != R1_HEAD or baseline['immediate']['old']['connected'] is not False \
            or baseline['settled']['current']['height'] != 44 \
            or baseline['negative_control']['original_44px_assertion_failed'] is not True:
        raise RuntimeError('Viewport causal/provenance receipt changed')
    for width in (320, 375, 390, 1280):
        for suffix in ('.json', '.png'):
            original(proof / 'corrected-original-test', 'phone-' + str(width) + suffix,
                     'viewport-proof/corrected-original-test/phone-' + str(width) + suffix)
    original(proof / 'corrected-original-test', 'exact-native-search.json',
             'viewport-proof/corrected-original-test/exact-native-search.json')
    for name in ('baseline-container-inspect.json', 'corrected-container-inspect.json',
                 'attempt1-import-baseline-container-inspect.json'):
        raw = (proof / name).read_bytes()
        config = json.loads(raw)
        if not isinstance(config, list) or len(config) != 1 or config[0]['State'].get('Error'):
            raise RuntimeError('Container source needs manual sanitization review')
        config = config[0]
        selected = {'Id': config['Id'], 'Image': config['Image'], 'State': config['State'],
                    'limits': {k: config['HostConfig'][k] for k in ('Memory', 'MemorySwap', 'NanoCpus', 'NetworkMode')}}
        derived('viewport-proof/' + name.replace('-inspect.json', '-sanitized.json'), {
            'derived': True, 'original_file_sha256': digest(raw), 'selected_metadata': selected,
            'selected_metadata_sha256': digest(encoded(selected)),
            'omitted': 'Full Config/Env, Args, mounts, paths, network/security settings and remaining Docker configuration.',
            'reason': 'Publish only bounded state/resource receipt; full original stays local and is not claimed byte-identical to this derived file.',
        }, 'Explicitly derived sanitized Docker metadata from original ' + str(proof / name))

    public_manifest = (REVIEW / 'publication-manifest.json').read_bytes()
    if digest(public_manifest) != REVIEW_MANIFEST_SHA:
        raise RuntimeError('Immutable historical review manifest changed')
    public = {r['name']: r for r in json.loads(public_manifest)['files']}
    link_names = [name for name in sorted(public) if name.startswith('prior-author-focused/') and name.endswith('.log')]
    links = []
    for name in link_names:
        row = public[name]
        links.append({**row, 'commit': REVIEW_COMMIT,
                      'url': 'https://github.com/Richarddavis47/dtos/blob/' + REVIEW_COMMIT + '/' + REVIEW_PREFIX + '/' + name})
    original(REVIEW, 'publication-manifest.json', 'review-3a19/publication-manifest.json', sha=REVIEW_MANIFEST_SHA)
    original(R1, 'review-publication-receipt.json', 'review-3a19/publication-receipt.json', sha=REVIEW_RECEIPT_SHA)
    for name in ('ANALYSIS.md', 'summary.json', 'result.json', 'events.json', 'observer.py', 'run.py',
                 'projection_audit_precollect.py', 'projection_audit_negative.py', 'original-console.log',
                 'container.json', 'cleanup-state.json', 'sha256.json'):
        row = public['gc-analysis/' + name]
        original(REVIEW / 'gc-analysis', name, 'gc-proof/' + name, sha=row['sha256'], size=row['bytes'])
    for name in ('focused-native-initial-verifier-original.log', 'focused-native-arrow-corrected-verifier-original.log',
                 'focused-native-arrow-corrected-verifier-prefix.json', 'focused-native-label-corrected-integrity.json'):
        original(R1, name, 'reader-failures/' + name)
    original(base, 'native-prefix-invocation-attempt.json', 'reader-failures/r2-native-prefix-invocation-attempt.json')
    original(base, 'pr-description-graphql-failure.json', 'minor-tooling/r2-pr-description-graphql-failure.json')
    original(base, 'patch-packaging-controls.json', 'minor-tooling/r2-patch-packaging-controls.json')
    derived('PRIOR_SUPPLEMENT_INDEX.json', {
        'scope': 'prior-attempts-only', 'historical_source': {'candidate': R1_HEAD, 'tree': R1_TREE},
        'product': {'run': 42986949235, 'job': 130410273016, 'status': 'failed', 'tests': 687, 'errors': 1,
                    'decoded_utf8_log_sha256': PRODUCT_SHA, 'native_failed_zip_sha256': PRODUCT_ZIP_SHA,
                    'native_success_guard_applied': False},
        'local_canonical': {'status': 'CANCELLED_SUPERSEDED_INCOMPLETE', 'events': dict(events),
                            'manifest_members_verified_locally': 138, 'validator_exit': -15, 'container_exit': 241,
                            'original_manifest_payloads_all_embedded': False,
                            'omitted': 'Only requested core originals are embedded. Other original partial captures remain retained locally; the different hosted canceled ZIP is not their substitute.',
                            'complete_canonical_pass': False},
        'hosted_canonical': {'status': 'cancelled', 'artifact_available': receipt['artifact_available'],
                             'test_events': receipt.get('test_events'),
                             'original_decoded_console_sha256': transfer['original_sha256'],
                             'native_success_guard_applied': False},
        'viewport_proof': 'Original dirty3a19 corrected test bytes remain dirty in their record; commit-provenance binds them to cleanb602 without changing the historical head.',
        'current_source_minor_tooling': {'candidate': R2_HEAD, 'tree': R2_TREE,
                                        'scope': 'PR CLI query compatibility and expected patch-integrity negative controls only; not application validation failure or final release acceptance.'},
        'historical_review': {'commit': REVIEW_COMMIT, 'manifest_sha256': REVIEW_MANIFEST_SHA,
                              'readback_receipt_sha256': REVIEW_RECEIPT_SHA, 'fresh_remote_readback': False,
                              'linked_author_failure_logs': links},
        'files': rows,
    }, 'New historical index; no failed/canceled or modeled result becomes final-source acceptance')
    return {'candidate': R1_HEAD, 'tree': R1_TREE, 'scope': 'prior-attempts-only',
            'product_status': 'failed', 'local_canonical_status': 'CANCELLED_SUPERSEDED_INCOMPLETE',
            'hosted_canonical_status': 'cancelled', 'hosted_artifact_available': receipt['artifact_available'],
            'supplement_index': 'PRIOR_SUPPLEMENT_INDEX.json'}
