import sys;sys.path.insert(0,"/app")
import gc,importlib.util,json,os,time,unittest
from pathlib import Path
import psutil
from src.platform.memory_reclamation import release_unused_allocator_pages
from src.platform.trade_execution import observe_memory,assess_memory
import dtos_app  # Preload application imports before matching resident memory.
mode=sys.argv[1]
if mode=="before":
 spec=importlib.util.spec_from_file_location("original_simple_browser","/evidence/simple-browser-original.py");module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
else:
 import tests.test_trade_simple_browser as module
process=psutil.Process();gc.collect();release_unused_allocator_pages()
start=process.memory_info().rss;target=845*1024**2
padding=bytearray(max(0,target-start))
for i in range(0,len(padding),4096):padding[i]=1
initial=observe_memory();assert initial["cgroup_limit_bytes"]==2147483648
print("BOUNDED_PRESSURE",json.dumps(dict(mode=mode,rss=process.memory_info().rss,padding=len(padding),memory=initial,admission=assess_memory(initial))),flush=True)
started=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.SimpleTradeJourneyBrowserTests);result=unittest.TextTestRunner(verbosity=2).run(suite)
del padding;gc.collect();release_unused_allocator_pages();time.sleep(.2)
report=dict(mode=mode,scope="Disposable845MiB parent RSS pressure, chosen from the original post-GC885854208-byte unittest RSS;, not the real preceding full-suite heap; same application and prepared fixtures; no memory telemetry mocks or admission changes",tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),passed=result.wasSuccessful(),initial_rss_target=target,padding_bytes=max(0,target-start),initial_memory=initial,elapsed_seconds=time.monotonic()-started,final_memory=observe_memory(),kernel_peak=int(Path("/sys/fs/cgroup/memory.peak").read_text()),live_children=[dict(pid=p.pid,name=p.name()) for p in process.children(recursive=True) if p.is_running() and p.status()!=psutil.STATUS_ZOMBIE])
Path("/evidence/browser-pressure-"+mode+"-matched.json").write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report),flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
