import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import r78_contract as c
spec=importlib.util.spec_from_file_location('root_run_pair',ROOT/'audit/root_run_pair.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class LocalEdit(unittest.TestCase):
 def test_same_original_numerical_graph(self):
  case=c.read(ROOT/'configs/scientific_contract.json')['cases'][0]
  parent=c.read(ROOT/case['parent_graph']);actual=c.read(ROOT/'configs/graphs'/(case['run_id']+'.json'))
  for n,key in [('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir'),('5','run_id'),('6','run_id'),('50','run_id'),('51','run_id'),('52','run_id'),('51','source_run_id'),('6','pair_id'),('14','filename_prefix')]:
   parent[n]['inputs'][key]=actual[n]['inputs'][key]='ADMIN'
  self.assertEqual(actual,parent)
 def test_p1_task_preserves_source_objects(self):
  s=c.read(ROOT/'configs/scientific_contract.json');p=c.prompt_values()['p1'];task=s['cases'][0]['original_task']
  for key in ['edit_prompt','source_prompt','target_prompt']:self.assertIn(task[key],p)
  for text in ['[video editing]','same man','original room','wooden furniture','small cup','sipping action']:self.assertIn(text,p)
  self.assertNotIn('<Picture',p)
 def test_only_two_native_jobs(self):
  jobs,order=c.registry();self.assertEqual(len(jobs),2)
  for run in order:self.assertEqual(c.read(ROOT/'configs/graphs'/(run+'.json'))['50']['inputs']['mode'],'native')
  self.assertTrue(c.read(ROOT/'configs/queue.json')['finalize'])
 def test_peer_generation_mismatch_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d).resolve();root=base/'r78';peer=base/'r74';(peer/'processes').mkdir(parents=True)
   (peer/'processes/service.json').write_text(json.dumps({'pid':77,'identity':{'uid':os.getuid(),'start_ticks':'1','cmdline':'x'}}))
   with patch.object(runner,'ROOT',root),patch.object(runner.service,'current_identity',return_value={'uid':os.getuid(),'start_ticks':'2','cmdline':'x'}):
    with self.assertRaisesRegex(ValueError,'generation changed'):runner.live_peers([peer])
 def test_absent_peer_not_registered(self):
  with tempfile.TemporaryDirectory() as d:
   base=Path(d).resolve();root=base/'r78';peer=base/'r74';(peer/'processes').mkdir(parents=True)
   (peer/'processes/service.json').write_text(json.dumps({'pid':77,'identity':{}}))
   with patch.object(runner,'ROOT',root),patch.object(runner.service,'current_identity',return_value=None):self.assertEqual(runner.live_peers([peer]),[])

if __name__=='__main__':unittest.main()
