import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from gpu_coexistence import assess,task_cuda_absent

PEER=dict(pid=123,uid=1004,start_ticks='456',cmdline_sha256='abc',gpu_uuid='gpu5')

class CoexistenceTests(unittest.TestCase):
 def test_existing_service_and_selected_two_devices(self):
  r=assess([PEER],'gpu7',[PEER]);self.assertTrue(r['passed']);self.assertEqual(r['observed_owned_cuda'][0]['classification'],'verified pre-existing service')
 def test_unknown_addition_uses_capacity_and_device_count(self):
  other=dict(PEER,pid=124,cmdline_sha256='def')
  r=assess([PEER,other],'gpu7',[PEER]);self.assertTrue(r['passed']);self.assertIn('capacity assessed',r['observed_owned_cuda'][1]['classification'])
 def test_third_owned_device_rejected(self):
  self.assertFalse(assess([PEER,dict(PEER,pid=124,gpu_uuid='gpu6')],'gpu7',[PEER])['passed'])
 def test_other_users_devices_not_counted(self):
  r=assess([PEER,dict(PEER,pid=789,uid=1008,gpu_uuid='gpu1')],'gpu7',[PEER]);self.assertTrue(r['passed']);self.assertEqual(len(r['observed_owned_cuda']),1)
 def test_identity_mismatch_observed_not_whitelisted(self):
  r=assess([dict(PEER,start_ticks='999')],'gpu7',[PEER]);self.assertTrue(r['passed']);self.assertIn('other observed',r['observed_owned_cuda'][0]['classification'])
 def test_final_release_only_our_exact_identity(self):
  task=dict(PEER,pid=456,gpu_uuid='gpu7')
  self.assertTrue(task_cuda_absent([PEER],[task]));self.assertFalse(task_cuda_absent([PEER,task],[task]))
 def test_pid_reuse_is_different_process(self):
  self.assertTrue(task_cuda_absent([dict(PEER,start_ticks='999')],[PEER]))

if __name__=='__main__':unittest.main()
