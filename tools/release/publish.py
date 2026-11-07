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
    '.github/release-plans/2239.json', '.github/release-plans/2239-recovery.zip',
    '.github/release-plans/2239-prior.zip',
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


def verify_canonical_sums(archive, manifest, prefix=''):
    name = prefix + 'SHA256SUMS'
    require(name in archive.namelist(), 'Canonical checksum list missing')
    entries = [line.split('  ', 1) for line in archive.read(name).decode().splitlines()]
    require(all(len(row) == 2 for row in entries), 'Malformed canonical checksum list')
    expected = {row['name']: row['sha256'] for row in manifest}
    require(len(entries) == len(expected) and {row[1] for row in entries} == set(expected),
            'Canonical checksum population mismatch')
    for sha, member in entries:
        require(sha == expected[member] and hashlib.sha256(archive.read(prefix + member)).hexdigest() == sha,
                'Canonical checksum list mismatch')


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
        verify_canonical_sums(archive, manifest)
        events = Counter(json.loads(line)['event'] for line in archive.read('tests.jsonl').splitlines())
        require(events['start'] == events['stop'] == plan['canonical_tests'] and not any(events[x] for x in ('failure', 'error', 'skip')), 'Incomplete/failed canonical tests')
        trace = [json.loads(line) for line in archive.read('canonical-trace.jsonl').splitlines()]
        require(any(x.get('event') == 'validator_final_summary' and x.get('gates') == 10 for x in trace), 'Ten-gate final summary missing')
        completed = [x for x in trace if x.get('event') == 'validation_child_completed']
        require(len(completed) == 10 and all(x['return_code'] == 0 for x in completed), 'Incomplete canonical gate execution')
        return result


def verify_current_history(path, plan):
    """Verify source-pinned restored-history browser controls, never live proof."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read('browser.json'))
        require(report.get('head') == plan['candidate'] and report.get('tree') == plan['tree']
                and report.get('working_tree_clean') is True, 'Current history source mismatch')
        rows = report.get('records', [])
        expected = {(league, width, height) for league in ('Granite-shaped', 'Day-shaped', 'Arkham-shaped')
                    for width, height in ((320, 432), (375, 667), (390, 844), (1280, 900))}
        require(len(rows) == 12 and {(r['league_control'], r['width'], r['height']) for r in rows} == expected,
                'Current history browser population incomplete')
        require(all(r.get('retrieved') == [1, 2, 3, 5, 6, 7, 8] and r.get('failed') == [4]
                    and r.get('keyboard') is True and r.get('overflow') is False
                    and r.get('extra_disclosure_requests') == 0
                    and r.get('touch_emulated') is (r['width'] < 1000) for r in rows),
                'Current history lifecycle or accessibility control failed')
        pngs = [n for n in archive.namelist() if n.endswith('.png')]
        require(len(pngs) == 12 and all(archive.read(n).startswith(b'\x89PNG\r\n\x1a\n') for n in pngs),
                'Current history screenshots missing')
    return report


def verify_history_followthrough(path, plan):
    """Validate the actual origin/branch/Back sequence on the pinned source."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read('browser.json'))
        require(report.get('head') == plan['candidate'] and report.get('tree') == plan['tree']
                and report.get('working_tree_clean') is True, 'History follow-through source mismatch')
        rows = report.get('records', [])
        controls = ('Day retained chain plus disposable pagination', 'Arkham retained history and scope reset')
        expected = {(control, w, h) for control in controls
                    for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))}
        require(len(rows) == 8 and {(r['control'], r['width'], r['height']) for r in rows} == expected,
                'History follow-through browser population incomplete')
        require(report.get('errors') == [] and report.get('server_thread_reaped') is True,
                'History browser error or server cleanup failed')
        for row in rows:
            require(row.get('overflow') is False, 'History browser overflow')
            if row['control'] == controls[1]:
                require(row.get('source_qualified') is True and row.get('old_league_replay') is False,
                        'History selected-league qualification failed')
                continue
            chain = row.get('chain', [])
            require(len(chain) == 16 and chain[0].startswith('/history/team/'), 'History journey incomplete')
            history, player = chain[0], chain[4]
            root = '/trades/history/' + row['original']
            pick = '/picks/' + row['pick'] + '?from_trade=' + row['original']
            later = '/trades/history/' + row['later'] + '?from_trade=' + row['original']
            require(player.startswith('/players/') and player.endswith('?from_trade=' + row['original']),
                    'History player origin missing')
            require(chain[:15] == [history, history+'?events_page=2', root, pick, player, later,
                                  root, later, player, pick, root, history+'?events_page=2', history,
                                  history+'?events_page=2', history+'?events_page=2']
                    and chain[15].startswith('/history/team/') and chain[15] != history,
                    'History branch, origin, pagination or Forward/reload sequence changed')
            require(row.get('pagination_return') is True and row.get('forward_reload') is True
                    and row.get('keyboard') is True and row.get('touch_emulated') is (row['width'] < 500)
                    and row.get('extra_disclosure_requests') == 0, 'History interaction control failed')
        requests = report.get('requests', [])
        require(requests and any(r['path'] == '/api/account/navigation-context' and r['status'] == 200 for r in requests)
                and not any('/sync' in r['path'] or '/trades/recommended' in r['path'] for r in requests),
                'History verified context missing or unexpected heavyweight request')
        pngs = [n for n in archive.namelist() if n.endswith('.png')]
        require(len(pngs) == 8 and all(archive.read(n).startswith(b'\x89PNG\r\n\x1a\n') for n in pngs),
                'History follow-through screenshots missing')
    return report


def verify_market_history(path, plan):
    """Require actual cache transitions on the pinned source, never live proof."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read('browser.json'))
        require(report.get('head') == plan['candidate'] and report.get('tree') == plan['tree']
                and report.get('working_tree_clean') is True, 'Market history source mismatch')
        rows = report.get('records', [])
        expected = {(league, w, h) for league in ('1314695233040052224', '1319750579458686976')
                    for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))}
        require(len(rows) == 8 and {(r['league'], *r['viewport']) for r in rows} == expected,
                'Market history browser population incomplete')
        require(report.get('errors') == [] and report.get('browser_closed') is True,
                'Market history browser errors or cleanup failed')
        for row in rows:
            require(row.get('before') == dict(magnitude=100, checkpoint_count=2), 'Market baseline changed')
            updated, boundary = row.get('updated', {}), row.get('boundary', {})
            require(updated.get('magnitude') == 120 and updated.get('checkpoint_count') == 3
                    and updated.get('comparison_start_at') == '2026-06-01T12:00:00Z'
                    and updated.get('comparison_end_at') == '2026-08-31T12:00:00+00:00'
                    and updated.get('comparison_scope') == 'historical_to_current'
                    and updated.get('comparison_units') == '0-1000'
                    and updated.get('confidence') == 'low', 'Market comparison evidence mismatch')
            require(boundary.get('magnitude') is None and boundary.get('checkpoint_count') == 4
                    and boundary.get('direction') == 'not_comparable'
                    and boundary.get('comparison_reasons') == ['INCOMPATIBLE_OBSERVATION_BOUNDARY'],
                    'Market compatibility boundary lost')
            require(row.get('price_publication_unchanged') is True and row.get('overflow') is False
                    and row.get('keyboard') is True and row.get('disclosure_extra_requests') == 0
                    and row.get('source_catalogue_not_participation') is True,
                    'Market cache, provider or accessibility control failed')
        for key in ('before_memory', 'after_memory'):
            memory = report.get(key, {})
            require(memory.get('cgroup_limit_bytes') == 2147483648
                    and not memory.get('cgroup_memory_events', {}).get('oom')
                    and not memory.get('cgroup_memory_events', {}).get('oom_kill'),
                    'Market constrained memory evidence failed')
        requests = report.get('requests', [])
        require(requests and not any('/sync' in r['path'] or '/trades/recommended' in r['path']
                                    or '/fois/rebuild' in r['path'] for r in requests),
                'Unexpected heavyweight Market request')
        pngs = [n for n in archive.namelist() if n.endswith('.png')]
        require(len(pngs) == 24 and all(archive.read(n).startswith(b'\x89PNG\r\n\x1a\n') for n in pngs),
                'Market history screenshots missing')
    return report


def verify_current_production(path, plan):
    """Pinned source-to-screen evidence, not a claim of live league recovery."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        report = json.loads(archive.read('browser.json'))
        require(report.get('head') == plan['candidate'] and report.get('tree') == plan['tree']
                and report.get('working_tree_clean') is True, 'Production coverage source mismatch')
        rows = report.get('records', [])
        expected = {(league, w, h) for league in ('1314695233040052224', '1319750579458686976')
                    for w, h in ((320, 432), (375, 667), (390, 844), (1280, 900))}
        require(len(rows) == 8 and {(r['league'], *r['viewport']) for r in rows} == expected,
                'Production coverage browser population incomplete')
        require(report.get('errors') == [] and report.get('browser_closed') is True,
                'Production coverage browser errors or cleanup failed')
        for row in rows:
            complete, partial = row.get('complete', {}), row.get('partial', {})
            require(complete.get('fantasy_points') == 18 and complete.get('observation_count') == 8
                    and complete.get('scored_count') == 8 and complete.get('season') == 2026
                    and complete.get('weeks') == list(range(1, 9)), 'Complete production evidence mismatch')
            require(partial.get('fantasy_points') is None and partial.get('observation_count') == 8
                    and partial.get('scored_count') == 7 and partial.get('missing_components') == ['conflicting_sleeper_scores'],
                    'Missing production incorrectly calculated')
            require(row.get('retained_failure') is True and row.get('keyboard') is True
                    and row.get('overflow') is False and row.get('extra_disclosure_requests') == 0
                    and row.get('touch_emulated') is (row['viewport'][0] < 1000),
                    'Production retained-data or accessibility control failed')
        for key in ('before_memory', 'after_memory'):
            memory = report.get(key, {})
            require(memory.get('cgroup_limit_bytes') == 2147483648
                    and not memory.get('cgroup_memory_events', {}).get('oom')
                    and not memory.get('cgroup_memory_events', {}).get('oom_kill'),
                    'Production constrained memory evidence failed')
        requests = report.get('requests', [])
        require(requests and not any('/sync' in r['path'] or '/trades/recommended' in r['path']
                                    or '/fois/rebuild' in r['path'] for r in requests),
                'Unexpected heavyweight production request')
        pngs = [n for n in archive.namelist() if n.endswith('.png')]
        require(len(pngs) == 24 and all(archive.read(n).startswith(b'\x89PNG\r\n\x1a\n') for n in pngs),
                'Production coverage screenshots missing')
    return report


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


def verify_restoration_unused(path, plan):
    """Exact-source completion and deferral; no private Granite recovery claim."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('evidence/result.json'))
        require(result.get('head') == plan['candidate'] and result.get('tree') == plan['tree']
                and result.get('working_tree_clean') is True, 'Restoration source mismatch')
        require(result.get('passed') is True and result.get('scratch_removed') is True
                and result.get('explicit_retry_completed') is True
                and result.get('expired_released_active_and_fresh_preserved') is True
                and result.get('fois_reserve_preserved') is True, 'Restoration execution or ownership incomplete')
        before, after = result['before_plan'], result['recovery']
        require(before['would_admit'] is False and after['would_admit'] is True
                and before['required_bytes'] == after['required_bytes']
                and after['expired_entries'] == 3 and result['raw_bytes_released'] > 0,
                'Restoration guard or unused-reference recovery not established')
        require(result['unsafe_pressure_deferred']['would_admit'] is False
                and result['fois_reserved_plan']['would_admit'] is False
                and result['fois_reserved_plan']['required_bytes'] > before['required_bytes'],
                'Restoration pressure or FOIS safeguards incomplete')
        require(0 < result['kernel_lifetime_peak_bytes'] <= 2147483648
                and result['samples'] and all(x['cgroup_limit_bytes'] == 2147483648
                    and not x['cgroup_memory_events'].get('oom')
                    and not x['cgroup_memory_events'].get('oom_kill') for x in result['samples']),
                'Restoration constrained memory evidence failed')
        require(all(x.get('resource_tracker') is True for x in result['cleanup_processes']),
                'Restoration retained application workers')
        require(len(result['liveness']) == 4 and all(0 <= x['server_ms'] < 500
                and x['client_ms'] >= 0 for x in result['liveness']), 'Restoration liveness failed')
        checks = [line.split('  ', 1) for line in archive.read('SHA256SUMS').decode().splitlines()]
        require(len(checks) == 3 and {n for _,n in checks} == {'evidence/result.json','raw.log','prior-study.zip'},
                'Restoration checksum manifest incomplete')
        for expected, name in checks:
            require(hashlib.sha256(archive.read(name)).hexdigest() == expected, 'Restoration checksum mismatch')
        require(hashlib.sha256(archive.read('prior-study.zip')).hexdigest()
                == 'df5c88eda13a0671104c76a943b05032d7adfa089d11e738785b11e35a932439'
                == result['prior_archive_sha256'], 'Restoration prior input changed')
    return result


def verify_actuals_restoration(path, plan):
    result = verify_restoration_unused(path, plan)
    actual = result.get('native_actuals') or {}
    require(actual.get('passed') is True and actual.get('method') == 'sleeper-matchup-actuals-v1'
            and actual.get('source_generation') and actual['source_generation'] == actual.get('admitted_generation')
            and actual.get('expected_first_scores') == [0, -2.125]
            and actual.get('admitted_first_scores') == actual['expected_first_scores']
            and actual.get('league_id') and actual.get('season') and actual.get('scoring_fingerprint')
            and type(actual.get('observations')) is int and actual['observations'] > 0,
            'Native actuals restoration parity or source identity missing')
    return result


def verify_resident_refresh(path, plan):
    """Real terminal ownership, active readers and capacity recovery; not live parity."""
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('evidence/result.json'))
        require(result.get('schema') == 'resident-refresh-ownership-v2'
                and result.get('passed') is True and result.get('head') == plan['candidate']
                and result.get('tree') == plan['tree'] and result.get('working_tree_clean') is True,
                'Resident refresh source or completion mismatch')
        require(result.get('cgroup_limit') == 2147483648 and result.get('swap_limit') == 0
                and result.get('cpus') == 2 and result.get('network') == 'none'
                and result.get('children_after') == [] and result.get('scratch_removed') is True
                and result.get('source_values_preserved') is True, 'Resident refresh resource/cleanup proof missing')
        cases = result.get('cases', [])
        require(len(cases) == 4 and [(x.get('name'), x.get('failed_refresh'), x.get('reader')) for x in cases[:3]]
                == [('oneqb', False, False), ('oneqb', True, False), ('superflex', False, True)],
                'Resident refresh case population mismatch')
        for case in cases[:3]:
            require(case.get('completed') is True and case.get('invalid_restore_preserved_current') is True
                    and case.get('repeated_switches') == 3 and case.get('cancellation_writer_drained') is True
                    and case.get('old_released_without_reader') is (not case['reader'])
                    and re.fullmatch('[0-9a-f]{64}', case.get('source_digest', '')),
                    'Resident refresh real execution/ownership missing')
        reader = cases[2]
        require(all(reader.get(k) is True for k in ('pressure_deferred', 'fois_protected', 'recovery_completed'))
                and type(reader.get('relieved_fixture_bytes')) is int and reader['relieved_fixture_bytes'] > 0
                and reader.get('owner_release_plan', {}).get('telemetry_valid') is True
                and reader.get('recovery_plan', {}).get('would_admit') is True,
                'Resident refresh deferral/FOIS/recovery missing')
        global_owner = cases[3]
        require(global_owner.get('name') == 'global-evidence'
                and all(global_owner.get(k) is True for k in (
                    'completed', 'old_released_without_reader', 'source_acquisition_mocked',
                    'source_restoration_completed', 'scheduler_cancelled'))
                and re.fullmatch('[0-9a-f]{64}', global_owner.get('source_digest', '')),
                'Global scheduler ownership/restoration proof missing')
        samples = result.get('samples', [])
        require(samples and all(x.get('cgroup_limit_bytes') == 2147483648
                and not x.get('cgroup_memory_events', {}).get('oom_kill') for x in samples),
                'Resident refresh cgroup evidence missing')
        require(result.get('liveness') and all(isinstance(x.get('server_ms'), (int, float)) and 0 <= x['server_ms'] < 500
                for x in result['liveness']), 'Resident refresh liveness failed')
        for line in archive.read('SHA256SUMS').decode().splitlines():
            expected, name = line.split('  ', 1)
            require(name in {'evidence/result.json', 'raw.log'}
                    and hashlib.sha256(archive.read(name)).hexdigest() == expected,
                    'Resident refresh checksum mismatch')
        require({line.split('  ', 1)[1] for line in archive.read('SHA256SUMS').decode().splitlines()}
                == {'evidence/result.json', 'raw.log'}, 'Resident refresh checksum population missing')
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
        require('local-canonical/manifest.json' in archive.namelist(), 'Local canonical manifest missing')
        manifest = json.loads(archive.read('local-canonical/manifest.json'))
        require(len(manifest) == plan['local_canonical_entries'], 'Local canonical manifest population mismatch')
        names = set()
        for entry in manifest:
            require(entry['name'] not in names, 'Duplicate local canonical manifest row')
            names.add(entry['name'])
            payload = archive.read('local-canonical/' + entry['name'])
            require(len(payload) == entry['bytes'] and hashlib.sha256(payload).hexdigest() == entry['sha256'],
                    'Local canonical payload checksum mismatch')
        verify_canonical_sums(archive, manifest, 'local-canonical/')
    return result


def verify_prior_evidence(path, plan):
    """Prior attempts are integrity evidence, never substitutes for final gates."""
    require(digest(path) == plan['prior_evidence_sha256'], 'Prior evidence archive changed')
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        meta = json.loads(archive.read('prior-manifest.json'))
        require(meta['candidate'] == plan['candidate'] and meta['tree'] == plan['tree']
                and meta['scope'] == 'prior-attempts-only', 'Prior evidence association mismatch')
        names = set()
        for entry in meta['files']:
            require(entry['name'] not in names, 'Duplicate prior manifest row')
            names.add(entry['name'])
            data = archive.read(entry['name'])
            require(len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256'],
                    'Prior evidence payload mismatch')
        require(set(archive.namelist()) == names | {'prior-manifest.json'}, 'Unmanifested prior evidence')


def verify_preflight(path, plan):
    """Exact-source metadata-only admission under the actual 2 GiB limit."""
    verify_zip(path)
    expected_cases = {
        'healthy': ('would_admit', 'sufficient_headroom'),
        'capacity_deferred': ('would_defer', 'insufficient_headroom'),
        'pressure_relieved': ('would_admit', 'sufficient_headroom'),
        'fois_reserve_protected': ('would_defer', 'insufficient_headroom'),
        'fois_released_same_pressure': ('would_admit', 'sufficient_headroom'),
    }
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('result.json'))
        require(result['head'] == plan['candidate'] and result['tree'] == plan['tree'], 'Preflight source mismatch')
        require(result.get('passed') is True and result.get('complete') is True, 'Preflight incomplete')
        require(result.get('enforced_limit') == 2147483648 and result.get('swap_limit') == 0, 'Preflight enforced limit missing')
        require(type(result.get('kernel_peak_bytes')) is int and 0 < result['kernel_peak_bytes'] <= 2147483648,
                'Preflight exceeded enforced memory')
        require(result.get('scratch_removed') is True and result.get('children_after') == []
                and result.get('runtime_population_unchanged') is True
                and result.get('no_private_payload_decoded') is True, 'Preflight cleanup or read-only proof missing')
        require(result.get('guarded_operation_calls') == [0, 0, 0, 0, 0], 'Preflight started prohibited work')
        memory = result.get('final_memory') or {}
        require(memory.get('cgroup_limit_bytes') == 2147483648
                and not (memory.get('cgroup_memory_events') or {}).get('oom')
                and not (memory.get('cgroup_memory_events') or {}).get('oom_kill'), 'Preflight final memory evidence failed')
        rows = result.get('cases') or []
        require(len(rows) == len(expected_cases) and Counter(r.get('name') for r in rows) == Counter(expected_cases.keys()),
                'Preflight cases missing or duplicated')
        by_name = {row['name']: row for row in rows}
        for name, expected in expected_cases.items():
            response = by_name[name].get('response') or {}
            require((response.get('verdict'), response.get('reason')) == expected, 'Preflight verdict evidence mismatch')
            require(response.get('advisory_only') is True and response.get('non_atomic') is True
                    and response.get('recheck_required') is True, 'Preflight falsely grants admission')
            process = response.get('process') or {}
            require(type(process.get('pid')) is int and process['pid'] > 0
                    and process.get('lifecycle_scope') == 'serving_process_only'
                    and process.get('other_worker_idleness') == 'not_established', 'Preflight process scope unsupported')
            require(response.get('assessment_scope') == 'saved_cache_resource_and_coordination_admission_only',
                    'Preflight scope changed')
            cache = response.get('cache') or {}
            require(cache.get('size_bytes') == 23048708 and cache.get('generation_pinned') is True
                    and cache.get('path_matches_pinned_generation_at_end') is True
                    and cache.get('payload_readability') == 'not_checked'
                    and cache.get('content_compatibility') == 'not_evaluated', 'Preflight cache or compatibility claim unsupported')
            life = response.get('lifecycle') or {}
            require(life.get('available') is True and life.get('cache_lease_conflict') is False,
                    'Preflight is not a memory-only admission control')
            reserved = name == 'fois_reserve_protected'
            require((life.get('heavy_work') or {}).get('fois_generation') is reserved, 'Preflight FOIS reservation mismatch')
            memory = response.get('memory') or {}
            require(memory.get('scope') == 'shared_container' and memory.get('cgroup_limit_bytes') == 2147483648
                    and type(memory.get('cgroup_current_bytes')) is int
                    and 0 <= memory['cgroup_current_bytes'] <= 2147483648, 'Preflight container scope unsupported')
            events = memory.get('memory_events') or {}
            require(not events.get('oom') and not events.get('oom_kill'), 'Preflight case OOM')
            capacity = response.get('capacity') or {}
            working = 16 * 23048708
            safety, fois = (256 * 1024**2, 512 * 1024**2) if reserved else (128 * 1024**2, 0)
            require(capacity.get('telemetry_valid') is True and capacity.get('working_bytes') == working
                    and capacity.get('safety_bytes') == safety and capacity.get('fois_working_bytes') == fois
                    and capacity.get('required_bytes') == working + safety + fois
                    and capacity.get('effective_limit_bytes') == 2147483648
                    and capacity.get('headroom_bytes') == 2147483648 - memory['cgroup_current_bytes'],
                    'Preflight changed the restoration reservation')
            require(capacity.get('would_admit') is (expected[0] == 'would_admit')
                    and capacity['would_admit'] is (capacity['headroom_bytes'] >= capacity['required_bytes']),
                    'Preflight headroom verdict mismatch')
        before = by_name['fois_reserve_protected']['harness_padding_bytes']
        require(type(before) is int and before > 0
                and before == by_name['fois_released_same_pressure']['harness_padding_bytes'],
                'Preflight FOIS recovery changed the harness pressure')
        liveness = result.get('liveness') or []
        require(len(liveness) == 5 and Counter(x.get('case') for x in liveness) == Counter(expected_cases.keys())
                and all(type(x.get('server_ms')) in (int, float) and 0 <= x['server_ms'] < 500
                        and type(x.get('client_ms')) in (int, float) and x['client_ms'] >= 0
                        for x in liveness), 'Preflight server liveness failed')
        sums = [line.split('  ', 1) for line in archive.read('SHA256SUMS').decode().splitlines()]
        require(len(sums) == 2 and {x[1] for x in sums} == {'result.json', 'raw.log'}, 'Preflight checksum population mismatch')
        for expected, name in sums:
            require(hashlib.sha256(archive.read(name)).hexdigest() == expected, 'Preflight payload checksum mismatch')
        return result


def verify_league_entry(path, plan):
    verify_zip(path)
    with zipfile.ZipFile(path) as archive:
        result = json.loads(archive.read('result.json'))
        require(result['head'] == plan['candidate'] and result['tree'] == plan['tree'], 'League entry source mismatch')
        require(result.get('passed') is True and result.get('complete') is True
                and result.get('working_tree_clean') is True, 'League entry incomplete or dirty')
        require(result.get('warm_cold_saved_http') == 'passed'
                and result.get('one_qb_k_def_http_evaluation') == 'passed', 'League entry HTTP controls missing')
        require(result.get('pressure_deferred') is True and result.get('recovery_completed') is True
                and result.get('worker_reaped') is True, 'League entry deferral/recovery/cleanup missing')
        require(result.get('active_fois_commitment_deferred') is True
                and result.get('after_fois_release_same_pressure_completed') is True,
                'Outstanding FOIS reserve or same-pressure recovery not established')
        require(result['cgroup_lifetime_peak'] <= 2147483648, 'League entry exceeded enforced memory')
        samples = result['samples']
        require(samples and all(x['cgroup_limit_bytes'] == 2147483648
                and not x['cgroup_memory_events'].get('oom') and not x['cgroup_memory_events'].get('oom_kill')
                and x['cgroup_current_bytes'] <= 2147483648 for x in samples), 'League entry memory evidence failed')
        labels = {x['label'] for x in samples}
        require({'active_fois_worker','before_large_restore_with_fois','after_large_restore_with_fois',
                 'unsafe_pressure','active_fois_outstanding_reserve','same_pressure_after_fois_release',
                 'pressure_relieved','recovered_restore','cleanup'} <= labels, 'League entry lifecycle evidence incomplete')
        require(result['liveness'] and len(result['liveness']) == 5
                and all(type(x.get('server_ms')) in (int,float) and 0 <= x['server_ms'] < 500
                        and type(x.get('client_ms')) in (int,float) and x['client_ms'] >= 0
                        for x in result['liveness']), 'League entry server liveness failed')
        checks = [line.split('  ',1) for line in archive.read('SHA256SUMS').decode().splitlines()]
        require({x[1] for x in checks} == {'result.json','raw.log','preparation.log'} and len(checks) == 3,
                'League entry attachment manifest incomplete')
        for expected, name in checks:
            require(hashlib.sha256(archive.read(name)).hexdigest() == expected, 'League entry checksum mismatch')
        return result


def prior_attempt_record(repo, reference):
    """Keep a failed historical attempt distinct from a later successful rerun."""
    require(isinstance(reference, dict) and set(reference) == {'id', 'attempt'}, 'Invalid prior attempt reference')
    run_id, attempt = reference['id'], reference['attempt']
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0,
            'Invalid prior attempt identity')
    run = api(repo + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt))
    require(run['id'] == run_id and run['run_attempt'] == attempt,
            'Prior attempt API identity mismatch')
    return {key: run[key] for key in ('id', 'name', 'head_sha', 'status', 'conclusion', 'html_url', 'run_attempt')}


def verify_handoff(data, plan):
    require(len(data) <= 128 * 1024 and not TOKEN.search(data), 'Unsafe handoff attachment')
    require(plan['candidate'].encode() in data and plan['tree'].encode() in data,
            'Handoff describes another source')
    return data


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
    require(len(records) == 13 and product_job, 'Required gate population mismatch')
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
        if expected['file'] == 'actuals-restoration-original.zip':
            verify_actuals_restoration(path, plan)
        if expected['file'] == 'restoration-unused-original.zip':
            verify_restoration_unused(path, plan)
        if expected['file'] == 'resident-refresh-original.zip':
            verify_resident_refresh(path, plan)
        if expected['file'] == 'trade-resource-original.zip':
            verify_trade_resource(path, plan)
        if expected['file'] == 'league-entry-original.zip':
            verify_league_entry(path, plan)
        if expected['file'] == 'preflight-original.zip':
            verify_preflight(path, plan)
        if expected['file'] == 'current-history-original.zip':
            verify_current_history(path, plan)
        if expected['file'] == 'current-production-coverage-original.zip':
            verify_current_production(path, plan)
        if expected['file'] == 'market-history-coverage-original.zip':
            verify_market_history(path, plan)
        if expected['file'] == 'history-followthrough-original.zip':
            verify_history_followthrough(path, plan)
        if expected['file'].startswith('lifecycle-'):
            with zipfile.ZipFile(path) as archive:
                result = json.loads(archive.read('summary.json'))
            require(result['passed'] is True and result['completed'] is True and result['exit_code'] == 0 and result['memory_max'] == 2147483648, 'Lifecycle acceptance missing')
    require(canonical is not None, 'Canonical artifact absent')
    recovery = Path(plan['recovery_file'])
    require(digest(recovery) == plan['recovery_sha256'], 'Recovery evidence changed')
    local_canonical = verify_local_recovery(recovery, plan)
    with zipfile.ZipFile(recovery) as archive:
        local_preflight = root / 'local-preflight.zip'
        make_zip(local_preflight, {name: archive.read('local-preflight/' + name)
                                  for name in ('result.json', 'raw.log', 'SHA256SUMS')})
        (assets / 'SCOUT_HANDOFF.md').write_bytes(verify_handoff(archive.read('SCOUT_HANDOFF.md'), plan))
        local_unused = root / 'local-restoration-unused.zip'
        make_zip(local_unused, {name: archive.read('local-restoration-unused/' + name)
                               for name in ('evidence/result.json', 'raw.log', 'prior-study.zip', 'SHA256SUMS')})
    local_preflight_result = verify_preflight(local_preflight, plan)
    local_unused_result = verify_actuals_restoration(local_unused, plan)
    with zipfile.ZipFile(recovery) as archive:
        local_resident = root / 'local-resident-refresh.zip'
        make_zip(local_resident, {name: archive.read('local-resident-refresh/' + name)
                                 for name in ('evidence/result.json', 'raw.log', 'SHA256SUMS')})
    local_resident_result = verify_resident_refresh(local_resident, plan)
    require(any(x['file'] == 'preflight-original.zip' for x in plan['artifacts']), 'Hosted preflight proof absent')
    require(any(x['file'] == 'trade-resource-original.zip' for x in plan['artifacts'])
            and any(x['file'] == 'league-entry-original.zip' for x in plan['artifacts']),
            'Existing hosted Trade or league-entry acceptance absent')
    require(any(x['file'] == 'actuals-restoration-original.zip' for x in plan['artifacts']), 'Native restoration acceptance absent')
    require(any(x['file'] == 'restoration-unused-original.zip' for x in plan['artifacts']), 'Hosted restoration recovery proof absent')
    require(any(x['file'] == 'resident-refresh-original.zip' for x in plan['artifacts']), 'Hosted resident ownership proof absent')
    shutil.copyfile(recovery, assets / 'Trade-decision-evidence.zip')
    prior_evidence = Path(plan['prior_evidence_file'])
    require(str(prior_evidence) == '.github/release-plans/2239-prior.zip', 'Unexpected prior archive path')
    verify_prior_evidence(prior_evidence, plan)
    shutil.copyfile(prior_evidence, assets / 'Prior-attempts.zip')
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
    prior.extend(prior_attempt_record(repo, reference) for reference in plan.get('prior_attempts', []))
    write_json(assets / 'prior-attempts.json', prior)
    write_json(assets / 'VALIDATION.json', dict(candidate=plan['candidate'], tree=plan['tree'], version=plan['version'], build=plan['build'],
        canonical=canonical, local_canonical=local_canonical, local_preflight=local_preflight_result, local_restoration_unused=local_unused_result, local_resident_refresh=local_resident_result, required_jobs=records, product_test_executions=sum(counts), original_artifacts=plan['artifacts'],
        recovery_sha256=plan['recovery_sha256'], prior_evidence_sha256=plan['prior_evidence_sha256'], limitations='Trade presentation and existing zero-qualified diagnosis only. Recorded bilateral verdicts, scoring, Neutral/Custom values, exact picks, search limits and all memory policies remain unchanged. The preview action is earlier on phones. Why-now requires matching supported calendar evidence; retained context is not revalidated. Disposable qualifying offers and phone measurements are not live production offers. Existing authorized owner-browser/Shell control is not attached in this session; external401 is not retried. No forced production acquisition, Trade discovery, preference mutation or infrastructure change.'))
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
    found = [x for x in artifacts if x['name'] == 'guarded-release-2239-prepare-' + str(run_id) and not x['expired']]
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
            notes += '\n\nReleased merge: ' + main + '\nValidated source: ' + plan['candidate'] + '\nSource tree: ' + plan['tree'] + '\nAll 13 required hosted jobs and all ten canonical gates passed; ' + str(plan['canonical_tests']) + ' canonical tests and ' + str(plan['product_tests']) + ' Product tests. Prior failures and resource qualifications remain in attached evidence.\n'
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


def verify_plan(plan):
    require(plan.get('finalized') is True, 'Release plan is not finalized')
    for field in ('draft_id', 'canonical_tests', 'canonical_entries', 'local_canonical_entries', 'product_tests'):
        require(type(plan.get(field)) is int and plan[field] > 0, 'Missing final release evidence: ' + field)
    for field in ('candidate', 'tree', 'baseline'):
        require(isinstance(plan.get(field), str) and re.fullmatch('[0-9a-f]{40}', plan[field]), 'Invalid source identity: ' + field)
    for field in ('recovery_sha256', 'prior_evidence_sha256'):
        require(isinstance(plan.get(field), str) and re.fullmatch('[0-9a-f]{64}', plan[field]), 'Missing evidence checksum: ' + field)
    required = {'current-production-coverage-original.zip', 'market-history-coverage-original.zip', 'canonical-original.zip', 'current-history-original.zip', 'history-followthrough-original.zip', 'preflight-original.zip', 'trade-resource-original.zip',
                'league-entry-original.zip', 'actuals-restoration-original.zip', 'restoration-unused-original.zip', 'resident-refresh-original.zip', 'lifecycle-ordinary.zip', 'lifecycle-archive-warmed.zip',
                'lifecycle-combined-read.zip', 'public-welcome-security.zip'}
    files = [x.get('file') for x in plan.get('artifacts', [])]
    require(required <= set(files), 'Missing mandatory release artifacts')
    require(len(files) == len(set(files)) == len(required), 'Unexpected or duplicate release artifact population')
    require(sum(len(x.get('jobs', [])) for x in plan.get('runs', [])) == 13, 'Required thirteen-job population missing')
    require(all(type(run.get('id')) is int and run['id'] > 0 for run in plan['runs']),
            'Final validation run identities missing')


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
        verify_plan(plan)
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
