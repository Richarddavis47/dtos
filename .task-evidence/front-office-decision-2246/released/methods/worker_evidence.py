"""Explicit original worker-method evidence selection; no top-level I/O or reruns.

The caller supplies the unchanged common.verify_worker_setup_controls receipt.
Only selected original files and one clearly DERIVED container receipt are
returned. The full Docker inspection and fixture/partial-result bodies stay out.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/workspace/2246-granite-activation/expansion/worker-setup-reconciliation')
PRIMARY = ('result.json', 'summary.json', 'source-predicate-proof.json', 'commit-provenance.json', 'SHA256SUMS')
ORIGINALS = PRIMARY + (
    'protocol.py', 'baseline-original.py', 'projection_worker_old_placement.py',
    'projection_worker_foreground_negative.py', 'original-console.log',
    'actual-audit-module-original.log', 'invocation.json', 'exit.json',
    'ruff-original.log', 'compile-original.log', 'whitespace-original.log', 'candidate.patch',
)
DERIVED = 'container-selected-derived.json'
MANIFEST = 'worker-evidence-manifest.json'
BYTE_LIMIT = 150000
STATE_FIELDS = ('Status', 'Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead', 'Pid', 'ExitCode', 'StartedAt', 'FinishedAt')
LIMIT_FIELDS = ('Memory', 'MemorySwap', 'NanoCpus', 'NetworkMode')
SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
SIGNED = re.compile(rb'https?://[^\s"<>]*[?&](?:sig|signature|token|access_token|X-Amz-Signature|X-Amz-Credential|X-Goog-Signature|X-Goog-Credential)=', re.I)


def require(condition, message):
    if not condition:
        raise RuntimeError('Worker evidence selection: ' + message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def read_original(name, limit=BYTE_LIMIT):
    require(name in ORIGINALS or name in {'commit-provenance.sha256', 'container-inspect-running-original.json'},
            'file is outside the explicit read allowlist')
    path = ROOT / name
    require(path.is_file() and not path.is_symlink() and not any(parent.is_symlink() for parent in path.parents),
            'missing or symlink original: ' + name)
    require(path.stat().st_size <= limit, 'unexpected original size: ' + name)
    return path.read_bytes()


def verify_originals(read, authority):
    require(authority['passed'] is True and authority['originals_path'] == str(ROOT)
            and set(authority['original_sha256']) == set(PRIMARY), 'unchanged primary control authority required')
    raw = {name: read(name) for name in ORIGINALS}
    sums_rows = [line.split('  ', 1) for line in raw['SHA256SUMS'].decode('utf-8').splitlines()]
    require(all(len(row) == 2 and re.fullmatch(r'[a-f0-9]{64}', row[0]) for row in sums_rows), 'malformed original checksums')
    sums = {name: checksum for checksum, name in sums_rows}
    require(len(sums) == len(sums_rows), 'duplicate original checksum names')
    for name, data in raw.items():
        data.decode('utf-8')
        require(not SECRET.search(data) and not SIGNED.search(data), 'credential/signed URL shape in selected original: ' + name)
        if name in authority['original_sha256']:
            require(digest(data) == authority['original_sha256'][name], 'primary original changed: ' + name)
        if name in sums:
            require(digest(data) == sums[name], 'original checksum disagreement: ' + name)
        else:
            require(name in {'SHA256SUMS', 'commit-provenance.json'}, 'authorized original lacks a checksum: ' + name)
    bridge = json.loads(raw['commit-provenance.json'])
    require(bridge['commit'] == authority['candidate'] and bridge['tree'] == authority['tree']
            and bridge['test_file_sha256'] == authority['candidate_file_sha256'], 'committed-source bridge disagreement')
    require(json.loads(raw['result.json'])['source'] == authority['historical_execution_source'],
            'historical dirty execution identity changed')
    summary = json.loads(raw['summary.json'])
    require(json.loads(raw['exit.json']) == {'exit_code': 0}
            and summary['resources']['exit_code'] == 0 and summary['resources']['auto_removed_after_exit'] is True,
            'original completion/auto-removal record changed')
    return raw, sums, summary


def verify_worker_setup_evidence(read, authority, names, method_raw):
    """Verify selected archive/public bytes without reading the private inspection."""
    require(set(names) == set(ORIGINALS) | {DERIVED, MANIFEST}, 'selected evidence population changed')
    originals, sums, summary = verify_originals(read, authority)
    manifest = json.loads(read(MANIFEST))
    require(manifest['schema'] == 'dtos-worker-method-evidence-v1'
            and manifest['candidate'] == authority['candidate'] and manifest['tree'] == authority['tree']
            and manifest['historical_execution_source'] == authority['historical_execution_source']
            and manifest['method_sha256'] == digest(method_raw), 'selected manifest identity/method mismatch')
    rows = {row['name']: row for row in manifest['files']}
    require(len(rows) == len(manifest['files']) and set(rows) == set(ORIGINALS) | {DERIVED}, 'selected manifest population mismatch')
    for name, row in rows.items():
        raw = read(name)
        require(row['bytes'] == len(raw) and row['sha256'] == digest(raw), 'selected payload hash mismatch: ' + name)
        require(row['kind'] == ('derived' if name == DERIVED else 'original'), 'original/derived provenance mislabeled')
    require(manifest['payload_bytes'] == sum(row['bytes'] for row in rows.values())
            and sum(len(read(name)) for name in names) <= BYTE_LIMIT, 'selected evidence byte bound exceeded')
    selected = json.loads(read(DERIVED))
    require(set(selected) == {'kind', 'derived', 'original', 'selected_metadata', 'completion_from_original_records', 'omitted', 'scope'}
            and selected['kind'] == 'DERIVED_SELECTED_DOCKER_METADATA' and selected['derived'] is True,
            'derived receipt must be clearly labeled and bounded')
    require(selected['original'] == {'name': 'container-inspect-running-original.json',
            'sha256': sums['container-inspect-running-original.json'], 'included': False,
            'capture': 'Original running-container inspection, not a post-exit inspection'}, 'derived original inspection provenance mismatch')
    metadata = selected['selected_metadata']
    require(set(metadata) == {'Id', 'Image', 'State', 'User', 'HostConfig'}
            and set(metadata['State']) == set(STATE_FIELDS) and set(metadata['HostConfig']) == set(LIMIT_FIELDS),
            'derived metadata escaped the explicit selected-field allowlist')
    resources = summary['resources']
    require(isinstance(metadata['Id'], str) and re.fullmatch(r'[a-f0-9]{64}', metadata['Id'])
            and metadata['Image'] == resources['runtime_image'] and metadata['User'] == resources['user']
            and metadata['State']['Status'] == 'running' and metadata['State']['Running'] is True
            and metadata['State']['OOMKilled'] is False
            and metadata['HostConfig'] == {'Memory': resources['memory_bytes'],
                'MemorySwap': resources['total_memory_and_swap_bytes'], 'NanoCpus': int(resources['cpus'] * 1000000000),
                'NetworkMode': resources['network']}, 'derived selected resource/capture fields disagree with original summary')
    require(selected['completion_from_original_records'] == {'exit_code': 0, 'auto_removed_after_exit': True,
            'sources': {'exit.json': digest(originals['exit.json']), 'summary.json': digest(originals['summary.json'])}},
            'completion evidence must remain separate from running inspection')
    require(selected['omitted'] == 'Full Config including Env (except selected User), Args, mounts, network configuration, Health/log/error bodies and all other inspection fields.'
            and 'not byte-identical to the full original inspection' in selected['scope'], 'derived omissions/authority qualification missing')
    return {'passed': True, 'candidate': authority['candidate'], 'tree': authority['tree'],
            'files': len(names), 'bytes': sum(len(read(name)) for name in names),
            'manifest_sha256': digest(read(MANIFEST)), 'original_files': len(ORIGINALS),
            'scope': 'Selected original-method/log byte integrity and explicitly derived metadata only; historical dirty execution and expected negative controls retain their original qualifications.'}


def collect_worker_setup_evidence(authority):
    """Return deterministic safe bytes; never write files or execute any command."""
    originals, sums, summary = verify_originals(read_original, authority)
    bridge_sums = read_original('commit-provenance.sha256').decode('utf-8').splitlines()
    require(bridge_sums == [authority['original_sha256']['commit-provenance.json'] + '  commit-provenance.json'],
            'separate original commit-provenance checksum disagrees with frozen authority')
    inspection_raw = read_original('container-inspect-running-original.json', limit=32768)
    require(digest(inspection_raw) == sums['container-inspect-running-original.json'], 'private inspection raw checksum disagreement')
    inspection = json.loads(inspection_raw)
    require(isinstance(inspection, list) and len(inspection) == 1, 'unexpected original inspection population')
    captured = inspection[0]
    selected = {'Id': captured['Id'], 'Image': captured['Image'],
                'State': {key: captured['State'][key] for key in STATE_FIELDS},
                'User': captured['Config']['User'], 'HostConfig': {key: captured['HostConfig'][key] for key in LIMIT_FIELDS}}
    derived = {'kind': 'DERIVED_SELECTED_DOCKER_METADATA', 'derived': True,
        'original': {'name': 'container-inspect-running-original.json', 'sha256': digest(inspection_raw), 'included': False,
                     'capture': 'Original running-container inspection, not a post-exit inspection'},
        'selected_metadata': selected,
        'completion_from_original_records': {'exit_code': json.loads(originals['exit.json'])['exit_code'],
            'auto_removed_after_exit': summary['resources']['auto_removed_after_exit'],
            'sources': {'exit.json': digest(originals['exit.json']), 'summary.json': digest(originals['summary.json'])}},
        'omitted': 'Full Config including Env (except selected User), Args, mounts, network configuration, Health/log/error bodies and all other inspection fields.',
        'scope': 'New DERIVED selected metadata, not byte-identical to the full original inspection. Running-state capture and later completion/auto-removal records are distinct. No fresh Docker observation, rerun, historical GC-duration attribution or new full-suite acceptance is asserted.'}
    payload = {**originals, DERIVED: encoded(derived)}
    manifest = {'schema': 'dtos-worker-method-evidence-v1', 'candidate': authority['candidate'], 'tree': authority['tree'],
        'historical_execution_source': authority['historical_execution_source'], 'method_sha256': digest(Path(__file__).read_bytes()),
        'scope': 'Original protocol/source/command/log evidence, including expected old-placement and120ms negative assertions. Empty compilation/whitespace logs stay empty originals; no separate successful exits are invented. Full private inspection and partial-result/fixture bodies are excluded.',
        'separate_commit_provenance_checksum_verified': True,
        'files': [{'name': name, 'bytes': len(raw), 'sha256': digest(raw), 'kind': 'derived' if name == DERIVED else 'original'}
                  for name, raw in sorted(payload.items())], 'payload_bytes': sum(len(raw) for raw in payload.values())}
    payload[MANIFEST] = encoded(manifest)
    verify_worker_setup_evidence(payload.__getitem__, authority, payload.keys(), Path(__file__).read_bytes())
    return payload
