"""Observe real admissions with unchanged tests, limits and lifecycle."""
import gc,json,logging,os
from pathlib import Path
import subprocess
import time
import unittest
import psutil

out=Path('/output')
cg=Path('/sys/fs/cgroup')
def git(*args):
    return subprocess.check_output(['git',*args],text=True).strip()
assert git('rev-parse','HEAD')==os.environ['DTOS_EXPECTED_HEAD']
assert git('rev-parse','HEAD^{tree}')==os.environ['DTOS_EXPECTED_TREE']
assert git('status','--porcelain')==''
assert (cg/'memory.max').read_text().strip()=='2147483648'
assert gc.isenabled()
parent=psutil.Process()

def snapshot(phase,**details):
    stats=dict(line.split() for line in (cg/'memory.stat').read_text().splitlines())
    kids=[]
    for proc in [parent,*parent.children(recursive=True)]:
        try:
            m=proc.memory_full_info()
            kids.append(dict(pid=proc.pid,name=proc.name(),rss=m.rss,pss=m.pss,uss=m.uss))
        except psutil.Error:
            continue
    with (out/'memory-original.jsonl').open('a') as trace:
        trace.write(json.dumps(dict(phase=phase,at=time.time(),
            cgroup=int((cg/'memory.current').read_text()),
            stats={k:int(stats[k]) for k in ('anon','file','shmem','active_file','inactive_file','kernel')},
            processes=kids,**details))+'\n')

class Admission(logging.Handler):
    def emit(self,record):
        if getattr(record,'event',None)=='trade_admission':
            snapshot('admission', diagnostic=record.diagnostic)
logging.getLogger('dtos.trade_resources').addHandler(Admission())

class Observed(unittest.TextTestResult):
    def startTest(self,test):
        snapshot('start',test=test.id())
        super().startTest(test)
    def stopTest(self,test):
        super().stopTest(test)
        snapshot('stop',test=test.id())

names=[
    'tests.test_00_trade_workflow_experience',
    'tests.test_rebuild_discovery_browser',
    'tests.test_rebuild_roster_space_browser',
]
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
result=unittest.TextTestRunner(verbosity=2,resultclass=Observed).run(suite)
events = dict(line.split() for line in (cg/'memory.events').read_text().splitlines())
record=dict(commit=git('rev-parse','HEAD'),tree=git('rev-parse','HEAD^{tree}'), tests=result.testsRun,
    passed=result.wasSuccessful() and not result.skipped and result.testsRun==10,
    errors=len(result.errors),failures=len(result.failures),
    peak=int((cg/'memory.peak').read_text()),events=events)
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n')
raise SystemExit(not record['passed'])
