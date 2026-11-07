import sys
sys.path.insert(0,'/app')
from pathlib import Path
import json,unittest,subprocess,time
from tests import test_fois_process_execution as fixtures
from src.platform.lifecycle import memory_snapshot
def main():
 b=Path('/evidence');case=fixtures.FOISProcessExecutionTests('test_prewarmed_worker_keeps_event_loop_responsive_with_large_irrelevant_data');checks=[];original=case.assertLess
 # Record the test's actual measured heartbeat; delegate every unchanged assertion.
 def capture(a,b,*args,**kwargs):
  checks.append(dict(value=a,limit=b));return original(a,b,*args,**kwargs)
 case.assertLess=capture
 before=memory_snapshot();cpu_before=Path('/sys/fs/cgroup/cpu.stat').read_text();started=time.monotonic();result=unittest.TextTestRunner(verbosity=2).run(case);after=memory_snapshot()
 report=dict(source=subprocess.check_output(['git','rev-parse','HEAD','HEAD^{tree}'],text=True).splitlines(),passed=result.wasSuccessful(),tests=result.testsRun,checks=checks,seconds=time.monotonic()-started,before=before,after=after,cpu_before=cpu_before,cpu_after=Path('/sys/fs/cgroup/cpu.stat').read_text(),scope='One unchanged mandatory liveness test in a separate enforced2GiB/no-swap/offline container. Observer records assertLess arguments and delegates without altering thresholds. A pass does not establish the cause of the earlier548msfailure or universal liveness.')
 (b/'fois-liveness-control.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],tests=report['tests'],checks=checks,seconds=report['seconds'])));raise SystemExit(not result.wasSuccessful())

if __name__ == "__main__":
 main()
