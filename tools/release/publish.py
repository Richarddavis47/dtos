"""Two-phase Actions publisher. Never merges PRs or updates a branch ref."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile

ALLOWED_PATHS = {
    '.github/workflows/canonical-release-recovery.yml',
    '.github/release-plans/2223.json', '.github/release-plans/2223-recovery.zip',
    '.github/release-plans/README.md', 'tools/release/__init__.py',
    'tools/release/publish.py', 'tests/test_release_publisher.py',
}
TOKEN = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def api(path, body=None):
    args = ['gh', 'api', path]
    if body is None:
        return json.loads(command(*args))
    # A structured input file preserves literal strings and never exposes GH_TOKEN.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as stream:
        json.dump(body, stream)
        stream.flush()
        return json.loads(command(*args, '--method', 'POST' if path.endswith(('/tags', '/refs')) else 'PATCH', '--input', stream.name))


def download(path, destination):
    args = ['gh', 'api', path]
    if path.endswith('/logs'):
        # Match the established publisher: retain ANSI bytes in a file, never
        # render downloaded logs directly in the terminal.
        args.append('--allow-escape-sequences')
    with destination.open('wb') as stream:
        subprocess.run(args, stdout=stream, check=True)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def verify_zip(path):
    """Reject paths/symlinks/duplicates before reading any artifact member."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive member')
        require(sum(x.file_size for x in archive.infolist()) < 512 * 1024**2, 'Oversized archive')
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            require(not name.is_absolute() and '..' not in name.parts and '\\' not in item.filename, 'Unsafe archive member')
            require((item.external_attr >> 16) & 0o170000 != 0o120000, 'Archive symlink')
            if not item.is_dir() and name.suffix in {'.log', '.json', '.jsonl', '.md', '.txt', '.py', '.html', '.js'}:
                require(not TOKEN.search(archive.read(item)), 'Credential-shaped material in evidence; manual review required')
        require(archive.testzip() is None, 'Archive CRC mismatch')


def verify_canonical(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('result.json'))
        require(result['head'] == plan['candidate'] and result['tree'] == plan['tree'], 'Canonical source mismatch')
        require(result['passed'] is True and result['exit_code'] == 0, 'Canonical did not pass')
        require(str(result.get('python', '')).split(' ', 1)[0] == plan['python_version'], 'Canonical Python runtime mismatch')
        require(result['cgroup_limit'] == 2147483648 and result['cpus'] == 2 and result['network'] == 'none', 'Canonical resource contract mismatch')
        require(not result['final_memory']['cgroup_memory_events'].get('oom_kill'), 'Canonical OOM event')
        manifest = json.loads(archive.read('manifest.json'))
        require(len(manifest) == plan['canonical_entries'], 'Canonical manifest population mismatch')
        names = set()
        for entry in manifest:
            require(entry['name'] not in names, 'Duplicate canonical manifest row')
            names.add(entry['name'])
            data = archive.read(entry['name'])
            require(len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'], 'Canonical payload checksum mismatch')
        events = Counter(json.loads(line)['event'] for line in archive.read('tests.jsonl').splitlines())
        require(events['start'] == events['stop'] == plan['canonical_tests'] and not any(events[x] for x in ('failure', 'error', 'skip')), 'Incomplete/failed canonical tests')
        trace = [json.loads(line) for line in archive.read('canonical-trace.jsonl').splitlines()]
        require(any(x.get('event') == 'validator_final_summary' and x.get('gates') == 10 for x in trace), 'Ten-gate final summary missing')
        completed = [x for x in trace if x.get('event') == 'validation_child_completed']
        require(len(completed) == 10 and all(x['return_code'] == 0 for x in completed), 'Incomplete canonical gate execution')
        return result


def verify_trade_resource(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('result.json'))
        require(result['head'] == plan['candidate'] and result['tree'] == plan['tree'], 'Trade resource source mismatch')
        require(result.get('passed') is True and result.get('complete') is True and result.get('working_tree_clean') is True, 'Trade resource acceptance incomplete or dirty')
        require(result.get('cleanup', {}).get('harness_scratch_exists_after') is False and result.get('cleanup', {}).get('trade_lease_available') is True, 'Trade scratch/lease cleanup missing')
        require(result['kernel_peak'] <= 2147483648 and result['one_qb_http_evaluation']['passed'] is True, 'Trade enforced memory or one-QB control failed')
        require(len(result['operations']) >= 2 and all(x['full_evaluations'] == 180 for x in result['operations']), 'Real Trade execution missing')
        require(len({x['business_digest'] for x in result['operations']}) == 1, 'Trade recovery changed intelligence')
        require(result['actual_cancel']['evaluations_started'] > 0 and result['file_cache_recovery']['completed_evaluations'] == 180 and result['file_cache_recovery']['content_still_valid'] is True, 'Trade cleanup/reclaim evidence missing')
        require(result['states'] and all(x['cgroup_limit_bytes'] == 2147483648 and not x['cgroup_memory_events'].get('oom') and not x['cgroup_memory_events'].get('oom_kill') for x in result['states']), 'Trade container or OOM evidence failed')
        require(result['liveness'] and all(type(x.get('server_duration_ms')) in (int, float) and x['server_duration_ms'] == x.get('milliseconds') and x['server_duration_ms'] < 500 and type(x.get('client_elapsed_ms')) in (int, float) and x['client_elapsed_ms'] >= 0 for x in result['liveness']), 'Trade overlapping server liveness failed')
        for line in archive.read('SHA256SUMS').decode().splitlines():
            expected, name = line.split('  ', 1)
            require(name in {'result.json', 'raw.log', 'preparation.log'} and hashlib.sha256(archive.read(name)).hexdigest() == expected, 'Trade artifact checksum mismatch')
        require({line.split('  ', 1)[1] for line in archive.read('SHA256SUMS').decode().splitlines()} == {'result.json', 'raw.log', 'preparation.log'}, 'Trade attachment manifest incomplete')
    return result


def verify_local_recovery(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('local-canonical/result.json'))
        require(result['head'] == plan['candidate'] and result['tree'] == plan['tree'], 'Local canonical source mismatch')
        require(result['passed'] is True and result['exit_code'] == 0 and result['cgroup_limit'] == 2147483648 and result['cpus'] == 2 and result['network'] == 'none', 'Local canonical acceptance missing')
        require(str(result.get('python', '')).split(' ', 1)[0] == plan['python_version'], 'Local canonical Python runtime mismatch')
        require(not result['final_memory']['cgroup_memory_events'].get('oom_kill'), 'Local canonical OOM')
        events = Counter(json.loads(line)['event'] for line in archive.read('local-canonical/tests.jsonl').splitlines())
        require(events['start'] == events['stop'] == plan['canonical_tests'] and not any(events[x] for x in ('failure','error','skip')), 'Local regression incomplete')
        trace = [json.loads(line) for line in archive.read('local-canonical/canonical-trace.jsonl').splitlines()]
        completed = [x for x in trace if x.get('event') == 'validation_child_completed']
        require(len(completed) == 10 and all(x['return_code'] == 0 for x in completed) and any(x.get('event') == 'validator_final_summary' and x.get('gates') == 10 for x in trace), 'Local canonical gates incomplete')
    return result


def verify_context(plan, operation):
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'Publisher requires GitHub Actions')
    require(os.environ.get('GITHUB_REPOSITORY') == plan['repository'], 'Wrong repository')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Only explicit dispatch is authorized')
    require(os.environ.get('GITHUB_ACTOR') == plan['actor'], 'Unapproved dispatch actor')
    require(os.environ.get('GITHUB_REF') == plan['publisher_ref'], 'Unapproved publisher ref')
    sha = os.environ['GITHUB_SHA']
    require(command('git', 'rev-parse', 'HEAD') == sha, 'Publisher checkout mismatch')
    repo = 'repos/' + plan['repository']
    ref = api(repo + '/git/ref/heads/' + plan['publisher_ref'].removeprefix('refs/heads/'))
    require(ref['object']['sha'] == sha, 'Publisher ref advanced')
    changed = set(command('git', 'diff', '--name-only', plan['baseline'], sha).splitlines())
    require(changed <= ALLOWED_PATHS, 'Publisher contains application changes')
    run = api(repo + '/actions/runs/' + os.environ['GITHUB_RUN_ID'])
    require(run['head_sha'] == sha and run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/canonical-release-recovery.yml', 'Untrusted publisher run')
    pr = api(repo + '/pulls/' + str(plan['pr']))
    require(pr['base']['ref'] == 'main' and pr['base']['repo']['full_name'] == plan['repository'], 'Wrong PR base')
    require(pr['head']['repo']['full_name'] == plan['repository'] and pr['head']['sha'] == plan['candidate'] and pr['head']['ref'] == plan['source_branch'], 'Candidate PR changed')
    main = api(repo + '/git/ref/heads/main')['object']['sha']
    if operation == 'publish':
        require(pr['merged'] and pr['merged_at'] and pr['merge_commit_sha'] == main, 'Publication requires the approved PR merged at current main')
    else:
        require(not pr['merged'] and pr['state'] == 'open' and main == plan['baseline'], 'Preparation requires unchanged baseline and open candidate')
    subprocess.run(['git', 'fetch', 'origin', 'refs/pull/' + str(plan['pr']) + '/head', 'main'], check=True)
    require(command('git', 'rev-parse', plan['candidate'] + '^{tree}') == plan['tree'], 'Candidate tree mismatch')
    if operation == 'publish':
        require(command('git', 'rev-parse', main + '^{tree}') == plan['tree'], 'Merged application differs from validated source')
    source = ast.parse(command('git', 'show', plan['candidate'] + ':app_metadata.py'))
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in source.body
                 if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in {'VERSION', 'BUILD_NUMBER'}}
    require(constants == {'VERSION': plan['version'], 'BUILD_NUMBER': plan['build']}, 'Version/build mismatch')
    previous = api(repo + '/releases/tags/' + plan['prior_immutable_tag'])
    require(previous['immutable'] is True and previous['draft'] is False, 'Established immutable policy not verified')
    return pr, main


def verify_runs(plan):
    repo = 'repos/' + plan['repository']
    checks = api(repo + '/commits/' + plan['candidate'] + '/check-runs?filter=latest&per_page=100')['check_runs']
    for name in [n for run in plan['runs'] for n in run['jobs']]:
        matching = [x for x in checks if x['name'] == name]
        require(matching and all(x['head_sha'] == plan['candidate'] and x['status'] == 'completed' and x['conclusion'] == 'success' and x['app']['slug'] == 'github-actions' for x in matching), 'Latest required check not successful: ' + name)
    records = []
    product_job = None
    for expected in plan['runs']:
        run = api(repo + '/actions/runs/' + str(expected['id']))
        require(run['head_sha'] == plan['candidate'] and run['head_repository']['full_name'] == plan['repository'], 'Validation run source mismatch')
        require(run['event'] == 'pull_request' and run['path'] == expected['path'] and run['name'] == expected['name'], 'Wrong validation workflow')
        require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Validation workflow not successful')
        jobs = api(repo + '/actions/runs/' + str(expected['id']) + '/jobs?per_page=100')['jobs']
        for name in expected['jobs']:
            found = [x for x in jobs if x['name'] == name]
            require(len(found) == 1 and found[0]['status'] == 'completed' and found[0]['conclusion'] == 'success', 'Required job not successful: ' + name)
            records.append({'id': found[0]['id'], 'name': name, 'run': expected['id'], 'conclusion': 'success'})
            if name == 'product-browser':
                product_job = found[0]['id']
    require(len(records) == 12 and product_job, 'Required gate population mismatch')
    return records, product_job


def make_zip(path, files):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    verify_zip(path)


def collect(plan, root):
    repo = 'repos/' + plan['repository']
    assets = root / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    records, product_job = verify_runs(plan)
    canonical = None
    for expected in plan['artifacts']:
        metadata = api(repo + '/actions/artifacts/' + str(expected['id']))
        require(not metadata['expired'] and metadata['name'] == expected['name'], 'Artifact unavailable or renamed')
        require(metadata['workflow_run']['id'] == expected['run'] and metadata['workflow_run']['head_sha'] == plan['candidate'], 'Artifact run mismatch')
        require(metadata['digest'] == 'sha256:' + expected['sha256'], 'Artifact API digest mismatch')
        path = assets / expected['file']
        download(repo + '/actions/artifacts/' + str(expected['id']) + '/zip', path)
        require(digest(path) == expected['sha256'] and path.stat().st_size == metadata['size_in_bytes'], 'Original artifact checksum mismatch')
        verify_zip(path)
        if expected['file'] == 'canonical-original.zip':
            canonical = verify_canonical(path, plan)
        if expected['file'] == 'trade-resource-original.zip':
            verify_trade_resource(path, plan)
        if expected['file'].startswith('lifecycle-'):
            with zipfile.ZipFile(path) as archive:
                result = json.loads(archive.read('summary.json'))
            require(result['passed'] is True and result['completed'] is True and result['exit_code'] == 0 and result['memory_max'] == 2147483648, 'Lifecycle acceptance missing')
    require(canonical is not None, 'Canonical artifact absent')
    recovery = Path(plan['recovery_file'])
    require(digest(recovery) == plan['recovery_sha256'], 'Recovery evidence changed')
    verify_local_recovery(recovery, plan)
    shutil.copyfile(recovery, assets / 'Trade-resource-recovery.zip')
    logs = {}
    for job in [product_job, *plan['prior_jobs']]:
        path = root / (str(job) + '.log')
        download(repo + '/actions/jobs/' + str(job) + '/logs', path)
        data = path.read_bytes()
        require(not TOKEN.search(data), 'Credential-shaped material in job log')
        logs[str(job) + '.log'] = data
    counts = [int(n) for n in re.findall(rb'Ran (\d+) tests? in', logs[str(product_job) + '.log'])]
    require(sum(counts) == plan['product_tests'] and b'FAILED (' not in logs[str(product_job) + '.log'], 'Product test evidence mismatch')
    make_zip(assets / 'product-and-prior-job-logs.zip', logs)
    prior = []
    for run_id in plan['prior_runs']:
        run = api(repo + '/actions/runs/' + str(run_id))
        prior.append({key: run[key] for key in ('id', 'name', 'head_sha', 'status', 'conclusion', 'html_url')})
    write_json(assets / 'prior-attempts.json', prior)
    write_json(assets / 'VALIDATION.json', dict(candidate=plan['candidate'], tree=plan['tree'], version=plan['version'], build=plan['build'],
        canonical=canonical, required_jobs=records, product_test_executions=sum(counts), original_artifacts=plan['artifacts'],
        recovery_sha256=plan['recovery_sha256'], limitations='Disposable constrained Trade execution is not live Granite acceptance. Conditional clean-file reclaim is not free heap or universal capacity clearance. Raw cgroup measurements, harness padding and prior failures remain disclosed. No production mutations or synthetic capacity stress.'))
    files = [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(assets.iterdir()) if p.is_file()]
    require(sum(x['bytes'] for x in files) < 512 * 1024**2, 'Unexpected attachment population size')
    write_json(assets / 'evidence-manifest.json', dict(candidate=plan['candidate'], tree=plan['tree'], files=files))
    files.append({'name': 'evidence-manifest.json', 'bytes': (assets / 'evidence-manifest.json').stat().st_size, 'sha256': digest(assets / 'evidence-manifest.json')})
    (assets / 'SHA256SUMS').write_text(''.join(x['sha256'] + '  ' + x['name'] + '\n' for x in files))
    return assets


def expected_assets(assets):
    manifest = json.loads((assets / 'evidence-manifest.json').read_text())
    for item in manifest['files']:
        p = assets / item['name']
        require(p.parent == assets and p.is_file() and not p.is_symlink() and p.stat().st_size == item['bytes'] and digest(p) == item['sha256'], 'Attachment manifest mismatch')
    expected = {x['name'] for x in manifest['files']} | {'evidence-manifest.json', 'SHA256SUMS'}
    require({p.name for p in assets.iterdir()} == expected, 'Unmanifested local attachment')
    sums = ''.join(digest(assets / name) + '  ' + name + '\n' for name in sorted(expected - {'SHA256SUMS'}))
    # Manifest rows are name-sorted, with the manifest's own digest appended.
    listed = dict(line.split('  ', 1)[::-1] for line in (assets / 'SHA256SUMS').read_text().splitlines())
    require(listed == dict(line.split('  ', 1)[::-1] for line in sums.splitlines()), 'Attachment checksum list mismatch')
    return {p.name: (p.stat().st_size, digest(p)) for p in assets.iterdir()}


def verify_remote_assets(release, expected, complete):
    remote = {x['name']: x for x in release['assets']}
    require(len(remote) == len(release['assets']) and set(remote) <= set(expected), 'Unexpected/duplicate draft asset')
    if complete:
        require(set(remote) == set(expected), 'Missing release attachment')
    for name, item in remote.items():
        require(item['state'] == 'uploaded' and item['size'] == expected[name][0] and item['digest'] == 'sha256:' + expected[name][1], 'Remote attachment mismatch: ' + name)
    return remote


def verify_remote_bytes(plan, root, expected):
    with tempfile.TemporaryDirectory(dir=root) as directory:
        subprocess.run(['gh', 'release', 'download', 'v' + plan['version'], '--repo', plan['repository'], '--dir', directory], check=True)
        paths = {p.name: p for p in Path(directory).iterdir()}
        require(set(paths) == set(expected), 'Release attachment readback population mismatch')
        for name, (size, sha) in expected.items():
            require(paths[name].stat().st_size == size and digest(paths[name]) == sha, 'Release attachment readback mismatch: ' + name)


def verify_preparation(plan, root, expected, run_id):
    require(run_id, 'Publish requires an explicit successful preparation run')
    repo = 'repos/' + plan['repository']
    run = api(repo + '/actions/runs/' + str(run_id))
    require(run['head_sha'] == os.environ['GITHUB_SHA'] and run['event'] == 'workflow_dispatch' and run['path'] == '.github/workflows/canonical-release-recovery.yml' and run['conclusion'] == 'success' and run['status'] == 'completed', 'Preparation was not successful on this publisher source')
    artifacts = api(repo + '/actions/runs/' + str(run_id) + '/artifacts?per_page=100')['artifacts']
    found = [x for x in artifacts if x['name'] == 'guarded-release-2223-prepare-' + str(run_id) and not x['expired']]
    require(len(found) == 1, 'Preparation certificate missing')
    path = root / 'preparation-certificate.zip'
    download(repo + '/actions/artifacts/' + str(found[0]['id']) + '/zip', path)
    require('sha256:' + digest(path) == found[0]['digest'], 'Preparation certificate checksum mismatch')
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        certificate = json.loads(archive.read('publication.json'))
    require(certificate['operation'] == 'prepare' and certificate['publisher'] == os.environ['GITHUB_SHA'] and certificate['candidate'] == plan['candidate'] and certificate['tree'] == plan['tree'] and certificate['main'] == plan['baseline'] and certificate['release_id'] == plan['draft_id'] and certificate['draft'] is True, 'Wrong preparation admission certificate')
    actual = {x['name']: (x['bytes'], x['sha256']) for x in certificate['attachments']}
    require(actual == expected, 'Prepared evidence differs from current release evidence')


def prepare_or_publish(plan, root, operation, prepared_run=None):
    pr, main = verify_context(plan, operation)
    assets = collect(plan, root)
    expected = expected_assets(assets)
    repo = 'repos/' + plan['repository']
    release_path = repo + '/releases/' + str(plan['draft_id'])
    release = api(release_path)
    require(release['tag_name'] == 'v' + plan['version'], 'Wrong existing release tag')
    require(release['target_commitish'] in {plan['candidate'], main}, 'Wrong existing release target')
    existing = verify_remote_assets(release, expected, complete=operation == 'publish')
    if operation == 'audit':
        require(release['draft'] and not release['immutable'], 'Audit requires existing draft')
    elif operation == 'prepare':
        require(release['draft'] and not release['immutable'], 'Preparation requires existing draft')
        for name in sorted(set(expected) - set(existing)):
            # The Actions GITHUB_TOKEN is used by the standard GitHub CLI only.
            subprocess.run(['gh', 'release', 'upload', 'v' + plan['version'], str(assets / name), '--repo', plan['repository']], check=True)
        release = api(release_path)
        verify_remote_assets(release, expected, complete=True)
        verify_remote_bytes(plan, root, expected)
    elif operation == 'publish':
        verify_preparation(plan, root, expected, prepared_run)
        # Recheck main/PR after downloads, before touching any tag/release metadata.
        _, latest = verify_context(plan, operation)
        require(latest == main and pr['merge_commit_sha'] == main, 'Main moved during publication')
        if release['draft']:
            notes = command('git', 'show', plan['candidate'] + ':RELEASE_NOTES.md').split('\n# ', 1)[0]
            notes += '\n\nReleased merge: ' + main + '\nValidated source: ' + plan['candidate'] + '\nSource tree: ' + plan['tree'] + '\nAll 12 required hosted jobs and all ten canonical gates passed; ' + str(plan['canonical_tests']) + ' canonical tests and ' + str(plan['product_tests']) + ' Product tests. Prior failures and resource qualifications remain in attached evidence.\n'
            api(release_path, {'tag_name': 'v' + plan['version'], 'target_commitish': main, 'name': 'DTOS v' + plan['version'] + ' / build ' + str(plan['build']), 'body': notes})
            release = api(release_path)
            require(release['draft'] and release['target_commitish'] == main, 'Draft target was not updated to approved merge')
        tag_ref_path = repo + '/git/ref/tags/v' + plan['version']
        lookup = subprocess.run(['gh', 'api', tag_ref_path], capture_output=True, text=True)
        if lookup.returncode:
            require('HTTP 404' in lookup.stderr, 'Tag lookup failed; not confirmed absent')
            require(release['draft'] and not release['immutable'], 'Missing tag on published release')
            tag = api(repo + '/git/tags', {'tag': 'v' + plan['version'], 'message': 'DTOS v' + plan['version'] + ' / build ' + str(plan['build']), 'object': main, 'type': 'commit'})
            api(repo + '/git/refs', {'ref': 'refs/tags/v' + plan['version'], 'sha': tag['sha']})
        tag = api(tag_ref_path)['object']
        if tag['type'] == 'tag':
            tag = api(repo + '/git/tags/' + tag['sha'])['object']
        require(tag['type'] == 'commit' and tag['sha'] == main, 'Version tag does not resolve to approved merge')
        if release['draft']:
            _, latest = verify_context(plan, operation)
            require(latest == main, 'Main changed before immutable publication')
            verify_remote_assets(api(release_path), expected, complete=True)
            api(release_path, {'draft': False})
        release = api(release_path)
        require(not release['draft'] and release.get('immutable') is True and release['target_commitish'] == main, 'Published release is not immutable or targets wrong merge')
        verify_remote_assets(release, expected, complete=True)
        verify_remote_bytes(plan, root, expected)
        verify_production(plan, main, root)
    write_json(root / 'publication.json', dict(operation=operation, publisher=os.environ['GITHUB_SHA'], candidate=plan['candidate'], tree=plan['tree'],
        main=main, release_id=release['id'], draft=release['draft'], immutable=release.get('immutable'), url=release['html_url'],
        attachments=[{'name': n, 'bytes': s, 'sha256': h} for n, (s, h) in sorted(expected.items())]))


def verify_production(plan, sha, root):
    import time
    attempts = []
    ready = None
    for _ in range(60):
        try:
            request = urllib.request.Request('https://dtos.onrender.com/health/ready', headers={'Cache-Control': 'no-cache'})
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.load(response)
            attempts.append(data)
            if data.get('status') == 'ready' and data.get('version') == plan['version'] and data.get('build') == plan['build'] and data.get('deployment', {}).get('commit') == sha:
                ready = data
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            attempts.append({'error_type': type(exc).__name__})
        finally:
            write_json(root / 'readiness.json', attempts)
        time.sleep(10)
    require(ready is not None, 'Approved production identity not ready in bounded observation')
    results = []
    for path, expected in [('/health/live', 200), ('/welcome', 200), ('/account/sign-in', 200), ('/api/my-dtos', 401), ('/api/inspect/live/teams', 401)]:
        try:
            with urllib.request.urlopen('https://dtos.onrender.com' + path, timeout=15) as response:
                code = response.status
                response.read()
        except urllib.error.HTTPError as exc:
            code = exc.code
        require(code == expected, 'Production read-only smoke failed: ' + path)
        results.append({'path': path, 'status': code})
    write_json(root / 'production-smoke.json', {'readiness': ready, 'reads': results, 'scope': 'Bounded public read-only requests; no private-account mutations or heavy production workloads.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--operation', choices=['audit', 'prepare', 'publish'], required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('.validation/guarded-release'))
    parser.add_argument('--prepared-run', type=int)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    outcome = dict(operation=args.operation, publisher=os.environ.get('GITHUB_SHA'), candidate=plan['candidate'], passed=False)
    try:
        prepare_or_publish(plan, args.output, args.operation, args.prepared_run)
        outcome['passed'] = True
    except Exception as exc:
        outcome['error_type'] = type(exc).__name__
        if isinstance(exc, RuntimeError):
            outcome['reason'] = str(exc)
        raise
    finally:
        write_json(args.output / 'outcome.json', outcome)
    print('Verified guarded release ' + args.operation + ' completed.')


if __name__ == '__main__':
    main()
