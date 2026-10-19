import copy,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import r97_contract as c
spec=importlib.util.spec_from_file_location('r85_root_predecessor_test',ROOT/'audit/root_run_control.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PredecessorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  base=Path(self.tmp.name);self.root=base/'new';self.old=base/'old'
  for p in [self.root/'configs',self.old/'processes',self.old/'logs']:p.mkdir(parents=True)
  self.owner={'pid':123,'identity':{'start_ticks':'456'},'gpu_uuid':runner.service.GPU}
  self.config={'root':str(self.old),'service_pid':123,'service_start_ticks':'456','gpu_uuid':runner.service.GPU,'last_run':'final'}
  self.put(self.root/'configs/predecessor.json',self.config);self.put(self.old/'processes/service.json',self.owner)
  self.put(self.old/'logs/final_history.json',{'status':{'completed':True,'status_str':'success'}})
  self.put(self.old/'processes/cleanup.json',{'pid':123,'process_absent':True,'own_compute_absent':True})
 def put(self,p,v):p.write_text(json.dumps(v))
 def check(self,identity=None,rows=()):
  with patch.object(runner,'ROOT',self.root),patch.object(runner.service,'current_identity',return_value=identity),patch.object(runner.service,'compute_processes',return_value=rows):return runner.verify_predecessor()
 def test_successful_final_job_and_exact_release_accepted(self):self.assertEqual(self.check()['owner'],self.owner)
 def test_running_generation_refused(self):
  with self.assertRaisesRegex(ValueError,'still exists'):self.check(self.owner['identity'])
 def test_reused_pid_or_changed_gpu_refused(self):
  for field,value in [('pid',124),('gpu_uuid','GPU-other')]:
   with self.subTest(field=field):
    owner=copy.deepcopy(self.owner);owner[field]=value;self.put(self.old/'processes/service.json',owner)
    with self.assertRaisesRegex(ValueError,'generation/device'):self.check()
 def test_final_failed_or_pending_refused(self):
  for status in [{'completed':False,'status_str':'running'},{'completed':True,'status_str':'error'}]:
   with self.subTest(status=status):
    self.put(self.old/'logs/final_history.json',{'status':status})
    with self.assertRaisesRegex(ValueError,'incomplete'):self.check()
 def test_cuda_still_registered_refused(self):
  with self.assertRaisesRegex(ValueError,'allocation remains'):self.check(rows=[{'pid':123}])
 def test_false_or_wrong_owner_cleanup_refused(self):
  for receipt in [{'pid':124,'process_absent':True,'own_compute_absent':True},{'pid':123,'process_absent':True,'own_compute_absent':False}]:
   with self.subTest(receipt=receipt):
    self.put(self.old/'processes/cleanup.json',receipt)
    with self.assertRaisesRegex(ValueError,'cleanup receipt'):self.check()

if __name__=="__main__":unittest.main()
