"""Replay the actual pre-failure test prefix; diagnose, never replace full validation."""
import ast,asyncio,gc,hashlib,inspect,json,os,sys,textwrap,time,unittest
from pathlib import Path
import psutil
sys.path.insert(0,'/app');sys.path.insert(0,'/app/tests')
TARGET='test_fois_process_execution.FOISProcessExecutionTests.test_prewarmed_worker_keeps_event_loop_responsive_with_large_irrelevant_data'
B=Path('/output');records=[];gc_events=[];phase='prefix';active={}
def callback(event,info):
 gen=info.get('generation');now=time.perf_counter()
 if event=='start':active[gen]=now
 else:
  began=active.pop(gen,now);gc_events.append(dict(phase=phase,generation=gen,elapsed_ms=(now-began)*1000,collected=info.get('collected'),uncollectable=info.get('uncollectable'),at=now))
def measured(gaps,status):
 records.append(dict(phase=phase,gaps_ms=list(gaps),max_gap_ms=max(gaps) if gaps else None,records=status.get('records'),state=status.get('state'),execution={k:status.get('execution',{}).get(k) for k in ['worker_pid','execution','process_model','input_bytes','source_bytes','exit_status']},rss=psutil.Process().memory_info().rss,gc_enabled=gc.isenabled(),gc_count=gc.get_count()))
all_suite=unittest.defaultTestLoader.discover('/app/tests')
def flatten(suite):
 for test in suite:
  if isinstance(test,unittest.TestSuite):yield from flatten(test)
  else:yield test
all_tests=list(flatten(all_suite));ids=[t.id() for t in all_tests];assert len(ids)==4435 and TARGET in ids
index=ids.index(TARGET);prefix_cases=all_tests[:index];target_case=all_tests[index];held_suffix=all_tests[index+1:];del all_suite,all_tests
module=sys.modules['test_fois_process_execution'];method=getattr(module.FOISProcessExecutionTests,TARGET.rsplit('.',1)[-1]);original=inspect.getsource(method);tree=ast.parse(textwrap.dedent(original));function=tree.body[0]
# Add one metric snapshot only after heartbeat stop and real-worker shutdown,
# immediately before the original assertions. No original assertion is altered.
for i,node in enumerate(function.body):
 if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='assertTrue':
  function.body.insert(i,ast.Expr(value=ast.Call(func=ast.Name(id='_profile_measured',ctx=ast.Load()),args=[ast.Name(id='gaps',ctx=ast.Load()),ast.Call(func=ast.Attribute(value=ast.Name(id='service',ctx=ast.Load()),attr='status',ctx=ast.Load()),args=[],keywords=[])],keywords=[])))
  break
else:raise AssertionError('Original assertion boundary not found')
ast.fix_missing_locations(tree);module.__dict__['_profile_measured']=measured;exec(compile(tree,'<source-f40-diagnostic-only>','exec'),module.__dict__);setattr(module.FOISProcessExecutionTests,TARGET.rsplit('.',1)[-1],module.__dict__[TARGET.rsplit('.',1)[-1]])
method_record=dict(source_file_sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),original_method_sha256=hashlib.sha256(original.encode()).hexdigest(),instrumented_ast_sha256=hashlib.sha256(ast.dump(tree).encode()).hexdigest(),prefix_methods=index,total_source_methods=4435,scope='Diagnostic only. Actual original source prefix/fixtures and native worker. One post-measurement record inserted; original500ms/input assertions unchanged. No admission mock, GC disable or source mutation.')
(B/'diagnostic-method.json').write_text(json.dumps(method_record,indent=2)+'\n')
# The actual prefix runs unchanged, with the same imported source universe.
prefix=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(prefix_cases));del prefix_cases
phase='unclean-after-actual-prefix';gc.callbacks.append(callback)
first=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([target_case]));del target_case
phase='precondition-collection';before=time.perf_counter();collected=gc.collect();collection=dict(collected=collected,elapsed_ms=(time.perf_counter()-before)*1000,rss=psutil.Process().memory_info().rss,gc_enabled=gc.isenabled())
phase='after-fixture-collection'
second=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([module.FOISProcessExecutionTests(TARGET.rsplit('.',1)[-1])]))
gc.callbacks.remove(callback)
result=dict(method=method_record,prefix=dict(tests=prefix.testsRun,failures=len(prefix.failures),errors=len(prefix.errors),skipped=len(prefix.skipped)),unclean=dict(tests=first.testsRun,failures=len(first.failures),errors=len(first.errors),skipped=len(first.skipped)),collection=collection,after_collection=dict(tests=second.testsRun,failures=len(second.failures),errors=len(second.errors),skipped=len(second.skipped)),records=records,gc_events=gc_events,held_future_test_cases=len(held_suffix),scope='Not mandatory full regression or proof of the original unobserved GC event. Both native operations and any assertion failures are retained. Prefix replay plus controlled GC preconditioning is for causal diagnosis only.')
(B/'diagnostic-prefix-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(not (prefix.wasSuccessful() and first.wasSuccessful() and second.wasSuccessful()))
