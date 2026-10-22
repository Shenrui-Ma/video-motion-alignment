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
