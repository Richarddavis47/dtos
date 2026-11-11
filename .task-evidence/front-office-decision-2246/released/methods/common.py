"""Shared final-source orchestration; importing this module never starts validation."""
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE = Path(__file__).resolve().parent
SOURCE_CHECKOUT = Path("/workspace/dtos-frontoffice-local-2246-r3")
SOURCE_REPOSITORY = Path("/workspace/dtos")
CONTAINER_NAME = "dtos-frontoffice-local-2246-r3"
IMAGE = "dtos-canonical314:2245"
IMAGE_ID = "sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def load_source():
    source = json.loads((BASE / "source.json").read_text())
    for key in ("candidate", "tree", "baseline"):
        assert re.fullmatch("[a-f0-9]{40}", source[key]), key
    assert type(source["expected_test_count"]) is int and source["expected_test_count"] > 0
    assert source["version"] == "1.22.31" and source["build"] == 2246
    assert source["baseline"] == "abbe723a0566cf84a8fff947cf7320cb66567a77" and source["pr"] == 335
    assert source["candidate"] != "b602d6acd03cc1c95d85ee734d2d7f28658885cf", "R3 requires the reviewed replacement commit"
    assert source["supersedes"] == "b602d6acd03cc1c95d85ee734d2d7f28658885cf"
    return source


def verify_worker_setup_controls(source=None):
    """Read retained controls and Git bytes only; never run/import a test or Docker.

    Original controls ran on dirty b602 test bytes. The original commit bridge,
    exact committed file hash and AST comparison bind those bytes to the actual
    replacement source without relabeling that historical execution.
    """
    source = load_source() if source is None else source
    root = Path('/workspace/2246-granite-activation/expansion/worker-setup-reconciliation')
    expected = {
        'result.json': 'f4e913e6e8cc3170c9036d3aec488f1e2f5fdbe8132b00a1c304265deda8e030',
        'summary.json': '43e4235eb7b9e47ca6a199bc4fc4e09eb30f92d6bf7b800521aff5eaff82226d',
        'source-predicate-proof.json': '3289b1a4850e3dcf498634787f8c5e373fa92c7ddf0b22041f0125f1ae8d16e1',
        'commit-provenance.json': '660282db4cbdd5a1f69cfcf6e595940251c10f101b3acc1d7647d47d932298bc',
        'SHA256SUMS': 'b2b9ade101ac762210b43cfd0f1f0ab9f0f522a302c43d94185a65234254168a',
    }

    def check(condition, message):
        if not condition:
            raise RuntimeError('Worker setup controls: ' + message)

    originals = {}
    for name, checksum in expected.items():
        path = root / name
        check(path.is_file() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents),
              'missing/unsafe retained original ' + name)
        raw = path.read_bytes()
        check(hashlib.sha256(raw).hexdigest() == checksum, 'original changed: ' + name)
        originals[name] = raw
    result, summary, predicates, bridge = (json.loads(originals[name]) for name in
        ('result.json', 'summary.json', 'source-predicate-proof.json', 'commit-provenance.json'))
    sums_rows = [line.split('  ', 1) for line in originals['SHA256SUMS'].decode().splitlines()]
    check(all(len(row) == 2 for row in sums_rows), 'malformed original checksums')
    sums = {name: checksum for checksum, name in sums_rows}
    check(len(sums) == len(sums_rows), 'duplicate original checksum names')
    for name in ('result.json', 'summary.json', 'source-predicate-proof.json'):
        check(sums[name] == expected[name], 'original checksum list disagrees: ' + name)
    check(source['expected_test_count'] == result['loaded_suite_tests'] == summary['loaded_source_tests'] == 4364,
          'all-module discovery population changed')
    check(bridge['commit'] == source['candidate'] and bridge['tree'] == source['tree']
          and bridge['tested_bytes_match_commit'] is True and bridge['working_tree_clean'] is True
          and bridge['strict_predicates_unchanged'] is True and bridge['all_controls_matched_expected'] is True
          and bridge['actual_audit_tests_passed'] == 9, 'actual committed-source bridge required')
    baseline = 'b602d6acd03cc1c95d85ee734d2d7f28658885cf'
    test_path = 'tests/test_projection_audit.py'
    check(result['source']['head'] == baseline
          and result['source']['tree'] == '8a687ea0256d6e0031b57e08e2a1a38a90a1a535'
          and result['source']['status'] == ' M tests/test_projection_audit.py\n', 'historical dirty execution identity changed')
    committed = subprocess.check_output(['git', 'show', source['candidate'] + ':' + test_path], cwd=SOURCE_REPOSITORY)
    original = subprocess.check_output(['git', 'show', baseline + ':' + test_path], cwd=SOURCE_REPOSITORY)
    candidate_sha = hashlib.sha256(committed).hexdigest()
    baseline_sha = hashlib.sha256(original).hexdigest()
    check(candidate_sha == bridge['test_file_sha256'] == result['source']['candidate_file_sha256'] == predicates['candidate_sha256'],
          'committed file is not the exact tested corrected bytes')
    check(baseline_sha == result['baseline_file_sha256'] == predicates['baseline_sha256'] == sums['baseline-original.py']
          and predicates['baseline'] == baseline and predicates['strict_predicates_unchanged'] is True
          and predicates['only_gc_statement_placement_and_comment_changed'] is True
          and predicates['application_diff_files'] == bridge['changed_files'] == [test_path], 'placement-only source proof changed')
    check(subprocess.check_output(['git', 'rev-parse', source['candidate'] + '^{tree}'], cwd=SOURCE_REPOSITORY, text=True).strip() == source['tree'],
          'actual committed tree differs from source input')
    check(subprocess.check_output(['git', 'diff', '--name-only', baseline, source['candidate']], cwd=SOURCE_REPOSITORY,
                                  text=True).splitlines() == [test_path], 'replacement changes more than the reviewed fixture file')
    old_ast, new_ast = ast.parse(original), ast.parse(committed)
    target = 'test_projection_audit_does_not_block_lightweight_request'
    def function(tree):
        matches = [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == target]
        check(len(matches) == 1, 'unique worker audit test required')
        return matches[0]
    def call(node, owner, attr):
        return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == owner
    for tree in (old_ast, new_ast):
        test = function(tree)
        wait = [node for node in ast.walk(test) if call(node, 'release', 'wait')]
        request = [node for node in ast.walk(test) if call(node, 'asyncio', 'wait_for')]
        threshold = [node for node in ast.walk(test) if call(node, 'self', 'assertLess')]
        check(len(wait) == len(request) == len(threshold) == 1
              and ast.literal_eval(wait[0].args[0]) == 2.0 and ast.literal_eval(request[0].args[1]) == 0.25
              and isinstance(threshold[0].args[0], ast.Name) and threshold[0].args[0].id == 'latency_ms'
              and ast.literal_eval(threshold[0].args[1]) == 100, 'unchanged 2s/250ms/100ms predicates required')
    def gc_lines(tree):
        return [node.lineno for node in ast.walk(function(tree))
                if isinstance(node, ast.Expr) and call(node.value, 'gc', 'collect')]
    def task_lines(tree):
        return [node.lineno for node in ast.walk(function(tree)) if call(node, 'asyncio', 'create_task')]
    old_gc, new_gc, old_task, new_task = gc_lines(old_ast), gc_lines(new_ast), task_lines(old_ast), task_lines(new_ast)
    check(len(old_gc) == len(new_gc) == len(old_task) == len(new_task) == 1
          and old_gc[0] > old_task[0] and new_gc[0] < new_task[0], 'setup collection was not moved before held worker creation')
    class RemoveSetupCollection(ast.NodeTransformer):
        def visit_Expr(self, node):
            return None if call(node.value, 'gc', 'collect') else self.generic_visit(node)
    check(ast.dump(RemoveSetupCollection().visit(old_ast), include_attributes=False)
          == ast.dump(RemoveSetupCollection().visit(new_ast), include_attributes=False), 'AST changed beyond setup collection placement/comments')
    negative_needle = '        async def lightweight() -> dict[str, bool]:\n            return {"ready": True}'
    candidate_text = committed.decode()
    check(candidate_text.count(negative_needle) == 1, 'negative-control injection boundary changed')
    negative = candidate_text.replace(negative_needle,
        '        async def lightweight() -> dict[str, bool]:\n            time.sleep(0.12)\n            return {"ready": True}').encode()
    check(hashlib.sha256(negative).hexdigest() == result['negative_file_sha256'] == sums['projection_worker_foreground_negative.py'],
          'real 120ms foreground negative source differs')
    expected_cases = {'old_placement_controlled_2.1s_setup': False, 'new_placement_controlled_2.1s_setup': True,
                      'new_placement_actual_gc_same_graph': True, 'new_placement_real_120ms_foreground_negative': False}
    cases = {row['name']: row for row in result['cases']}
    summaries = {row['name']: row for row in summary['cases']}
    check(len(cases) == len(result['cases']) == len(summaries) == len(summary['cases']) == len(expected_cases)
          and set(cases) == set(summaries) == set(expected_cases) and summary['all_controls_matched_expected'] is True,
          'four exact positive/negative controls required')
    for name, expected_pass in expected_cases.items():
        row, short = cases[name], summaries[name]
        check(row['passed'] is expected_pass and short['actual_passed'] is expected_pass and row['tests'] == 1
              and not row['errors'] and not short['errors'] and row['gc_enabled'] is True and row['gc_enabled_after'] is True,
              'control outcome/GC mismatch: ' + name)
        for field in ('failures', 'worker_holds', 'requests'):
            check(row[field] == short[field], 'summary differs from complete original: ' + name)
        check(row['collections'] == short['collection'] and len(row['worker_holds']) == len(row['collections']) == 1,
              'collection/worker observation missing: ' + name)
        hold, collection = row['worker_holds'][0], row['collections'][0]
        old = name.startswith('old_')
        delay = 2.1 if 'controlled_2.1s_setup' in name else 0
        check(hold['timeout'] == 2.0 and hold['released'] is (not old)
              and hold['observed_context'] == ['projection-audit-request']
              and collection['worker_started'] is old and collection['audit_task_created'] is old
              and collection['controlled_setup_delay_seconds'] == delay and collection['gc_enabled'] is True
              and collection['gc_enabled_after'] is True, 'worker placement/release/context mismatch: ' + name)
        if expected_pass:
            check(not row['failures'] and all(request.get('status') == 200 for request in row['requests']), 'positive control failed')
        else:
            check(len(row['failures']) == 1 and row['failures'][0]['type'] == 'AssertionError', 'negative must fail an assertion')
            text = row['failures'][0]['text']
            check(('False is not true' in text and hold['elapsed_ms'] >= 2000) if old else 'not less than 100' in text,
                  'wrong negative failure predicate: ' + name)
        if not old:
            check(hold['elapsed_ms'] < 2000 and all(request.get('status') == 200 for request in row['requests']),
                  'replacement must release actual worker and complete both requests')
    check(result['actual_audit_module'] == summary['actual_audit_module']
          and result['actual_audit_module'] == {'tests': 9, 'passed': True, 'failures': 0, 'errors': 0,
                                               'gc_enabled': True, 'retained_same_graph': True}, 'nine actual audit tests did not pass')
    environment, resources = result['environment'], summary['resources']
    check(environment['python'].startswith('3.14.3') and environment['cgroup_limit'] == '2147483648'
          and environment['swap_max'] == '0' and environment['cpu_max'] == '200000 100000' and environment['network'] == 'none'
          and resources['memory_bytes'] == resources['total_memory_and_swap_bytes'] == 2147483648
          and resources['extra_swap_bytes'] == 0 and resources['cpus'] == 2 and resources['network'] == 'none'
          and resources['user'] == '1000:1000' and resources['runtime_image'] == IMAGE_ID and resources['exit_code'] == 0,
          'actual constrained runtime/resource identity changed')
    def memory_events(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('cgroup_memory_events', 'cgroup_events'):
                    check(all(item.get(event, 0) == 0 for event in ('max', 'oom', 'oom_kill', 'oom_group_kill')),
                          'resource limit/OOM event recorded')
                memory_events(item)
        elif isinstance(value, list):
            for item in value:
                memory_events(item)
    memory_events(result)
    memory_events(summary)
    check(result['gc_thresholds'] == [2000, 10, 0] and result['gc_thresholds_unchanged'] is True
          and summary['gc_thresholds_unchanged'] is True and result['gc_enabled'] is True and summary['gc_enabled'] is True
          and result['graph']['rows'] == summary['retained_graph_rows'] == 2450000
          and result['same_graph_retained'] is True and summary['same_graph_retained'] is True, 'retained graph/GC controls changed')
    return {'passed': True, 'candidate': source['candidate'], 'tree': source['tree'],
            'test_file': test_path, 'candidate_file_sha256': candidate_sha,
            'historical_execution_source': result['source'], 'originals_path': str(root), 'original_sha256': expected,
            'controls': expected_cases, 'loaded_suite_tests': 4364, 'actual_audit_tests': 9,
            'strict_predicates': {'worker_wait_seconds': 2.0, 'request_timeout_seconds': 0.25, 'latency_bound_ms': 100},
            'resource_limits': {'memory_bytes': 2147483648, 'extra_swap_bytes': 0, 'cpu_max': '200000 100000', 'network': 'none'},
            'scope': 'Original dirty-b602 fixture controls bridged by exact file bytes to actual committed replacement. Controlled setup delay is a model; no historical GC-duration attribution or fresh full-suite pass is inferred.'}


def command(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def assert_checkout(source, checkout=SOURCE_CHECKOUT):
    assert command("git", "rev-parse", "HEAD", cwd=checkout) == source["candidate"]
    assert command("git", "rev-parse", "HEAD^{tree}", cwd=checkout) == source["tree"]
    assert not command("git", "status", "--porcelain", cwd=checkout), "Source checkout must be clean"


def image_record():
    record = json.loads(command("docker", "image", "inspect", IMAGE))[0]
    assert record["Id"] == IMAGE_ID, "Existing pinned validation runtime changed"
    return record


def git_common_dir(checkout):
    value = Path(command("git", "rev-parse", "--git-common-dir", cwd=checkout))
    return (checkout / value).resolve() if not value.is_absolute() else value.resolve()


def docker_base(source, readonly=True):
    assert_checkout(source)
    image_record()
    common = git_common_dir(SOURCE_CHECKOUT)
    return [
        "docker", "run", "--rm", "--init", "--user", "1000:1000",
        "--memory=2g", "--memory-swap=2g", "--cpus=2", "--network=none",
        "--env", "HOME=/tmp", "--env", "NODE_OPTIONS=--max-old-space-size=256",
        "--env", "DTOS_EXPECTED_HEAD=" + source["candidate"],
        "--env", "DTOS_EXPECTED_TREE=" + source["tree"],
        "--env", "GIT_CONFIG_COUNT=1", "--env", "GIT_CONFIG_KEY_0=safe.directory",
        "--env", "GIT_CONFIG_VALUE_0=/app",
        "--volume", str(SOURCE_CHECKOUT) + ":/app" + (":ro" if readonly else ""),
        "--volume", str(common) + ":" + str(common) + ":ro",
        "--volume", str(BASE) + ":/evidence", "--workdir", "/app",
    ]

