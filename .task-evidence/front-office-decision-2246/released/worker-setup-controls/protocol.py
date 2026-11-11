"""Bounded fixture-placement controls; not a release gate or hosted GC replay."""
from contextlib import ExitStack
import faulthandler
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import subprocess
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch


faulthandler.dump_traceback_later(90, repeat=True)
sys.path[:0] = ['/app', '/app/tests', '/output']
prefix = Path('/canonical/runner.py').read_text().split('git_n =', 1)[0]
exec(compile(prefix, '/canonical/runner.py:environment-prefix', 'exec'))

from src.platform.lifecycle import memory_snapshot
import httpx


OUT = Path('/output')
SOURCE = Path('/app/tests/test_projection_audit.py')
assert gc.isenabled()
thresholds = gc.get_threshold()
proof = dict(scope='Disposable actual audit worker/request controls. Explicit 2.1s setup delay models placement only; it is not measured historical GC duration or a substitute for fresh full validation.',
             started=time.time(), cases=[], gc_thresholds=thresholds,
             source=dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd='/app', text=True).strip(),
                         tree=subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd='/app', text=True).strip(),
                         status=subprocess.check_output(['git', 'status', '--porcelain'], cwd='/app', text=True),
                         candidate_file_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest()),
             environment=dict(python=sys.version, cgroup_limit=Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                              swap_max=Path('/sys/fs/cgroup/memory.swap.max').read_text().strip(),
                              cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(), network='none'))
assert proof['environment']['cgroup_limit'] == '2147483648'
assert proof['environment']['swap_max'] == '0'

all_modules = unittest.defaultTestLoader.discover('/app/tests', top_level_dir='/app/tests')
proof['loaded_suite_tests'] = all_modules.countTestCases()
assert proof['loaded_suite_tests'] == 4364
proof['after_all_module_imports'] = memory_snapshot()
print('Imported complete source suite:', proof['loaded_suite_tests'], flush=True)


def load_copy(name, text):
    path = OUT / (name + '.py')
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


baseline = (OUT / 'baseline-original.py').read_text()
candidate = SOURCE.read_text()
old_module = load_copy('projection_worker_old_placement', baseline)
new_module = __import__('test_projection_audit')
negative_needle = '        async def lightweight() -> dict[str, bool]:\n            return {"ready": True}'
assert candidate.count(negative_needle) == 1
negative = candidate.replace(negative_needle,
    '        async def lightweight() -> dict[str, bool]:\n            time.sleep(0.12)\n            return {"ready": True}')
negative_module = load_copy('projection_worker_foreground_negative', negative)
proof['baseline_file_sha256'] = hashlib.sha256(baseline.encode()).hexdigest()
proof['negative_file_sha256'] = hashlib.sha256(negative.encode()).hexdigest()

# Reuse the previous fixed rooted tracked-graph shape and population. Keep GC
# enabled during construction and all controls; do not tune thresholds/reserves.
anchor, graph = [], []
graph_started = time.monotonic()
for batch in range(98):
    assert gc.isenabled() and gc.get_threshold() == thresholds
    graph.extend({'owner': anchor, 'index': batch * 25000 + index} for index in range(25000))
    assert memory_snapshot()['rss_bytes'] < 1024**3, 'Fixed diagnostic exceeded its 1GiB RSS bound'
anchor.append(graph)
assert len(graph) == 2_450_000
proof['graph'] = dict(rows=len(graph), build_seconds=time.monotonic() - graph_started,
                      retained_rooted_shape='2.45M tracked dicts point to common anchor; anchor points to complete list',
                      memory=memory_snapshot(), gc_enabled=gc.isenabled())
print('Fixed same rooted graph:', len(graph), 'RSS', proof['graph']['memory']['rss_bytes'], flush=True)


class CapturingResult(unittest.TextTestResult):
    def addFailure(self, test, error):
        current['failures'].append(dict(test=test.id(), type=error[0].__name__, text=str(error[1])))
        super().addFailure(test, error)

    def addError(self, test, error):
        current['errors'].append(dict(test=test.id(), type=error[0].__name__, text=str(error[1])))
        super().addError(test, error)


real_wait = threading.Event.wait
real_get = httpx.AsyncClient.get


def observed_wait(event, timeout=None):
    frame = sys._getframe(1)
    audit_hold = frame.f_code.co_name == 'slow_builder' and timeout == 2.0
    observed_context = frame.f_locals.get('observed_context') if audit_hold else None
    del frame
    began = time.perf_counter()
    result = real_wait(event, timeout)
    if audit_hold:
        current['worker_holds'].append(dict(timeout=timeout, released=result,
                                            elapsed_ms=(time.perf_counter() - began) * 1000,
                                            observed_context=list(observed_context or [])))
    return result


async def observed_get(client, url, *args, **kwargs):
    record = dict(path=str(url), began=time.perf_counter())
    try:
        response = await real_get(client, url, *args, **kwargs)
        record['status'] = response.status_code
        return response
    except BaseException as error:
        record['error_type'] = type(error).__name__
        raise
    finally:
        record['elapsed_ms'] = (time.perf_counter() - record['began']) * 1000
        current['requests'].append(record)


def collection_with_setup_delay(delay):
    def collect(*args, **kwargs):
        frame = sys._getframe(1)
        state = dict(worker_started=frame.f_locals['started'].is_set(),
                     audit_task_created='audit_request' in frame.f_locals,
                     gc_enabled=gc.isenabled())
        del frame
        began = time.perf_counter()
        state['collected'] = gc.collect(*args, **kwargs)
        state['actual_gc_ms'] = (time.perf_counter() - began) * 1000
        state['controlled_setup_delay_seconds'] = delay
        if delay:
            time.sleep(delay)
        state['setup_total_ms'] = (time.perf_counter() - began) * 1000
        state['gc_enabled_after'] = gc.isenabled()
        current['collections'].append(state)
        return state['collected']
    return collect


def run_control(name, module, delay):
    global current
    current = dict(name=name, failures=[], errors=[], worker_holds=[], requests=[], collections=[],
                   memory_before=memory_snapshot(), gc_enabled=gc.isenabled())
    proof['cases'].append(current)
    began = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(module, 'gc', SimpleNamespace(collect=collection_with_setup_delay(delay))))
        stack.enter_context(patch.object(threading.Event, 'wait', observed_wait))
        stack.enter_context(patch.object(httpx.AsyncClient, 'get', observed_get))
        test = module.ProjectionAuditTests('test_projection_audit_does_not_block_lightweight_request')
        result = unittest.TextTestRunner(verbosity=2, resultclass=CapturingResult).run(unittest.TestSuite([test]))
    current.update(passed=result.wasSuccessful(), tests=result.testsRun,
                   elapsed_ms=(time.perf_counter() - began) * 1000, memory_after=memory_snapshot(),
                   gc_enabled_after=gc.isenabled())
    assert gc.isenabled() and gc.get_threshold() == thresholds
    assert len(graph) == 2_450_000 and anchor[0] is graph
    (OUT / 'partial-result.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(current), flush=True)
    return current


old = run_control('old_placement_controlled_2.1s_setup', old_module, 2.1)
assert not old['passed'] and len(old['collections']) == len(old['worker_holds']) == 1
assert old['collections'][0]['worker_started'] and old['collections'][0]['audit_task_created']
assert old['worker_holds'][0]['released'] is False

new = run_control('new_placement_controlled_2.1s_setup', new_module, 2.1)
assert new['passed'] and len(new['collections']) == len(new['worker_holds']) == 1
assert not new['collections'][0]['worker_started'] and not new['collections'][0]['audit_task_created']
assert new['worker_holds'][0]['released'] is True
assert [r['status'] for r in new['requests']] == [200, 200]

normal = run_control('new_placement_actual_gc_same_graph', new_module, 0)
assert normal['passed'] and normal['worker_holds'][0]['released'] is True
assert not normal['collections'][0]['worker_started']

negative = run_control('new_placement_real_120ms_foreground_negative', negative_module, 0)
assert not negative['passed'] and negative['worker_holds'][0]['released'] is True
assert any('not less than 100' in failure['text'] for failure in negative['failures'])
assert [r['status'] for r in negative['requests']] == [200, 200]

# Run all nine actual module tests after whole-suite import, using the normal
# real gc binding and unchanged application code, rather than diagnostic copies.
module_log = OUT / 'actual-audit-module-original.log'
with module_log.open('w') as stream:
    actual = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(new_module))
proof['actual_audit_module'] = dict(tests=actual.testsRun, passed=actual.wasSuccessful(), failures=len(actual.failures), errors=len(actual.errors),
                                  gc_enabled=gc.isenabled(), retained_same_graph=len(graph) == 2_450_000 and anchor[0] is graph)
assert actual.testsRun == 9 and actual.wasSuccessful()
proof.update(finished=time.time(), max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             final_memory=memory_snapshot(), same_graph_retained=len(graph) == 2_450_000 and anchor[0] is graph,
             gc_enabled=gc.isenabled(), gc_thresholds_unchanged=gc.get_threshold() == thresholds)
(OUT / 'result.json').write_text(json.dumps(proof, indent=2) + '\n')
faulthandler.cancel_dump_traceback_later()
print(json.dumps(dict(actual_audit_module=proof['actual_audit_module'], all_controls_matched_expected=True,
                      gc_enabled=proof['gc_enabled'], same_graph_retained=proof['same_graph_retained'])), flush=True)
