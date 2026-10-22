import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r123_contract as c
import predecessor as pred
class Contract(unittest.TestCase):
 def test_registry(self):
  jobs,order=c.registry();self.assertEqual(len(order),2);self.assertTrue(all(j['seed']==2026101703 for j in jobs.values()))
 def test_prompt_exact_template(self):
  s=c.read(ROOT/'configs/scientific_contract.json');p=s['cases'][0]['prompt'];self.assertEqual(p.count('Replace the man with an elderly woman'),1);self.assertEqual([x for x in ('subject_definitions:','summary:','retention_analysis:') if x in p],['subject_definitions:','summary:','retention_analysis:']);self.assertNotIn('Source caption:',p);self.assertNotIn('mask',p.lower())
 def test_only_prompt_and_administration_diff(self):
  rows=c.read(ROOT/'design/SCIENTIFIC_DIFF.json')['differences'];allowed={'/5/inputs/prompt','/14/inputs/filename_prefix','/5/inputs/audit_dir','/5/inputs/run_id','/50/inputs/audit_dir','/50/inputs/run_id','/51/inputs/run_id','/51/inputs/source_audit_dir','/51/inputs/source_run_id','/52/inputs/output_dir','/52/inputs/run_id','/6/inputs/audit_dir','/6/inputs/pair_id','/6/inputs/run_id'};self.assertEqual({x['path'] for x in rows},allowed)
 def test_noise_1703(self):
  n=c.read(ROOT/'configs/parent_noise.json');self.assertEqual(n['signature']['seed'],2026101703);self.assertEqual(n['source_sha256'],'e3a48ba246e6e9efd9d594b81091e57417dc9c912696b80766af4ffe19b818a9');self.assertEqual(n['actual_noise_streams'],c.read(ROOT/'design/PARENT_NOISE_MANIFEST.json')['actual_noise_streams'])
 def test_route_excludes_pure_padding(self):
  case=c.read(ROOT/'configs/scientific_contract.json')['cases'][0];self.assertEqual(c.routing_layout(case)['pixel_interval_inclusive'],[0,97]);self.assertTrue(c.routing_layout(case)['pure_pad_bins'])
 def test_paired_graph_scope(self):
  cases=c.read(ROOT/'configs/scientific_contract.json')['cases'];a=c.expected_graph(ROOT,cases[0]);b=c.expected_graph(ROOT,cases[1]);self.assertEqual(a['5'],b['5']);self.assertEqual(a['6']['inputs']['pair_id'],b['6']['inputs']['pair_id']);self.assertEqual(b['50']['inputs']['step_start'],6);self.assertEqual(b['50']['inputs']['step_end'],15)
 def test_execution_run_names(self):
  for name in ['scripts/run_queue.py','scripts/job.py','scripts/execution_gate.py','analysis/postrun/verify_pair.py']:
   text=(ROOT/name).read_text();self.assertNotIn('2026101701',text);self.assertNotIn("'r123_'",text)
 def test_prompt_mutation_rejected(self):
  original=c.read
  def altered(p):
   v=original(p)
   if str(p).endswith('scientific_contract.json'):v['cases'][0]['prompt']+=' Move faster.'
   return v
  with patch.object(c,'read',altered),self.assertRaises(ValueError):c.registry()
class Predecessor(unittest.TestCase):
 def fixture(self):
  root=Path('/new');old=Path('/old');attempt=old/'audit'/'done';owner={'pid':2,'identity':{'uid':1004},'gpu_uuid':'gpu','port':1};runtime={'uid':1004,'gpu_uuid':'gpu','port':1,'remote_root':str(old)}
  objects={root/'configs/predecessor.json':{'required':[{'key':'R138','kind':'online_recovery','remote_root':str(old),'producer_seal_sha256':'s','runtime_sha256':'s','required_run':'run'}]},old/'configs/runtime.json':runtime,old/'processes/service.json':owner,attempt/'STARTED.json':{'service':owner,'root_controller':{'pid':1}},attempt/'ROOT_EXIT_RECEIPT.json':{'passed':True,'service':owner,'service_cleanup':{'service_record':owner,'process_absent':True,'own_compute_absent':True},'observer_children':{'all_exact_generations_absent':True,'all_registered_CUDA_pids_absent':True}},attempt/'COMPLETE_REVIEW_HOLD.json':{'passed':True,'run_id':'run','gate_sha256':'s'},old/'analysis/postrun/ONLINE_RUNTIME_GATE.json':{'passed':True,'status':'pass','cleanup_verified':True,'schema':'r138-resumed-online-runtime-gate-v1','service_record':owner,'cases':[{'run':'run'}]}}
  return root,objects
 def runcheck(self,objects,identity=lambda p:None):
  with patch.object(pred,'read',lambda p:copy.deepcopy(objects[Path(p)])),patch.object(pred,'sha',lambda p:'s'):return pred.check(Path('/new'),['R138=done'],current_identity=identity,compute_processes=lambda:[])
 def test_online_complete(self):
  _,d=self.fixture();self.assertTrue(self.runcheck(d)['passed'])
 def test_unreleased_rejected(self):
  _,d=self.fixture();d[Path('/old/audit/done/ROOT_EXIT_RECEIPT.json')]['service_cleanup']['process_absent']=False
  with self.assertRaises(ValueError):self.runcheck(d)
 def test_running_wrapper_rejected(self):
  _,d=self.fixture()
  with self.assertRaises(ValueError):self.runcheck(d,lambda p:{'uid':1004} if p==1 else None)
 def test_missing_completed_rejected(self):
  _,d=self.fixture();del d[Path('/old/audit/done/COMPLETE_REVIEW_HOLD.json')]
  with self.assertRaises(KeyError):self.runcheck(d)
 def test_failed_gate_rejected(self):
  _,d=self.fixture();d[Path('/old/analysis/postrun/ONLINE_RUNTIME_GATE.json')]['passed']=False
  with self.assertRaises(ValueError):self.runcheck(d)
if __name__=='__main__':unittest.main()
