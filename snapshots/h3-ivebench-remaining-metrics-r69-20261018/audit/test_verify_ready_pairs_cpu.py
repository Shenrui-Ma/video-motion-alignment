import json
from pathlib import Path
import tempfile
import unittest
from verify_ready_pairs_cpu import readiness
class ReadyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);(self.root/'logs').mkdir()
 def tearDown(self):self.temp.cleanup()
 def write(self,method,kind,value):
  path=self.root/'logs'/('r69_short_0230_seed2026101701_'+method+'_'+kind+'.json');path.write_text(json.dumps(value));return path
 def complete(self,method):
  self.write(method,'history',{'status':{'completed':True,'status_str':'success'}});self.write(method,'job',{'status':'success'})
 def test_pending_without_pair(self):
  self.complete('native');self.assertEqual(readiness(self.root,'short_0230'),'PENDING')
 def test_complete_pair(self):
  self.complete('native');self.complete('forced');self.assertEqual(readiness(self.root,'short_0230'),'READY')
 def test_incomplete_write_is_pending(self):
  self.complete('native');self.complete('forced');self.write('forced','history',{}).write_text('{');self.assertEqual(readiness(self.root,'short_0230'),'PENDING_WRITING')
 def test_failed_job_is_not_verified(self):
  self.complete('native');self.complete('forced');self.write('forced','job',{'status':'failed'});self.assertEqual(readiness(self.root,'short_0230'),'PRODUCER_FAILED')
 def test_negative_gate_never_retried(self):
  p=self.root/'analysis/postrun/short_0230/PAIR_RUNTIME_GATE.json';p.parent.mkdir(parents=True);p.write_text('{"passed":false}')
  with self.assertRaises(ValueError):readiness(self.root,'short_0230')
 def test_positive_gate_is_not_rerun(self):
  p=self.root/'analysis/postrun/short_0230/PAIR_RUNTIME_GATE.json';p.parent.mkdir(parents=True);p.write_text('{"passed":true}');self.assertEqual(readiness(self.root,'short_0230'),'PASSED')
if __name__=='__main__':unittest.main()
