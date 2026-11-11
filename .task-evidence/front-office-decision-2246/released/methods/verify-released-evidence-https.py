"""Future-only anonymous raw-byte HTTPS readback of an actual publication commit.

Reads every released payload, publication manifest and SHA256 sidecar. Writes its
new receipt outside the published prefix only after every byte has matched. This
does not publish, commit, push, rerun release gates or access private production.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
from urllib.parse import quote

import httpx

BASE = Path(__file__).resolve().parent
REPO = Path('/workspace/cache-sharing-handoff')
BRANCH = 'evidence/cache-string-sharing-2237'
PREFIX = '.task-evidence/front-office-decision-2246/released'
ROOT = REPO / PREFIX
R2_HEAD = 'b602d6acd03cc1c95d85ee734d2d7f28658885cf'
R2_TREE = '8a687ea0256d6e0031b57e08e2a1a38a90a1a535'
BASELINE = 'abbe723a0566cf84a8fff947cf7320cb66567a77'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(*args, binary=False):
    raw = subprocess.check_output(['git', *args], cwd=REPO)
    return raw if binary else raw.decode().strip()


def checked(name):
    require(isinstance(name, str) and name, 'Empty payload name')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name and '..' not in path.parts
            and '\\' not in name and not any(ord(c) < 32 for c in name), 'Unsafe payload name')
    return name


class Anonymous(httpx.Auth):
    def auth_flow(self, request):
        request.headers.pop('Authorization', None)
        request.headers.pop('Cookie', None)
        yield request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publication-commit', required=True, help='Actual full immutable evidence publication commit SHA.')
    parser.add_argument('--source-sha256', required=True, help='Reviewed SHA256 of actual R3/source.json matching the published final source input.')
    parser.add_argument('--receipt', required=True, help='New R3-relative JSON receipt path, outside the evidence worktree/prefix.')
    args = parser.parse_args()
    commit = args.publication_commit
    require(re.fullmatch(r'[a-f0-9]{40}', commit) is not None, 'Actual full publication commit is required')
    require(git('branch', '--show-current') == BRANCH and git('rev-parse', 'HEAD') == commit,
            'Local evidence branch must be at the explicit actual publication commit')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Evidence worktree must be clean')
    source_path = BASE / 'source.json'
    require(source_path.is_file() and not source_path.is_symlink() and not any(p.is_symlink() for p in source_path.parents),
            'Actual reviewed R3/source.json required')
    source_raw = source_path.read_bytes()
    require(re.fullmatch(r'[a-f0-9]{64}', args.source_sha256) is not None
            and sha256(source_raw).hexdigest() == args.source_sha256, 'Actual reviewed source.json SHA256 mismatch')
    source = json.loads(source_raw)
    require(all(isinstance(source.get(key), str) and re.fullmatch(r'[a-f0-9]{40}', source[key]) is not None
                for key in ('candidate', 'tree', 'baseline')), 'Actual full source SHAs required')
    require(source['baseline'] == BASELINE and source['version'] == '1.22.31' and source['build'] == 2246
            and source['pr'] == 335 and source.get('supersedes') == R2_HEAD
            and source['candidate'] != R2_HEAD and source['tree'] != R2_TREE, 'Reviewed new R3 source/release identity required')
    checked(args.receipt)
    receipt_path = BASE / args.receipt
    receipt_sum = receipt_path.with_name(receipt_path.name + '.sha256')
    require(receipt_path.suffix == '.json' and receipt_path.resolve().is_relative_to(BASE.resolve())
            and not receipt_path.resolve().is_relative_to(REPO.resolve()), 'Receipt must be R3 JSON outside the evidence worktree')
    require(not any(p.is_symlink() for p in receipt_path.parents), 'Receipt ancestor is a symlink')
    require(not receipt_path.exists() and not receipt_path.is_symlink() and not receipt_sum.exists()
            and not receipt_sum.is_symlink(), 'Never overwrite a readback receipt or its sidecar')
    require(ROOT.is_dir() and not ROOT.is_symlink() and not any(p.is_symlink() for p in ROOT.parents), 'Unsafe local prefix')

    def local(name):
        checked(name)
        path = ROOT / name
        require(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents), 'Missing or symlink payload')
        raw = path.read_bytes()
        require(raw == git('show', commit + ':' + PREFIX + '/' + name, binary=True), 'Local payload differs from explicit publication commit')
        return raw

    manifest_raw = local('publication-manifest.json')
    manifest = json.loads(manifest_raw)
    require(manifest['schema'] == 'dtos-released-evidence-v1' and manifest['prefix'] == PREFIX
            and manifest['source'] == source and manifest['source_input_sha256'] == args.source_sha256,
            'Wrong released source/prefix/schema')
    require(local('final/source.json') == source_raw, 'Published original source input differs from reviewed R3/source.json')
    parent = manifest['evidence_parent_commit']
    require(re.fullmatch(r'[a-f0-9]{40}', parent) is not None and parent != commit, 'Invalid recorded evidence parent')
    subprocess.run(['git', 'merge-base', '--is-ancestor', parent, commit], cwd=REPO, check=True)
    changed = git('diff', '--name-only', parent, commit).splitlines()
    require(changed and all(name.startswith(PREFIX + '/') for name in changed),
            'Publication must change only the new released evidence prefix')
    require(not git('ls-tree', '-r', '--name-only', parent, '--', PREFIX), 'Released prefix already existed at recorded parent')
    rows = manifest['files']
    names = [checked(row['name']) for row in rows]
    require(len(set(names)) == len(names) and 'publication-manifest.json' not in names and 'SHA256SUMS' not in names,
            'Duplicate/self-referential manifest rows')
    require(manifest['payload_files'] == len(rows) and manifest['payload_bytes'] == sum(row['bytes'] for row in rows),
            'Derived manifest counts disagree')
    files = []
    for row in rows:
        require(type(row['bytes']) is int and row['bytes'] >= 0 and re.fullmatch(r'[a-f0-9]{64}', row['sha256']) is not None,
                'Invalid expected payload bound/digest')
        raw = local(row['name'])
        require(len(raw) == row['bytes'] and sha256(raw).hexdigest() == row['sha256'], 'Local manifest integrity mismatch')
        files.append({key: row[key] for key in ('name', 'bytes', 'sha256')})
    sums_raw = local('SHA256SUMS')
    sum_rows = [line.split('  ', 1) for line in sums_raw.decode('utf-8').splitlines()]
    require(all(len(row) == 2 for row in sum_rows), 'Malformed public checksum sidecar')
    sums = {name: digest for digest, name in sum_rows}
    expected_sums = {row['name']: row['sha256'] for row in rows}
    expected_sums['publication-manifest.json'] = sha256(manifest_raw).hexdigest()
    require(len(sums) == len(sum_rows) and sums == expected_sums, 'Public checksum sidecar population/digests disagree')
    for name, raw in (('publication-manifest.json', manifest_raw), ('SHA256SUMS', sums_raw)):
        files.append({'name': name, 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()})
    expected_names = {row['name'] for row in files}
    actual_paths = list(ROOT.rglob('*'))
    require(not any(path.is_symlink() for path in actual_paths), 'Symlink anywhere in prefix')
    actual_names = {path.relative_to(ROOT).as_posix() for path in actual_paths if path.is_file()}
    committed_names = {name.removeprefix(PREFIX + '/') for name in git('ls-tree', '-r', '--name-only', commit, '--', PREFIX).splitlines()}
    require(actual_names == committed_names == expected_names, 'Unmanifested/missing local or committed file')
    base_url = 'https://raw.githubusercontent.com/Richarddavis47/dtos/' + commit + '/' + PREFIX + '/'
    started = datetime.now(timezone.utc).isoformat()

    def verify(row):
        url = base_url + quote(row['name'], safe='/')
        attempts = []
        for attempt in range(1, 4):
            tick = time.monotonic()
            try:
                with httpx.stream('GET', url, follow_redirects=False, auth=Anonymous(),
                                  timeout=httpx.Timeout(45, connect=12),
                                  headers={'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache',
                                           'User-Agent': 'DTOS-released-evidence-byte-verifier/1'}) as response:
                    require(str(response.url) == url and not response.history, 'Unexpected redirect or URL')
                    require('Authorization' not in response.request.headers and 'Cookie' not in response.request.headers,
                            'Anonymous request contract failed')
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise RuntimeError('Retryable HTTP status ' + str(response.status_code))
                    require(response.status_code == 200, 'HTTP status ' + str(response.status_code))
                    require(response.headers.get('Content-Encoding', 'identity').lower() == 'identity',
                            'Encoded body rejected; raw evidence bytes required')
                    length = response.headers.get('Content-Length')
                    require(length is None or (length.isdigit() and int(length) == row['bytes']), 'HTTP length disagrees with expected bound')
                    count, hasher = 0, sha256()
                    for chunk in response.iter_raw(65536):
                        count += len(chunk)
                        require(count <= row['bytes'], 'Published body exceeded exact expected byte bound')
                        hasher.update(chunk)
                    actual = hasher.hexdigest()
                    require(count == row['bytes'] and actual == row['sha256'], 'Published raw byte count/digest mismatch')
                    attempts.append({'attempt': attempt, 'status': 200, 'passed': True, 'seconds': round(time.monotonic() - tick, 4)})
                    return {**row, 'url': url, 'https_raw_bytes_verified': count, 'https_sha256_verified': actual, 'attempts': attempts}
            except (httpx.HTTPError, RuntimeError) as error:
                # Never retain response bodies, headers, redirect locations, credentials or raw stderr.
                attempts.append({'attempt': attempt, 'passed': False, 'error_class': type(error).__name__,
                                 'seconds': round(time.monotonic() - tick, 4)})
                if attempt == 3:
                    raise RuntimeError('HTTPS verification failed for ' + row['name'] + '; class ' + type(error).__name__) from None
                time.sleep(attempt)
        raise RuntimeError('No verification outcome')

    first = next(row for row in files if row['name'] == 'publication-manifest.json')
    results = [verify(first)]
    print(json.dumps({'verified_files': len(results), 'total_files': len(files), 'manifest_https_preflight': 'passed'}), flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [pool.submit(verify, row) for row in files if row['name'] != first['name']]
        for future in as_completed(pending):
            results.append(future.result())
            if len(results) % 25 == 0 or len(results) == len(files):
                print(json.dumps({'verified_files': len(results), 'total_files': len(files)}), flush=True)
    require(len(results) == len(files) and {row['name'] for row in results} == expected_names, 'Incomplete HTTPS readback')
    require(git('rev-parse', 'HEAD') == commit and not git('status', '--porcelain', '--untracked-files=all'), 'Evidence worktree changed during readback')
    receipt = {'schema': 'dtos-released-evidence-https-receipt-v1', 'all_published_raw_bytes_verified': True,
               'publication_commit': commit, 'publication_tree': git('rev-parse', commit + '^{tree}'), 'branch': BRANCH,
               'prefix': PREFIX, 'source': manifest['source'], 'source_input_sha256': args.source_sha256,
               'merge_commit': manifest['merge_commit'],
               'manifest_sha256': sha256(manifest_raw).hexdigest(), 'sha256_sidecar': sha256(sums_raw).hexdigest(),
               'verification_started_at_utc': started, 'verification_finished_at_utc': datetime.now(timezone.utc).isoformat(),
               'payload_files': len(rows), 'payload_bytes': manifest['payload_bytes'], 'all_published_files': len(results),
               'all_published_bytes': sum(row['https_raw_bytes_verified'] for row in results),
               'public_tree_url': 'https://github.com/Richarddavis47/dtos/tree/' + commit + '/' + PREFIX,
               'method': 'Every payload, manifest and checksum sidecar streamed anonymously over HTTPS from explicit immutable commit URLs; no redirects, Authorization or Cookie; identity encoding, exact byte caps and SHA256 over iter_raw bytes; three bounded readers.',
               'scope': 'Published evidence byte availability/integrity only. Native publisher all-attachment readback, Cloud certificate/API digest checks, source gates and bounded production smoke remain their distinct original evidence; no live owner/physical Safari acceptance is inferred.',
               'files': sorted(results, key=lambda row: row['name'])}
    raw = (json.dumps(receipt, indent=2) + '\n').encode()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    with receipt_path.open('xb') as stream:
        stream.write(raw)
    with receipt_sum.open('xb') as stream:
        stream.write((sha256(raw).hexdigest() + '  ' + receipt_path.name + '\n').encode())
    print(json.dumps({'publication_commit': commit, 'all_published_files': len(results),
                      'all_published_bytes': receipt['all_published_bytes'], 'receipt': str(receipt_path),
                      'receipt_sha256': sha256(raw).hexdigest(), 'all_published_raw_bytes_verified': True}, indent=2), flush=True)


if __name__ == '__main__':
    main()
