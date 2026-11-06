"""Bounded diagnostic sampling of the unchanged test; not release acceptance."""
import concurrent.futures,json,unittest,sys
sys.path.insert(0, "/app")
from pathlib import Path
from unittest.mock import patch
from tests.test_fois_navigation_reliability import WorkerTimeoutReliabilityTests
original=concurrent.futures.Future.cancel
records=[]
def observe(self):
    before={'running':self.running(),'done':self.done(),'cancelled':self.cancelled()}
    answer=original(self)
    records.append(dict(before=before,cancel_return=answer))
if __name__=='__main__':
    outcomes=[]
    for sample in range(5):
        start=len(records)
        suite=unittest.TestSuite([WorkerTimeoutReliabilityTests('test_cancellation_during_submission_drains_handle_then_stops_writer')])
        with patch.object(concurrent.futures.Future,'cancel',observe):
            result=unittest.TextTestRunner(verbosity=2).run(suite)
        outcomes.append(dict(sample=sample,passed=result.wasSuccessful(),failures=result.failures,errors=result.errors,cancellations=records[start:]))
    # Only error text, never TestCase repr or private data.
    rows=[{**x,'failures':[t for _,t in x['failures']],'errors':[t for _,t in x['errors']]} for x in outcomes]
    Path('/evidence/cancellation-diagnostic.json').write_text(json.dumps(dict(scope='Five unchanged real-worker diagnostic trials; observations do not replace mandatory full regression',trials=rows),indent=2)+'\n')
