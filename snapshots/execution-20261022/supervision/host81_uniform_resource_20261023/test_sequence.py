import unittest
from sequence_guard import sequence_ready
class Tests(unittest.TestCase):
 def setUp(self):self.states={'first':{'status':'completed'}};self.result={'status':'passed','job':'first'};self.snap={'worker':{'state':'exited'},'service':{'state':'exited'},'locks':{'worker':False,'runner':False},'port_listening':False}
 def test_ready(self):self.assertTrue(sequence_ready(self.states,self.result,self.snap))
 def test_audit_required(self):self.result['status']='failed';self.assertFalse(sequence_ready(self.states,self.result,self.snap))
 def test_worker_required(self):self.snap['worker']['state']='owned_alive';self.assertFalse(sequence_ready(self.states,self.result,self.snap))
 def test_service_required(self):self.snap['service']['state']='owned_alive';self.assertFalse(sequence_ready(self.states,self.result,self.snap))
 def test_lock(self):self.snap['locks']['runner']=True;self.assertFalse(sequence_ready(self.states,self.result,self.snap))
 def test_api(self):self.snap['port_listening']=True;self.assertFalse(sequence_ready(self.states,self.result,self.snap))
 def test_completed(self):self.states['first']['status']='submitted';self.assertFalse(sequence_ready(self.states,self.result,self.snap))
if __name__=='__main__':unittest.main()

class PeakTests(unittest.TestCase):
 def test_peak(self):
  from sequence_guard import verify_peak
  import tempfile,json
  from pathlib import Path
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=r/'audit/memory';d.mkdir(parents=True);p=d/'capacity20_12.json';cap=int(19.5*1024**3)
   p.write_text(json.dumps({'pid':12,'cap_bytes':cap,'max_allocated_bytes':10,'max_reserved_bytes':20}))
   self.assertEqual(verify_peak(r,{'pid':12})['max_reserved_bytes'],20)
   p.write_text(json.dumps({'pid':12,'cap_bytes':cap,'max_allocated_bytes':10,'max_reserved_bytes':cap+1}))
   with self.assertRaises(AssertionError):verify_peak(r,{'pid':12})
 def test_missing_peak(self):
  from sequence_guard import verify_peak
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(FileNotFoundError):verify_peak(Path(t),{'pid':12})
