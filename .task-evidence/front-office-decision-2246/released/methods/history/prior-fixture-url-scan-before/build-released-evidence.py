"""Future-only sanitized evidence builder. No commit, push, network or release action.

Run only after all real release/deployment inputs exist and root review is complete.
An explicit reviewed additions manifest supplies the postdeployment FINAL_REPORT and
new integrated controls. This builder creates authored presentation metadata; it
does not independently rerun application, native publisher or production checks.
"""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from urllib.parse import parse_qsl, quote, urlsplit
import zipfile

from common import verify_worker_setup_controls
from worker_evidence import collect_worker_setup_evidence, verify_worker_setup_evidence

BASE = Path(__file__).resolve().parent
REPO = Path('/workspace/cache-sharing-handoff')
SOURCE_REPO = Path('/workspace/dtos')
BRANCH = 'evidence/cache-string-sharing-2237'
PREFIX = '.task-evidence/front-office-decision-2246/released'
# Final identity is assigned only from the explicit reviewed source input in main.
CANDIDATE = None
TREE = None
R2_HEAD = 'b602d6acd03cc1c95d85ee734d2d7f28658885cf'
R2_TREE = '8a687ea0256d6e0031b57e08e2a1a38a90a1a535'
R1_HEAD = '3a19eec0a00def82418d9658414f13e090d11b14'
R1_TREE = '041cfe403ca499c99b2be93a67d8e440c304be6b'
BASELINE = 'abbe723a0566cf84a8fff947cf7320cb66567a77'
REPOSITORY = 'Richarddavis47/dtos'
PART_LIMIT = 60000
# Existing canonical contract, not a snapshot of current job/file populations.
CANONICAL_GATES = 10
HOSTED_CONTRACT = {
    '.github/workflows/canonical-release-recovery.yml': {'canonical-release'},
    '.github/workflows/product-browser.yml': {'product-browser', 'my-team-browser', 'beginner-navigation',
        'public-welcome-browser', 'historical-trade-timeline', 'projection-display-cross-version', 'resident-refresh-memory'},
    '.github/workflows/validation-tooling.yml': {'tooling (ubuntu-24.04)', 'tooling (windows-latest)'},
    '.github/workflows/linux-market-lifecycle.yml': {'cgroup-lifecycle (ordinary)',
        'cgroup-lifecycle (archive-warmed)', 'cgroup-lifecycle (combined-read)'},
}
NATIVE_FILES = {'canonical-original.zip', 'current-history-original.zip', 'history-followthrough-original.zip',
    'market-history-coverage-original.zip', 'current-production-coverage-original.zip', 'trade-resource-original.zip',
    'league-entry-original.zip', 'restoration-unused-original.zip', 'actuals-restoration-original.zip',
    'preflight-original.zip', 'resident-refresh-original.zip', 'lifecycle-ordinary.zip',
    'lifecycle-archive-warmed.zip', 'lifecycle-combined-read.zip', 'public-welcome-security.zip'}
CORE = ('result.json', 'manifest.json', 'SHA256SUMS', 'canonical.log',
        'canonical-trace.jsonl', 'unittest-console.log', 'tests.jsonl', 'memory.jsonl')
DOCS = ('REPORT.md', 'SCOUT_HANDOFF.md', 'PRIOR_ATTEMPTS.md', 'CAPACITY_OPTIONS.md', 'README.md')
SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(*args, cwd=REPO, binary=False):
    value = subprocess.check_output(['git', *args], cwd=cwd)
    return value if binary else value.decode().strip()


def name_checked(name):
    require(isinstance(name, str) and name, 'Empty evidence name')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and '..' not in path.parts
            and '\\' not in name and not any(ord(c) < 32 for c in name), 'Unsafe evidence name')
    denied = {'.env', 'private', 'private-logs', 'private-cache', 'local-resource-inputs', '__pycache__'}
    require(not (set(part.lower() for part in path.parts) & denied), 'Excluded evidence path: ' + name)
    require(path.suffix.lower() not in {'.zip', '.sqlite', '.sqlite3', '.db', '.pyc', '.env'},
            'Binary archive/database/env payload excluded: ' + name)
    return path


def safe_file(relative):
    name_checked(relative)
    path = BASE / relative
    require(path.is_file() and not path.is_symlink(), 'Missing or symlink input: ' + relative)
    require(all(not parent.is_symlink() for parent in path.parents if parent != BASE.parent),
            'Symlink input ancestor: ' + relative)
    require(path.resolve().is_relative_to(BASE.resolve()), 'Input escaped R3')
    return path


def blob(relative):
    return safe_file(relative).read_bytes()


def record(relative):
    return json.loads(blob(relative))


def identity(value, label):
    require(CANDIDATE is not None and TREE is not None
            and value.get('candidate', value.get('head')) == CANDIDATE and value.get('tree') == TREE,
            'Wrong final source: ' + label)


def digest(raw):
    return sha256(raw).hexdigest()


def exact(raw, row, label):
    require(type(row['bytes']) is int and len(raw) == row['bytes'] and digest(raw) == row['sha256'],
            'Original bytes changed: ' + label)


def sanitize(name, raw):
    name_checked(name)
    require(not SECRET.search(raw), 'Credential-shaped bytes need manual review: ' + name)
    if name.endswith('.png'):
        require(raw.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG: ' + name)
        return
    text = raw.decode('utf-8')
    for url in re.findall(r'https?://[^\s<>\"\x27]+', text):
        parsed = urlsplit(url)
        require(parsed.username is None and parsed.password is None, 'URL userinfo excluded: ' + name)
        keys = {key.lower() for key, _ in parse_qsl(parsed.query)}
        require(not keys.intersection({'sig', 'signature', 'token', 'access_token', 'x-amz-signature',
                                      'x-amz-credential', 'x-amz-security-token', 'x-goog-signature',
                                      'x-goog-credential', 'googleaccessid', 'jwt'}),
                'Signed/token URL excluded: ' + name)
    if name.endswith('.json'):
        def inspect(value):
            if isinstance(value, dict):
                config = value.get('Config')
                require(not isinstance(config, dict) or 'Env' not in config, 'Full Docker Config.Env excluded: ' + name)
                for child in value.values():
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)
        inspect(json.loads(text))


def archive(relative, expected):
    # Archives are read locally, never copied into the evidence prefix.
    path = BASE / relative
    require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents)
            and path.resolve().is_relative_to(BASE.resolve()),
            'Missing original ZIP: ' + relative)
    exact(path.read_bytes(), expected, relative)
    value = zipfile.ZipFile(path)
    names = value.namelist()
    require(len(names) == len(set(names)), 'Duplicate ZIP members: ' + relative)
    for item in value.infolist():
        parsed = PurePosixPath(item.filename)
        require(not parsed.is_absolute() and '..' not in parsed.parts and '\\' not in item.filename,
                'Unsafe ZIP member')
        require(not stat.S_ISLNK(item.external_attr >> 16), 'ZIP symlink excluded')
    require(value.testzip() is None, 'Original ZIP CRC failure: ' + relative)
    return value


def verify_canonical(read, expected_tests, label, local=False):
    result = json.loads(read('result.json'))
    identity(result, label)
    require(result['passed'] is True and result['exit_code'] == 0, 'Canonical not successful: ' + label)
    # The committed hosted runner has no expected_test_count field; its complete
    # console and events below establish the executed count. Local records it.
    if local or 'expected_test_count' in result:
        require(result['expected_test_count'] == expected_tests, 'Canonical discovery count mismatch')
    require(result['cgroup_limit'] == 2147483648 and result['cpus'] == 2 and result['network'] == 'none',
            'Canonical resource identity mismatch')
    require(result['python'].startswith('3.14.3'), 'Canonical runtime mismatch')
    require(result['process_cleanup'].get('validator_reaped') is True
            and not result['process_cleanup'].get('timeout_triggered'), 'Canonical cleanup/timeout failure')
    require(not any(result['final_memory']['cgroup_memory_events'].get(k, 0) for k in ('oom', 'oom_kill')),
            'Canonical OOM recorded')
    manifest = json.loads(read('manifest.json'))
    sums_rows = [line.split('  ', 1) for line in read('SHA256SUMS').decode().splitlines()]
    require(all(len(row) == 2 for row in sums_rows), 'Malformed native SHA256SUMS')
    sums = {name: sha for sha, name in sums_rows}
    require(len(sums) == len(sums_rows) == len(manifest), 'Duplicate/incomplete native manifest')
    names = set()
    for row in manifest:
        path = PurePosixPath(row['name'])
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in row['name'], 'Unsafe canonical member')
        require(row['name'] not in names and sums[row['name']] == row['sha256'], 'Canonical manifest mismatch')
        names.add(row['name'])
        exact(read(row['name']), row, label + '/' + row['name'])
    console = read('unittest-console.log')
    match = re.search(rb'Ran (\d+) tests in [0-9.]+s\s+OK\s*$', console)
    require(match is not None and int(match[1]) == expected_tests, 'Canonical console incomplete')
    events = Counter(json.loads(line)['event'] for line in read('tests.jsonl').splitlines())
    require(events['start'] == events['stop'] == expected_tests and not any(events[k] for k in ('error', 'failure', 'skip')),
            'Canonical test events disagree')
    trace = [json.loads(line) for line in read('canonical-trace.jsonl').splitlines()]
    gates = [row for row in trace if row.get('event') == 'validation_child_completed']
    summaries = [row for row in trace if row.get('event') == 'validator_final_summary']
    require(len(gates) == CANONICAL_GATES and all(row['return_code'] == 0 for row in gates)
            and any(row.get('gates') == CANONICAL_GATES for row in summaries)
            and any(row.get('event') == 'validator_exit' and row.get('exit_code') == 0 for row in trace),
            'Complete canonical gate/exit trace required')
    return manifest


def main():
    global CANDIDATE, TREE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-evidence-head', required=True, help='Reviewed current evidence branch HEAD, never the future commit.')
    parser.add_argument('--source-sha256', required=True, help='Reviewed SHA256 of the actual R3/source.json; no pending identity is inferred.')
    parser.add_argument('--reviewed-additions', required=True, help='R3-relative explicit hash/byte allowlist; see RELEASED_EVIDENCE_METHODS.md.')
    args = parser.parse_args()
    require(re.fullmatch(r'[a-f0-9]{40}', args.expected_evidence_head) is not None, 'Full reviewed evidence SHA required')
    require(git('branch', '--show-current') == BRANCH and git('rev-parse', 'HEAD') == args.expected_evidence_head,
            'Evidence branch/head changed')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Evidence worktree must be clean')
    destination = REPO / PREFIX
    require(not destination.exists() and not destination.is_symlink(), 'Never overwrite an existing released prefix')
    require(not any(path.is_symlink() for path in destination.parents), 'Evidence destination ancestor is a symlink')

    source_raw = blob('source.json')
    require(re.fullmatch(r'[a-f0-9]{64}', args.source_sha256) is not None
            and digest(source_raw) == args.source_sha256, 'Actual reviewed source.json SHA256 required')
    source = json.loads(source_raw)
    require(all(isinstance(source.get(key), str) and re.fullmatch(r'[a-f0-9]{40}', source[key]) is not None
                for key in ('candidate', 'tree', 'baseline')), 'Actual full candidate/tree/baseline SHAs required')
    require(source.get('supersedes') == R2_HEAD and source['candidate'] != R2_HEAD and source['tree'] != R2_TREE,
            'R3 must identify the reviewed new source superseding failed b602, never relabel b602')
    CANDIDATE, TREE = source['candidate'], source['tree']
    identity(source, 'source.json')
    require(source['baseline'] == BASELINE and source['version'] == '1.22.31' and source['build'] == 2246 and source['pr'] == 335,
            'Wrong release/baseline identity')
    expected_tests = source['expected_test_count']
    require(type(expected_tests) is int and expected_tests > 0, 'Actual discovery count required')
    require(git('rev-parse', CANDIDATE + '^{tree}', cwd=SOURCE_REPO) == TREE, 'Committed final tree changed')
    patch = blob('candidate.patch')
    require(patch == git('diff', '--binary', BASELINE, CANDIDATE, cwd=SOURCE_REPO, binary=True), 'Exact committed patch required')
    patch_receipt = record('release-inputs.json')
    identity(patch_receipt, 'release-inputs.json')
    require(patch_receipt['baseline'] == BASELINE and patch_receipt['patch_bytes'] == len(patch)
            and patch_receipt['patch_sha256'] == digest(patch)
            and patch_receipt['metadata'] == {'VERSION': source['version'], 'BUILD_NUMBER': source['build']}, 'Patch receipt mismatch')

    checks = {'local-verified.json': 'all_local_gates_passed', 'host-canonical-verified.json': 'all_gates_passed',
              'hosted-artifacts-verified.json': 'passed', 'focused-resource-verified.json': 'all_native_guards_passed',
              'focused-ready.json': 'passed', 'recovery-offline-verified.json': 'all_native_recovery_guards_passed'}
    proofs = {}
    for filename, key in checks.items():
        proof = record(filename)
        identity(proof, filename)
        require(proof[key] is True, 'Mandatory gate missing: ' + filename)
        proofs[filename] = proof
    require(proofs['local-verified.json']['tests'] == proofs['host-canonical-verified.json']['tests'] == expected_tests,
            'Local/host executed totals differ')
    resources = record('resource-preservation-verified.json')
    require(resources['source'] == source and resources['all_native_guards_passed'] is True, 'Resource source/gates missing')
    review = record('source-review/source-review.json')
    require(review['source']['head'] == CANDIDATE and review['source']['tree'] == TREE
            and review['source']['baseline'] == BASELINE, 'Actual final-source policy review required')
    require(review['blocker_count'] == 0 and review['findings'] == [], 'Unresolved final source-policy findings')
    require(review['source']['working_tree_clean_at_review'] is True, 'Policy review did not inspect a clean final source')
    for name, checksum in review['scope']['source_file_sha256'].items():
        name_checked(name)
        require(digest(git('show', CANDIDATE + ':' + name, cwd=SOURCE_REPO, binary=True)) == checksum,
                'Policy review source bytes changed: ' + name)

    plan = record('2246-finalized-plan.json')
    identity(plan, 'finalized plan')
    require(plan['finalized'] is True and plan['baseline'] == BASELINE and plan['canonical_tests'] == expected_tests,
            'Finalized plan missing')
    records = record('hosted-final-records.json')
    require(len(plan['runs']) == len(HOSTED_CONTRACT)
            and {row['path']: set(row['jobs']) for row in plan['runs']} == HOSTED_CONTRACT,
            'Final plan must preserve the complete required workflow/job contract')
    for contract in plan['runs']:
        matches = [row for row in records if row['run']['id'] == contract['id']]
        require(len(matches) == 1, 'Required hosted run original missing')
        retained = matches[0]
        run = retained['run']
        require(run['head_sha'] == CANDIDATE and run['path'] == contract['path']
                and run['status'] == 'completed' and run['conclusion'] == 'success', 'Required hosted run failed')
        for name in contract['jobs']:
            jobs = [row for row in retained['jobs'] if row['name'] == name]
            require(len(jobs) == 1 and jobs[0]['head_sha'] == CANDIDATE and jobs[0]['status'] == 'completed'
                    and jobs[0]['conclusion'] == 'success', 'Required hosted job failed: ' + name)

    native = {row['file']: row for row in proofs['hosted-artifacts-verified.json']['originals']}
    queue = record('artifact-download-queue.json')
    require(len(native) == len(queue) and set(native) == {row['file'] for row in queue} == NATIVE_FILES,
            'Original archive population mismatch')
    for row in queue:
        require(all(native[row['file']][key] == row[key] for key in ('bytes', 'sha256', 'id', 'run'))
                and native[row['file']]['original_bytes_verified'] is True
                and native[row['file']]['specialized_guards_verified'] is True, 'Native archive guard/identity mismatch')
    planned = {row['file']: row for row in plan['artifacts']}
    require(len(planned) == len(plan['artifacts']) and set(planned) == set(native), 'Final plan original population mismatch')
    for row in queue:
        require(all(planned[row['file']][key] == row[key] for key in ('sha256', 'id', 'run', 'name')),
                'Final plan original identity mismatch')

    publisher = record('publisher-source.json')
    sealed = record('publisher-scoped-sealed.json')
    identity(sealed, 'sealed publisher checks')
    require(sealed['results'] and all(code == 0 for code in sealed['results'].values())
            and sealed['tests'] > 0 and sealed['canonical_steps_byte_identical'] is True,
            'Actual complete sealed publisher checks required')
    require(publisher['candidate'] == CANDIDATE and publisher['candidate_tree'] == TREE
            and publisher['sealed_receipt_sha256'] == digest(blob('publisher-scoped-sealed.json'))
            and publisher['source'] == sealed['source'], 'Frozen publisher not bound to sealed checks')
    merge = record('merged-source.json')
    published = record('published-publication.json')
    attached = record('published-attachment-verification.json')
    deployed = record('publication-verified.json')
    smoke = record('production-readonly-smoke.json')
    for label, proof in (('merge', merge), ('publication', published), ('attachments', attached), ('deployment', deployed)):
        identity(proof, label)
    merge_sha = merge['merge_commit']
    require(re.fullmatch(r'[a-f0-9]{40}', merge_sha) is not None and merge['validated_tree_unchanged'] is True, 'Actual validated merge required')
    require(merge['publisher'] == publisher['publisher'] == published['publisher'] == attached['publisher'], 'Frozen publisher mismatch')
    require(published['draft'] is False and published['immutable'] is True and published['main'] == merge_sha,
            'Actual immutable publication required')
    require(attached['native_all_attachment_bytes_read_back'] is True and attached['cloud_api_digests_match_certificate'] is True
            and attached['front_office_workflow_verified'] is True, 'Native attachment readback proof required')
    release = deployed['release']
    require(release['draft'] is False and release['immutable'] is True and release['tag_name'] == 'v' + source['version']
            and release['target_commitish'] == merge_sha and deployed['merge_commit'] == deployed['tag_target'] == merge_sha,
            'Immutable release/tag/deployment disagreement')
    require(deployed['run']['status'] == 'completed' and deployed['run']['conclusion'] == 'success'
            and deployed['run']['head_sha'] == publisher['publisher'], 'Publication run not successful')
    assets = {row['name']: row for row in release['assets']}
    expected_assets = {row['name']: row for row in attached['attachments']}
    require(len(assets) == len(release['assets']) and len(expected_assets) == len(attached['attachments'])
            and set(assets) == set(expected_assets), 'Immutable attachment population mismatch')
    for name, row in expected_assets.items():
        remote = assets[name]
        require(remote['state'] == 'uploaded' and remote['size'] == row['bytes']
                and remote['digest'] == 'sha256:' + row['sha256'], 'Attachment digest mismatch: ' + name)
    for name, row in native.items():
        require(name in expected_assets and all(expected_assets[name][key] == row[key] for key in ('bytes', 'sha256')),
                'Published native original differs from verified archive: ' + name)
    for asset_name, hash_key in (('League-Activation-Deferral-Handoff.zip', 'recovery_sha256'),
                                 ('Prior-attempts.zip', 'prior_evidence_sha256')):
        require(expected_assets[asset_name]['sha256'] == plan[hash_key], 'Published sealed ZIP differs from final plan')
    offline = proofs['recovery-offline-verified.json']
    require(offline['recovery_sha256'] == plan['recovery_sha256'] and offline['prior_sha256'] == plan['prior_evidence_sha256'],
            'Offline native gates are not bound to actual sealed ZIPs')
    ready = smoke['production_ready']
    require(ready['status'] == 'ready' and ready['version'] == source['version'] and ready['build'] == source['build']
            and ready['deployment']['commit'] == merge_sha, 'Actual production identity required')
    require(smoke['reads'] and all(row['guest_read_only'] is True for row in smoke['reads']), 'Actual readonly smoke required')
    observed = datetime.fromisoformat(smoke['observed_at'].replace('Z', '+00:00'))
    require(observed.tzinfo is not None, 'Production observation timestamp must be timezone-aware')

    additions = record(args.reviewed_additions)
    identity(additions, 'reviewed additions')
    require(additions['sanitized_for_publication'] is True and additions['reviewed_by'] and additions['reviewed_at_utc'],
            'Explicit sanitization review required')
    require(additions['scope'] == 'Authored publication selection; not independent gate verification', 'Authored selection scope required')
    require(additions['production_observed_at'] == smoke['observed_at'] and additions['merge_commit'] == merge_sha,
            'Postdeployment selection must bind actual production observation')
    selected_at = datetime.fromisoformat(additions['reviewed_at_utc'].replace('Z', '+00:00'))
    require(selected_at.tzinfo is not None and selected_at >= observed, 'Additions review must follow actual deployment proof')
    roles = {row['role'] for row in additions['files']}
    require({'final-report', 'integrated-control'} <= roles, 'Postdeployment FINAL_REPORT and integrated controls required')

    payloads, origins = {}, {}
    def add(name, raw, origin):
        require(name not in payloads, 'Duplicate destination: ' + name)
        sanitize(name, raw)
        payloads[name], origins[name] = raw, origin
    def copy(relative, destination_name=None):
        add(destination_name or 'final/' + relative, blob(relative), 'Exact retained R3 file: ' + relative)
    def authored(name, value):
        raw = value.encode() if isinstance(value, str) else (json.dumps(value, indent=2) + '\n').encode()
        add(name, raw, 'Authored presentation or derived integrity metadata; not independent verification')

    fixed = ('source.json', 'candidate.patch', 'release-inputs.json', 'canonical-invocation.json',
             'focused-ready.json', 'focused-original.log', 'worker-setup-verified.json', 'resource-preservation-verified.json',
             'resource-native-guards.json', 'resource-invocation.json', 'resource-methods.md',
             'local-verified.json', 'host-canonical-verified.json', 'hosted-artifacts-verified.json',
             'focused-resource-verified.json', 'recovery-offline-verified.json', 'capture-extraction.json',
             'validation-runs.json', 'hosted-final-records.json', 'artifact-download-queue.json',
             'product-test-counts.json', 'public-welcome-test-counts.json', '2246-finalized-plan.json',
             'recovery-package.json', 'prior-package.json', 'publisher-scoped-sealed.json', 'publisher-workflow-review.json',
             'publisher-source.json', 'merged-source.json', 'published-publication.json',
             'prepared-publication.json', 'prepared-attachment-verification.json', 'published-attachment-verification.json',
             'publication-verified.json', 'publisher-production-smoke.json', 'production-readonly-smoke.json',
             'preparation-certificate-metadata.json', 'publication-certificate-metadata.json',
             'preparation-run.json', 'publication-run.json', 'harness-origins.json', 'patch-packaging-controls.json',
             'source-review/source-review.json', 'source-review/source-review.md', 'source-review/SHA256SUMS',
             'retained-history-feature.json', 'retained-history-probe-original.log', 'retained-history-probe-invocation.json')
    for relative in fixed:
        copy(relative)
    copy(args.reviewed_additions, 'selection/reviewed-additions.json')
    local_root = BASE / 'local-canonical'
    def local_read(name):
        path = local_root / name
        require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents)
                and path.resolve().is_relative_to(local_root.resolve()), 'Unsafe local canonical member')
        return path.read_bytes()
    local_manifest = verify_canonical(local_read, expected_tests, 'local canonical', local=True)
    require({p.relative_to(local_root).as_posix() for p in local_root.rglob('*') if p.is_file()}
            == {row['name'] for row in local_manifest} | {'manifest.json', 'SHA256SUMS'}, 'Local canonical population changed')
    for name in CORE:
        copy('local-canonical/' + name, 'local-canonical/' + name)
    with archive('hosted-originals/canonical-original.zip', native['canonical-original.zip']) as original:
        verify_canonical(original.read, expected_tests, 'host canonical')
        for name in CORE:
            add('host-canonical/' + name, original.read(name), 'Exact member of verified native canonical-original.zip: ' + name)

    product = record('product-test-counts.json')
    identity(product, 'Product counts')
    product_raw = blob('hosted-decoded-originals/product-original.log')
    exact(product_raw, {'bytes': product['original_bytes'], 'sha256': product['original_sha256']}, 'whole decoded Product log')
    counts = [int(value) for value in re.findall(rb'Ran (\d+) tests in [0-9.]+s', product_raw)]
    require(counts == product['counts'] and sum(counts) == product['total'] == plan['product_tests'], 'Actual Product total mismatch')
    product_source = record('hosted-decoded-originals/product-job-source.json')
    identity(product_source, 'Product source proof')
    check = product_source['completed_check_api_original']
    require(check['head_sha'] == CANDIDATE and check['status'] == 'completed' and check['conclusion'] == 'success'
            and check['id'] == product['job'] == product_source['job_id'] and check['name'] == 'product-browser'
            and check['app']['slug'] == 'github-actions', 'Product source identity mismatch')
    product_runs = [row for row in records if row['run']['path'] == '.github/workflows/product-browser.yml']
    require(len(product_runs) == 1 and product_runs[0]['run']['id'] == product['run']
            and check['details_url'] == 'https://github.com/' + REPOSITORY + '/actions/runs/' + str(product['run']) + '/job/' + str(product['job']),
            'Product workflow run/source check disagreement')
    snapshot = product_source['source_snapshot']
    snapshot_raw = blob(snapshot['file'])
    exact(snapshot_raw, snapshot, 'Original Product source API snapshot')
    selected_checks = [row for row in json.loads(snapshot_raw)['check_runs'] if row['id'] == product['job']]
    require(selected_checks == [check], 'Product source proof differs from original API snapshot')
    add('product/check-api-original.json', snapshot_raw, 'Exact original API snapshot bound by Product source proof: ' + snapshot['file'])
    require(product['source_proof_sha256'] == digest(blob('hosted-decoded-originals/product-job-source.json'))
            and product['transfer_receipt_sha256'] == digest(blob('hosted-decoded-originals/product-log-transfer.json')),
            'Product source/transfer receipt mismatch')
    for name in ('product-original.log', 'product-job-source.json', 'product-log-transfer.json'):
        copy('hosted-decoded-originals/' + name, 'product/' + name)
    with archive('hosted-originals/public-welcome-security.zip', native['public-welcome-security.zip']) as original:
        identity(json.loads(original.read('source.json')), 'Welcome native source')
        welcome_raw = original.read('raw.log')
        welcome = record('public-welcome-test-counts.json')
        identity(welcome, 'Welcome counts')
        exact(welcome_raw, {'bytes': welcome['original_bytes'], 'sha256': welcome['original_sha256']}, 'whole Welcome log')
        counts = [int(value) for value in re.findall(rb'Ran (\d+) tests in [0-9.]+s', welcome_raw)]
        require(counts == welcome['counts'] and sum(counts) == welcome['total'] and re.search(rb'\bOK\s*$', welcome_raw),
                'Actual Welcome total mismatch')
        for name in ('raw.log', 'source.json'):
            add('welcome/' + name, original.read(name), 'Exact verified public-welcome-security.zip member: ' + name)

    extraction = record('capture-extraction.json')
    identity(extraction, 'capture extraction')
    require(extraction['source_bound_native_originals'] is True, 'Source-bound native captures required')
    allowed_captures = {'partner-history', 'team-need', 'protections', 'offer-comparison', 'activation', 'front-office-workflow', 'history-browser'}
    require({row['destination'] for row in extraction['captures']} == allowed_captures, 'Required native capture families missing')
    for capture in extraction['captures']:
        with archive('hosted-originals/' + capture['original'], native[capture['original']]) as original:
            require(capture['original_sha256'] == native[capture['original']]['sha256'], 'Capture archive changed')
            for row in capture['members']:
                relative = capture['destination'] + '/' + row['name']
                raw = blob(relative)
                exact(raw, row, relative)
                require(raw == original.read(capture['prefix'] + row['name']), 'Extracted capture differs from native ZIP')
                if PurePosixPath(row['name']).suffix in {'.json', '.png'}:
                    add('captures/' + relative, raw, 'Exact source-bound native ZIP member: ' + capture['original'] + '/' + capture['prefix'] + row['name'])
    for path in sorted((BASE / 'focused').rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.png'}:
            copy(path.relative_to(BASE).as_posix())
    focused_result = record('focused/result.json')
    identity(focused_result, 'focused result')
    focused_ready = proofs['focused-ready.json']
    worker_setup_controls = verify_worker_setup_controls(source)
    require(record('worker-setup-verified.json') == worker_setup_controls,
            'Retained worker setup verification receipt differs from the exact re-read original controls')
    require(focused_ready.get('worker_setup_controls') == worker_setup_controls,
            'Focused readiness must contain the exact re-read worker setup controls receipt')
    require(record('canonical-invocation.json').get('worker_setup_controls') == worker_setup_controls,
            'Canonical launch was not bound to mandatory worker setup controls')
    worker_payloads = collect_worker_setup_evidence(worker_setup_controls)
    for name, raw in worker_payloads.items():
        add('worker-setup-controls/' + name, raw,
            'Explicit selected original worker method/log evidence or clearly labeled DERIVED metadata; see worker-evidence-manifest.json')
    require(focused_result['passed'] is True and not any(focused_result[key] for key in ('failures', 'errors', 'skips'))
            and focused_result['tests'] == focused_ready['tests'] and focused_result['expected_test_count'] == expected_tests
            and focused_ready['original_console_sha256'] == digest(blob('focused-original.log'))
            and focused_ready['native_resource_receipt_sha256'] == digest(blob('resource-preservation-verified.json')),
            'Strict focused result/log/resource binding failed')
    for proof in focused_ready['native_guards'].values():
        identity(proof, 'focused native guard')
        require(proof['passed'] is True, 'Focused native guard failed')
    resource_receipts = {row['name']: row for row in resources['native_guard_receipts']}
    for case in ('local-preflight', 'local-restoration-unused', 'local-resident-refresh'):
        result = 'result.json' if case == 'local-preflight' else 'evidence/result.json'
        native_receipt = resource_receipts[case]
        require(native_receipt['passed'] is True, 'Resource native receipt failed')
        identity(resources['native_results'][case], case)
        with archive('local-resource-native-archives/' + case + '.zip',
                     {'bytes': native_receipt['archive_bytes'], 'sha256': native_receipt['archive_sha256']}) as original:
            for name in ('raw.log', result, 'SHA256SUMS'):
                raw = blob(case + '/' + name)
                require(raw == original.read(name) and digest(raw) == native_receipt['members'][name], 'Resource original differs from native ZIP')
                add('resources/' + case + '/' + name, raw, 'Exact original native local resource ZIP member: ' + case + '/' + name)
        copy(case + '/invocation.json', 'resources/' + case + '/invocation.json')
    recovery_meta = record('recovery-package.json')
    require(recovery_meta['sha256'] == plan['recovery_sha256'], 'Sealed Recovery identity differs from plan')
    with archive('recovery-package.zip', recovery_meta) as recovery:
        worker_prefix = 'worker-setup-controls/'
        worker_names = {name.removeprefix(worker_prefix) for name in recovery.namelist() if name.startswith(worker_prefix)}
        verify_worker_setup_evidence(lambda name: recovery.read(worker_prefix + name), worker_setup_controls,
                                     worker_names, recovery.read('methods/worker_evidence.py'))
        for name, raw in worker_payloads.items():
            require(recovery.read(worker_prefix + name) == raw,
                    'Selected worker original/derived bytes differ from sealed Recovery: ' + name)
        for name in DOCS:
            add('prepublication/' + name, recovery.read(name), 'Original prepublication document sealed in immutable Recovery.zip')
    prior = record('prior-package.json')
    require(prior['sha256'] == plan['prior_evidence_sha256'] and prior['native_prior_guard_passed'] is True
            and prior['both_complete_original_archives_linked_not_rebuilt'] is True
            and prior['b602_publication_readback_verified'] is True, 'Prior originals/publication readback not verified')
    old_links = [row for row in prior['linked_originals']
                 if row.get('commit') == 'ba102d1eb9f9bc90679d7b4f1fafc30cb76c1efd']
    expected_old = {
        'prior-attempts-original.zip': (81491689, '39f794f9f825c3d26766239c6d3906e6f4f3d3a24c2e3f2101c31b3b6b39cb78'),
        'local-isolated-failed-original.zip': (81042922, 'cca0b7f4d239fc1338618458594b60da747e8ca3aa4988b28413c8b0a07e7da6'),
    }
    require(len(old_links) == len(expected_old) and {row['file'] for row in old_links} == set(expected_old),
            'The two old immutable full archive links must remain present')
    for row in old_links:
        require((row['bytes'], row['sha256']) == expected_old[row['file']]
                and row['prefix'] == '.task-evidence/activation-deferral-2246/validation-held',
                'Old immutable archive identity changed')
    newer_links = [row for row in prior['linked_originals'] if row not in old_links]
    b602_links = [row for row in newer_links if row.get('file') == 'hosted/failed-canonical-original.zip']
    require(len(b602_links) == 1, 'Exactly one new immutable b602 failed-hosted archive link required')
    authored_local_links = [row for row in newer_links if row not in b602_links]
    require(1 <= len(authored_local_links) <= 2, 'Complete authored b602 local ZIP and optional earlier3a19 local ZIP links required')
    for row in old_links + b602_links:
        require(row['original_archive_rebuilt'] is False and row['complete_original_archive_embedded'] is False,
                'Full prior archives must remain linked originals without rebuilt/embedded duplicates')
    b602_link = b602_links[0]
    failed_member = b602_link.get('member', b602_link['file'])
    require(b602_link['historical_source'] == {'candidate': R2_HEAD, 'tree': R2_TREE}
            and b602_link['bytes'] == 93758581
            and b602_link['sha256'] == '9a51b7ffb0b4c4e07112e59d2f393ffb37489f5afe75563f661c9ae1ea766e9d'
            and b602_link['prefix'] == '.task-evidence/front-office-decision-2246/failed-b602'
            and re.fullmatch(r'[a-f0-9]{40}', b602_link['commit']) is not None
            and failed_member == 'hosted/failed-canonical-original.zip'
            and b602_link['canonical_outcome']['passed'] is False
            and b602_link['canonical_outcome']['canonical_manifest_entries'] == 689,
            'New b602 link must identify the complete original failed hosted archive')
    require(b602_link['raw_url'] == 'https://raw.githubusercontent.com/' + REPOSITORY + '/' + b602_link['commit']
            + '/' + b602_link['prefix'] + '/' + failed_member
            and b602_link['browser_url'] == 'https://github.com/' + REPOSITORY + '/blob/' + b602_link['commit']
            + '/' + b602_link['prefix'] + '/' + failed_member, 'b602 archive URLs must pin the actual immutable publication commit')
    expected_local_archives = {
        'local-cancelled/local-cancelled-original-members.zip':
            ({'candidate': R2_HEAD, 'tree': R2_TREE}, 258, 'local_cancelled_originals_archive'),
        'prior-3a19/local-cancelled-original-members.zip':
            ({'candidate': R1_HEAD, 'tree': R1_TREE}, 138, 'earlier_local_cancelled_originals_archive'),
    }
    selected_local_members = [row.get('member', row['file']) for row in authored_local_links]
    require(len(selected_local_members) == len(set(selected_local_members))
            and 'local-cancelled/local-cancelled-original-members.zip' in selected_local_members
            and set(selected_local_members) <= set(expected_local_archives), 'Authored canceled-local ZIP population changed')
    for row in authored_local_links:
        member = row.get('member', row['file'])
        historical_source, manifest_entries, receipt_field = expected_local_archives[member]
        require(row['historical_source'] == historical_source and row['original_manifest_entries'] == manifest_entries
                and row['newly_authored'] is True and row['original_runtime_archive'] is False
                and row['all_original_member_bytes_verified'] is True and row['complete_original_archive_embedded'] is False
                and row['commit'] == b602_link['commit'] and row['prefix'] == b602_link['prefix']
                and row['original_remote_readback_receipt'] == b602_link['original_remote_readback_receipt']
                and type(row['bytes']) is int and row['bytes'] > 0 and re.fullmatch(r'[a-f0-9]{64}', row['sha256']) is not None,
                'Authored canceled-local link must preserve every original member and historical source')
        require(row['raw_url'] == 'https://raw.githubusercontent.com/' + REPOSITORY + '/' + row['commit']
                + '/' + row['prefix'] + '/' + member
                and row['browser_url'] == 'https://github.com/' + REPOSITORY + '/blob/' + row['commit']
                + '/' + row['prefix'] + '/' + member, 'Authored canceled-local ZIP URLs must pin actual failure publication')
    with archive('prior-package.zip', prior) as original:
        for name in ('LINKED_ORIGINALS.json', 'PRIOR_PACKAGE_README.md', 'prior-manifest.json'):
            add('prior-attempts/' + name, original.read(name), 'Exact sealed Prior-attempts.zip member: ' + name)
        manifest_member = 'superseded-3a19/prior-3a19/attempt-api-original-manifest.json'
        prior_manifest_raw = original.read(manifest_member)
        prior_manifest = json.loads(prior_manifest_raw)
        require(prior_manifest['candidate'] == R1_HEAD and prior_manifest['tree'] == R1_TREE,
                'Historical 3a19 source association changed')
        add('prior-attempts/3a19/attempt-api-original-manifest.json', prior_manifest_raw,
            'Exact historical API manifest sealed in Prior-attempts.zip: ' + manifest_member)
        expected_prior_outcomes = {42986949235: 'failure', 42986949262: 'cancelled'}
        require({row['id']: row['conclusion'] for row in prior_manifest['files']} == expected_prior_outcomes,
                'Historical 3a19 failed/canceled attempt identities changed')
        for row in prior_manifest['files']:
            raw = original.read('superseded-3a19/api/' + row['name'])
            exact(raw, row, 'Historical 3a19 API original')
            retained = json.loads(raw)
            require(retained['head_sha'] == R1_HEAD and retained['run_attempt'] == 1
                    and retained['conclusion'] == expected_prior_outcomes[retained['id']], 'Historical API original outcome changed')
            add('prior-attempts/3a19/' + row['name'], raw, 'Exact historical terminal API original sealed in Prior-attempts.zip')
        publication_member = b602_link['original_remote_readback_receipt']
        failed_publication_raw = original.read(publication_member)
        failed_publication = json.loads(failed_publication_raw)
        failed_links_raw = original.read('superseded-b602/publication-links.json')
        failed_manifest_raw = original.read('superseded-b602/publication-manifest.json')
        failed_sums_raw = original.read('superseded-b602/publication-SHA256SUMS')
        receipt_method = safe_file('prior-b602-additions.py')
        receipt_spec = importlib.util.spec_from_file_location('released_prior_receipt_metadata', receipt_method)
        require(receipt_spec is not None and receipt_spec.loader is not None, 'Historical receipt metadata verifier is unavailable')
        receipt_guard = importlib.util.module_from_spec(receipt_spec)
        receipt_spec.loader.exec_module(receipt_guard)
        verified_receipt, _ = receipt_guard.verify_publication_receipt_metadata(
            failed_publication_raw, failed_links_raw, failed_manifest_raw, failed_sums_raw)
        require(verified_receipt == failed_publication, 'Historical receipt metadata verifier disagrees with original bytes')
        require(failed_publication['publication_commit'] == b602_link['commit']
                and failed_publication['prefix'] == b602_link['prefix'] and failed_publication['all_bytes_verified'] is True
                and failed_publication['source']['candidate'] == R2_HEAD and failed_publication['source']['tree'] == R2_TREE,
                'Actual immutable b602 publication/readback receipt required')
        failed_archive = failed_publication['original_failed_hosted_archive']
        require(failed_archive['member'] == failed_member and failed_archive['bytes'] == b602_link['bytes']
                and failed_archive['sha256'] == b602_link['sha256'] and failed_archive['manifest_entries'] == 689,
                'b602 publication/readback original archive identity mismatch')
        for row in authored_local_links:
            member = row.get('member', row['file'])
            historical_source, manifest_entries, receipt_field = expected_local_archives[member]
            published_local = failed_publication[receipt_field]
            require(published_local['member'] == member and published_local['bytes'] == row['bytes']
                    and published_local['sha256'] == row['sha256']
                    and published_local['original_manifest_entries'] == manifest_entries
                    and published_local['newly_authored'] is True and published_local['original_runtime_archive'] is False
                    and published_local['all_original_member_bytes_verified'] is True,
                    'Authored complete canceled-local ZIP differs from actual publication/readback receipt')
            if receipt_field == 'earlier_local_cancelled_originals_archive':
                require(published_local['source'] == historical_source, 'Earlier canceled-local ZIP source association changed')
        add('prior-attempts/b602-publication-readback.json', failed_publication_raw,
            'Exact historical immutable b602 failure-publication readback receipt sealed in Prior-attempts.zip')
        for name, raw in (('b602-publication-links.json', failed_links_raw),
                          ('b602-publication-manifest.json', failed_manifest_raw),
                          ('b602-publication-SHA256SUMS', failed_sums_raw)):
            add('prior-attempts/' + name, raw, 'Exact historical immutable b602 publication metadata sealed in Prior-attempts.zip')

    for stage in ('preparation', 'publication'):
        metadata = record(stage + '-certificate-metadata.json')
        expected = {'bytes': metadata['size_in_bytes'], 'sha256': metadata['digest'].removeprefix('sha256:')}
        with archive(stage + '-certificate.zip', expected) as original:
            certificate = json.loads(original.read('publication.json'))
            identity(certificate, stage + ' certificate')
            require(certificate['publisher'] == publisher['publisher'], 'Certificate publisher mismatch')
            if stage == 'publication':
                require(certificate == published, 'Published certificate receipt changed')
            names = ['outcome.json', 'publication.json', 'assets/VALIDATION.json', 'assets/evidence-manifest.json',
                     'assets/SHA256SUMS', 'assets/prior-attempts.json']
            if stage == 'publication':
                names.append('production-smoke.json')
            for name in names:
                add('certificates/' + stage + '/' + name, original.read(name), 'Exact original Actions ' + stage + ' certificate member: ' + name)

    final_reports = 0
    for row in additions['files']:
        require(row['sanitized'] is True and row['purpose'], 'Each additional file needs explicit sanitization/purpose')
        require(row['role'] in {'final-report', 'integrated-control', 'prior-failure-original', 'authored-doc'}, 'Unknown additional evidence role')
        raw = blob(row['source'])
        exact(raw, row, row['source'])
        if row['role'] == 'final-report':
            require(row['destination'] == 'FINAL_REPORT.md' and row['source'] == 'FINAL_REPORT.md', 'Final report must be separately authored in R3')
            require(CANDIDATE.encode() in raw and TREE.encode() in raw and merge_sha.encode() in raw, 'Final report must name final candidate/tree and actual merge')
            final_reports += 1
        else:
            require(row['destination'].startswith({'integrated-control': 'integrated-controls/', 'prior-failure-original': 'prior-attempts/new-originals/',
                                                  'authored-doc': 'postdeployment-docs/'}[row['role']]), 'Additional destination outside role allowlist')
        add(row['destination'], raw, 'Explicit reviewed addition (' + row['role'] + '): ' + row['source'])
    require(final_reports == 1, 'Exactly one separately authored FINAL_REPORT required')

    methods = sorted(path for path in BASE.glob('*.py') if path.is_file())
    methods += sorted(path for path in (BASE / 'harness').rglob('*.py') if path.is_file())
    # No earlier runtime harness is copied into R3 during preparation. Include
    # the actual fresh focused runner if the eventual run retained one.
    if (BASE / 'focused/run.py').exists():
        methods.append(safe_file('focused/run.py'))
    method_rows = []
    for path in methods:
        relative = path.relative_to(BASE).as_posix()
        raw = blob(relative)
        add('methods/' + relative, raw, 'Exact reviewed method source: ' + relative)
        method_rows.append({'name': relative, 'bytes': len(raw), 'sha256': digest(raw)})
    copy('RELEASED_EVIDENCE_METHODS.md', 'methods/RELEASED_EVIDENCE_METHODS.md')
    authored('methods/methods-manifest.json', {'scope': 'Authored method byte identities; no execution or independent verification claim', 'files': method_rows})
    links = []
    for name, row in sorted(expected_assets.items()):
        links.append({**row, 'url': 'https://github.com/' + REPOSITORY + '/releases/download/v' + source['version'] + '/' + quote(name, safe=''),
                      'immutable_release_id': release['id'], 'included_in_this_prefix': False})
    authored('IMMUTABLE_RELEASE_ATTACHMENTS.json', {'scope': 'Authored link index. Native publisher all-byte receipt and Cloud API digest receipt remain distinct originals.',
                                                  'release_url': release['html_url'], 'attachments': links,
                                                  'prior_archives': prior['linked_originals']})
    authored('README.md', '# Front Office decision 2246 — released evidence\n\n'
             'This sanitized handoff copies original final-source evidence after actual immutable publication and deployment proof. '
             'Its index, selection and checksums are authored presentation metadata, not independent application verification. '
             'Read FINAL_REPORT.md for actual outcomes and remaining acceptance limits. prepublication/ retains the original sealed reports unchanged. '
             'Large original ZIPs remain immutable release attachments with native readback/digest receipts; old full failed archives remain linked at ba102d1. '
             'Private owner entry, physical Safari and live Granite acceptance are distinct from disposable fixture and bounded guest/static evidence.\n\n'
             'readable/ contains contiguous UTF8 parts of complete long text originals, each at most 60000 bytes. '
             'A separate anonymous HTTPS readback receipt must be written outside this prefix after its actual publication commit exists.\n')

    for original_name, raw in list(sorted(payloads.items())):
        if len(raw) <= PART_LIMIT or original_name.endswith('.png'):
            continue
        raw.decode('utf-8')
        directory = 'readable/' + original_name
        offset, parts = 0, []
        while offset < len(raw):
            end = min(offset + PART_LIMIT, len(raw))
            if end < len(raw):
                newline = raw.rfind(b'\n', offset, end)
                if newline >= offset:
                    end = newline + 1
                while end > offset:
                    try:
                        raw[offset:end].decode('utf-8')
                        break
                    except UnicodeDecodeError:
                        end -= 1
            require(end > offset, 'Cannot bound UTF8 part: ' + original_name)
            chunk = raw[offset:end]
            part_name = directory + '/part-' + str(len(parts) + 1).zfill(4) + '.txt'
            add(part_name, chunk, 'Contiguous exact original UTF8 bytes: ' + original_name)
            parts.append({'path': part_name, 'offset': offset, 'bytes': len(chunk), 'sha256': digest(chunk)})
            offset = end
        require(b''.join(payloads[row['path']] for row in parts) == raw, 'Readable reconstruction mismatch')
        authored(directory + '/index.json', {'original': original_name, 'bytes': len(raw), 'sha256': digest(raw), 'parts': parts,
                                           'method': 'Contiguous original UTF8 bytes; no filtering, redaction, newline conversion or reencoding.'})
    rows = [{'name': name, 'bytes': len(raw), 'sha256': digest(raw), 'origin': origins[name]} for name, raw in sorted(payloads.items())]
    manifest = {'schema': 'dtos-released-evidence-v1', 'status': 'Final handoff assembled from actual released/deployed inputs',
                'metadata_authority': 'Authored presentation and copied-evidence integrity only; no independent verification claim',
                'source': source, 'source_input_sha256': args.source_sha256,
                'merge_commit': merge_sha, 'publisher': publisher['publisher'], 'prefix': PREFIX,
                'assembled_at_utc': datetime.now(timezone.utc).isoformat(), 'evidence_parent_commit': args.expected_evidence_head,
                'production_observed_at': smoke['observed_at'], 'payload_files': len(rows), 'payload_bytes': sum(row['bytes'] for row in rows),
                'exclusions': ['Environment files and full Docker Config.Env', 'Private Render logs, private caches and database bodies',
                               'Raw signed URL stderr or signed URL values', 'Unneeded artifacts and duplicate large original ZIPs'], 'files': rows}
    authored('publication-manifest.json', manifest)
    sums = ''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows)
    sums += digest(payloads['publication-manifest.json']) + '  publication-manifest.json\n'
    authored('SHA256SUMS', sums)
    require(git('rev-parse', 'HEAD') == args.expected_evidence_head and not git('status', '--porcelain', '--untracked-files=all'),
            'Evidence worktree changed during preparation')
    # All checks precede the single atomic creation of the new prefix.
    with tempfile.TemporaryDirectory(prefix='released-evidence-stage-', dir=BASE) as temporary:
        staged = Path(temporary) / 'payload'
        staged.mkdir()
        for name, raw in sorted(payloads.items()):
            target = staged / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
        require(not destination.exists(), 'Destination appeared during preparation')
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staged, destination)
    changed = git('status', '--porcelain', '--untracked-files=all').splitlines()
    require(changed and all(line.startswith('?? ' + PREFIX + '/') for line in changed), 'Only the new evidence prefix may change')
    print(json.dumps({'created_prefix': PREFIX, 'payload_files': len(rows), 'all_files': len(payloads),
                      'payload_bytes': manifest['payload_bytes'], 'committed_or_pushed': False,
                      'next': 'Review all bytes, then publish through the authorized evidence workflow. Run explicit-commit HTTPS readback afterward.'}, indent=2))


if __name__ == '__main__':
    main()
