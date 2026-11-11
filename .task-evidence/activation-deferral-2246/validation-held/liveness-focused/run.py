from pathlib import Path
import unittest,sys,json,time,hashlib,os
sys.path[:0]=['/app/tests','/app']
from src.platform.lifecycle import memory_snapshot
samples=[]
class Measured(unittest.TextTestResult):
 def startTest(self,test):
  samples.append(dict(event='start',test=test.id(),at=time.time(),memory=memory_snapshot(),cpu=Path('/sys/fs/cgroup/cpu.stat').read_text()))
  super().startTest(test)
 def stopTest(self,test):
  samples.append(dict(event='stop',test=test.id(),at=time.time(),memory=memory_snapshot(),cpu=Path('/sys/fs/cgroup/cpu.stat').read_text()))
  super().stopTest(test)
suite=unittest.defaultTestLoader.loadTestsFromName('test_projection_audit')
result=unittest.TextTestRunner(verbosity=2,resultclass=Measured).run(suite)
proof=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),passed=result.wasSuccessful(),memory=memory_snapshot(),samples=samples,scope='One fresh execution of the entire unchanged projection-audit module. Not a replacement for the failed complete canonical gate. No retries or latency/timeout changes.')
Path('/output/result.json').write_text(json.dumps(proof,indent=2)+'\n')
sys.exit(not result.wasSuccessful())
