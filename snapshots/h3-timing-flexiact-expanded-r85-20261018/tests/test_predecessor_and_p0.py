import copy,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import r85_contract as c
spec=importlib.util.spec_from_file_location('r85_root_predecessor_test',ROOT/'audit/root_run_batch.py')
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

class PromptPriorityTests(unittest.TestCase):
 def test_one_leg_first_has_exact_r72_successful_p0(self):
  jobs,order=c.registry();first=jobs[order[0]]['case']
  self.assertEqual((first['pair_key'],first['prompt_version']),('one_leg__movie_man_9','P0'))
  self.assertEqual(first['prompt'],c.read(ROOT/'design/R72_P0_ANCESTRY/actual_graph.json')['5']['inputs']['prompt'])
  self.assertEqual(first['prompt_sha256'],'450b160dcbfd7c16dd7310b7f7d8c92e8599a11fa746afb635455c109761b78e')
  self.assertEqual([jobs[r]['case']['prompt_version'] for r in order],['P0','P0','P1','P1','P1','P1'])
 def test_p0_ancestry_alteration_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for folder in ['configs','design']:shutil.copytree(ROOT/folder,root/folder)
   p=root/'design/R72_P0_ANCESTRY/p0.txt';p.write_text(p.read_text()+'changed')
   with self.assertRaisesRegex(ValueError,'ancestry changed'):c.prompt_values(root,c.PAIR_KEYS[0])

if __name__=='__main__':unittest.main()
