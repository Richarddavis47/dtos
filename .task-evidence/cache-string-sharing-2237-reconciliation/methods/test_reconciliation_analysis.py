import copy,json,unittest
from pathlib import Path
import reconciliation_analysis as m
root=Path('/evidence/reconciliation')
class PairIntegrityTests(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((root/'oneqb-standard-2.json').read_text());self.b=json.loads((root/'oneqb-shipping-2.json').read_text())
 def reject(self,key,value):
  b=copy.deepcopy(self.b);b[key]=value
  with self.assertRaises((AssertionError,KeyError)):m.verify_pair(self.a,b)
 def test_real_matching_pair(self):self.assertEqual(m.verify_pair(self.a,self.b)['fixture'],'oneqb')
 def test_digest_substitution_rejected(self):self.reject('digest_helper_unmodified',False)
 def test_digest_source_difference_rejected(self):self.reject('digest_helper_sha256','changed')
 def test_instrumentation_difference_rejected(self):self.reject('instrumentation_sha256','changed')
 def test_source_tree_difference_rejected(self):self.reject('tree','changed')
 def test_payload_difference_rejected(self):self.reject('payload_sha256','changed')
 def test_published_value_difference_rejected(self):self.reject('full_publication_digest','changed')
 def test_instrumentation_dominated_peak_rejected(self):self.reject('prior_kernel_peak',self.b['operation_kernel_peak'])
 def test_incomplete_cleanup_rejected(self):self.reject('scratch_removed',False)
 def test_orphan_child_rejected(self):self.reject('children_after',[123])
 def test_wrong_limit_rejected(self):self.reject('enforced_limit',4*1024**3)
 def test_oom_rejected(self):
  b=copy.deepcopy(self.b);b['stages'][0]['cgroup_memory_events']['oom_kill']=1
  with self.assertRaises(AssertionError):m.verify_pair(self.a,b)
if __name__=='__main__':unittest.main(verbosity=2)
