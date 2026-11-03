"""Read-only Actions evidence publisher. Never merges, tags or deploys."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ALLOWED = {'.github/workflows/canonical-release-recovery.yml',
           '.github/evidence-supplements/2225-corrigendum.json',
           '.github/evidence-supplements/2225-corrigendum.zip',
           '.github/evidence-supplements/verify_2225.py',
           '.github/evidence-supplements/test_verify_2225.py'}
TOKEN = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def api(path):
    return json.loads(command('gh', 'api', path))


def verify_archive(path, expected):
    require(digest(path) == expected, 'Supplement archive checksum mismatch')
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive path')
        require(sum(i.file_size for i in z.infolist()) < 64 * 1024**2, 'Archive too large')
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            require(not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename, 'Unsafe archive path')
            require((info.external_attr >> 16) & 0o170000 != 0o120000, 'Archive symlink')
            if p.suffix in {'.json', '.md', '.py', '.txt', '.log'}:
                require(not TOKEN.search(z.read(info)), 'Credential-shaped material in evidence')
        require(z.testzip() is None, 'Archive CRC mismatch')
        rows = json.loads(z.read('MANIFEST.json'))
        listed = set()
        for row in rows:
            require(row['name'] not in listed, 'Duplicate manifest row')
            listed.add(row['name'])
            data = z.read(row['name'])
            require(len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], 'Payload checksum mismatch')
        require(set(names) == listed | {'MANIFEST.json', 'SHA256SUMS'}, 'Unmanifested evidence')
        sums = dict(line.split('  ', 1)[::-1] for line in z.read('SHA256SUMS').decode().splitlines())
        require(set(sums) == listed | {'MANIFEST.json'}, 'Checksum population mismatch')
        for name, sha in sums.items():
            require(hashlib.sha256(z.read(name)).hexdigest() == sha, 'Checksum list mismatch')
    return len(rows)


def main():
    plan = json.loads(Path('.github/evidence-supplements/2225-corrigendum.json').read_text())
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'Actions required')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Explicit dispatch required')
    require(os.environ.get('GITHUB_ACTOR') == plan['actor'], 'Wrong actor')
    require(os.environ.get('GITHUB_REPOSITORY') == plan['repository'], 'Wrong repository')
    require(os.environ.get('GITHUB_REF') == plan['publisher_ref'], 'Wrong ref')
    sha = os.environ['GITHUB_SHA']
    require(command('git', 'rev-parse', 'HEAD') == sha, 'Checkout mismatch')
    prefix = 'repos/' + plan['repository'] + '/'
    require(api(prefix + 'git/ref/heads/' + plan['publisher_ref'].removeprefix('refs/heads/'))['object']['sha'] == sha, 'Publisher advanced')
    changed = set(command('git', 'diff', '--name-only', plan['baseline'], sha).splitlines())
    require(changed <= ALLOWED, 'Application source changed')
    require(command('git', 'rev-parse', plan['baseline'] + '^{tree}') == plan['tree'], 'Application baseline mismatch')
    require(api(prefix + 'git/ref/heads/main')['object']['sha'] == plan['baseline'], 'Production source advanced')
    run = api(prefix + 'actions/runs/' + os.environ['GITHUB_RUN_ID'])
    require(run['head_sha'] == sha and run['event'] == 'workflow_dispatch'
            and run['path'] == '.github/workflows/canonical-release-recovery.yml', 'Untrusted workflow')
    release = api(prefix + 'releases/' + str(plan['original_release_id']))
    require(release['immutable'] is True and release['draft'] is False
            and release['tag_name'] == 'v' + plan['version']
            and release['target_commitish'] == plan['baseline'], 'Original release identity changed')
    assets = [a for a in release['assets'] if a['name'] == plan['original_archive_name']]
    require(len(assets) == 1 and assets[0]['digest'] == 'sha256:' + plan['original_archive_sha256'], 'Original attachment mismatch')
    path = Path(plan['supplement_file'])
    require(str(path) == '.github/evidence-supplements/2225-corrigendum.zip', 'Wrong supplement path')
    require(path.stat().st_size == plan['supplement_bytes'], 'Supplement byte count mismatch')
    population = verify_archive(path, plan['supplement_sha256'])
    output = Path('.validation/2225-corrigendum')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        subprocess.run(['gh', 'release', 'download', 'v' + plan['version'], '--repo', plan['repository'],
                        '--pattern', plan['original_archive_name'], '--dir', str(temp)], check=True)
        original = temp / plan['original_archive_name']
        require(digest(original) == plan['original_archive_sha256'], 'Original downloaded bytes changed')
        extracted = temp / 'supplement'
        with zipfile.ZipFile(path) as z:
            # Paths/symlinks/size/checksums were checked before extraction.
            z.extractall(extracted)
            corrections = json.loads(z.read('CORRECTIONS.json'))
            with zipfile.ZipFile(original) as old:
                require(old.testzip() is None, 'Original archive CRC mismatch')
                for row in corrections['records']:
                    data = old.read(row['original_member'])
                    require(hashlib.sha256(data).hexdigest() == row['original_member_sha256'], 'Original member identity mismatch')
                    member = 'original-records/' + PurePosixPath(row['original_member']).name
                    require(z.read(member) == data, 'Original historical bytes not preserved')
        with (output / 'metadata-tests.log').open('w') as log:
            subprocess.run([sys.executable, str(extracted / 'tests/test_metadata_integrity.py'), '-v'],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        for filename in ('cache-restoration-measurement.json', 'cache-restoration-dense-measurement.json'):
            report = json.loads((extracted / 'measurements' / filename).read_text())
            require(report['head'] == plan['baseline'] and report['tree'] == plan['tree'], 'Measurement source mismatch')
            require(report['enforced_limit'] == 2147483648 and report['passed'] and report['complete']
                    and report['scratch_exists_after'] is False and report['source_unchanged'], 'Constrained execution incomplete')
            require(not report['final']['cgroup_memory_events'].get('oom_kill'), 'Measurement OOM')
            outcomes = [p['outcome'] for p in report['phases']]
            require(outcomes[0] == 'restored' and 'deferred' in outcomes and outcomes[-1] == 'restored', 'Completion/deferral/recovery missing')
        worker = json.loads((extracted / 'measurements/league-entry-proof.json').read_text())
        require(worker['head'] == plan['baseline'] and worker['passed'] and worker['complete']
                and worker['worker_reaped'] and worker['one_qb_k_def_http_evaluation'] == 'passed', 'Worker or one-QB proof incomplete')
    # Only admitted evidence is copied into the artifact output. No release write API exists here.
    shutil.copyfile(path, output / '2225-corrigendum.zip')
    (output / 'SHA256SUMS').write_text(plan['supplement_sha256'] + '  2225-corrigendum.zip\n')
    (output / 'ATTESTATION.json').write_text(json.dumps(dict(passed=True, publisher=sha,
        application_commit=plan['baseline'], application_tree=plan['tree'], application_source_changed=False,
        original_release_unchanged=True, original_archive_sha256=plan['original_archive_sha256'],
        supplement_sha256=plan['supplement_sha256'], verified_payloads=population,
        scope='Evidence supplement only; no application merge/tag/release mutation/deployment.'), indent=2))


if __name__ == '__main__':
    main()
