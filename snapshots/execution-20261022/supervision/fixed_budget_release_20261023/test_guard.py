import unittest
from guard import may_append
class Tests(unittest.TestCase):
 def setUp(self):self.states={'first':{'status':'completed'}};self.snap={'worker':{'state':'exited'},'service':{'state':'exited'},'locks':{'worker':False},'port_listening':False}
 def test_idle(self):self.assertTrue(may_append(self.states,'first',self.snap))
 def test_worker(self):self.snap['worker']['state']='owned_alive';self.assertFalse(may_append(self.states,'first',self.snap))
 def test_service(self):self.snap['service']['state']='owned_alive';self.assertFalse(may_append(self.states,'first',self.snap))
 def test_lock(self):self.snap['locks']['worker']=True;self.assertFalse(may_append(self.states,'first',self.snap))
 def test_api(self):self.snap['port_listening']=True;self.assertFalse(may_append(self.states,'first',self.snap))
 def test_state(self):self.states['first']['status']='submitted';self.assertFalse(may_append(self.states,'first',self.snap))
if __name__=='__main__':unittest.main()
