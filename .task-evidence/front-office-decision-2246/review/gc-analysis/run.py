"""Fixed, retained-old-heap diagnostic. Never used as a release gate result."""
from pathlib import Path
import faulthandler
import gc
import importlib.util
import json
import os
import resource
import sys
import time
import unittest

faulthandler.dump_traceback_later(60, repeat=True)
sys.path[:0] = ["/app", "/app/tests", "/harness", "/output"]
prefix = Path("/canonical/runner.py").read_text().split("git_n =", 1)[0]
exec(compile(prefix, "/canonical/runner.py:environment-prefix", "exec"))

from fixture_cleanup import reclaim_completed_fixtures
from observer import Observer
from src.platform.lifecycle import memory_snapshot

out = Path("/output")
start = time.time()
proof = {"cases": [], "started": start, "scope":
         "Fixed original/GC-precondition/120ms-foreground-block diagnostic; modeled retained graph, no gate replacement."}
suite = unittest.defaultTestLoader.discover("/app/tests", top_level_dir="/app/tests")
proof["loaded_tests"] = suite.countTestCases()
proof["after_import"] = memory_snapshot()
proof["gc_thresholds"] = gc.get_threshold()
print("Loaded", proof["loaded_tests"], "RSS", proof["after_import"]["rss_bytes"], flush=True)

source = Path("/app/tests/test_projection_audit.py").read_text()
needle = "                    began = time.perf_counter()"
assert source.count(needle) == 1
variant = source.replace(needle, "                    __import__('gc').collect()\n" + needle)
negative_needle = '        async def lightweight() -> dict[str, bool]:\n            return {"ready": True}'
assert variant.count(negative_needle) == 1
negative = variant.replace(negative_needle,
    '        async def lightweight() -> dict[str, bool]:\n            time.sleep(0.12)\n            return {"ready": True}')

def load_copy(name, text):
    path = out / (name + ".py")
    path.write_text(text)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

modules = [("original", __import__("test_projection_audit")),
           ("precollect", load_copy("projection_audit_precollect", variant)),
           ("foreground_120ms_negative", load_copy("projection_audit_negative", negative))]

# The anchor remains empty during construction so young entries do not lead
# back through the entire retained heap on every construction increment.
anchor = []
graph = []
target = 705_581_056
hard_cap = 1024**3
graph_start = time.monotonic()
for batch in range(160):
    graph.extend({"owner": anchor, "index": batch * 25000 + index}
                 for index in range(25000))
    current = memory_snapshot()["rss_bytes"]
    if current > hard_cap:
        raise RuntimeError("Hard 1GiB RSS diagnostic cap exceeded")
    if current >= target:
        break
else:
    raise RuntimeError("Fixed graph allocation budget exhausted before target")
anchor.append(graph)
proof["graph"] = {"rows": len(graph), "target_rss": target,
                  "after_build": memory_snapshot(),
                  "build_seconds": time.monotonic() - graph_start,
                  "description": "Rooted list of tracked dicts, each dict points to common anchor; anchor points to complete list."}
print("Rooted graph", len(graph), "RSS", proof["graph"]["after_build"]["rss_bytes"], flush=True)

class CapturingResult(unittest.TextTestResult):
    def addFailure(self, test, err):
        current_case["failures"].append({"test": test.id(), "type": err[0].__name__, "text": str(err[1])})
        super().addFailure(test, err)

    def addError(self, test, err):
        current_case["errors"].append({"test": test.id(), "type": err[0].__name__, "text": str(err[1])})
        super().addError(test, err)

observer = Observer(event_limit=4096, frame_limit=20)
with observer:
    for name, module in modules:
        current_case = {"name": name, "failures": [], "errors": [],
                        "before": memory_snapshot(), "gc_counts": gc.get_count()}
        proof["cases"].append(current_case)
        observer.event("case", name)
        cleanup = reclaim_completed_fixtures("test_production_readiness", str(out / "cleanup.jsonl"))
        prelude = unittest.TextTestRunner(verbosity=1).run(
            unittest.defaultTestLoader.loadTestsFromName("test_production_readiness"))
        current_case["prelude"] = {"tests": prelude.testsRun, "failures": len(prelude.failures), "errors": len(prelude.errors)}
        cleanup = reclaim_completed_fixtures("test_projection_audit", str(out / "cleanup.jsonl"))
        # Preserve the five actual test methods that precede the failing target
        # in the original module, rather than invoking a single isolated method.
        tests = unittest.defaultTestLoader.loadTestsFromModule(module)
        selected = []
        for group in tests:
            for test in group:
                selected.append(test)
                if test._testMethodName == "test_projection_audit_does_not_block_lightweight_request":
                    break
            else:
                continue
            break
        target_start = time.time()
        result = unittest.TextTestRunner(verbosity=2, resultclass=CapturingResult).run(unittest.TestSuite(selected))
        current_case.update(tests=result.testsRun, target_started=target_start,
                            target_finished=time.time(), after=memory_snapshot(),
                            gc_counts_after=gc.get_count(), gc_enabled=gc.isenabled(),
                            expected="latency failure diagnostic" if name != "precollect" else "all original assertions pass")
        print("Case", name, "failures", current_case["failures"], "errors", current_case["errors"], flush=True)
        (out / "partial-result.json").write_text(json.dumps(proof, indent=2) + "\n")
observer.export(out / "events.json")
proof["finished"] = time.time()
proof["elapsed_seconds"] = time.time() - start
proof["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
proof["same_graph_retained"] = len(graph) == proof["graph"]["rows"] and anchor[0] is graph
(out / "result.json").write_text(json.dumps(proof, indent=2) + "\n")
faulthandler.cancel_dump_traceback_later()
print(json.dumps({"cases": proof["cases"], "elapsed_seconds": proof["elapsed_seconds"]}), flush=True)
