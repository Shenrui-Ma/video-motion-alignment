import copy,importlib.util,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
import r115_contract as c
import preflight,execution_gate,parent_evidence
import verify_pair as vp

class TwoArmContract(unittest.TestCase):
 def test_only_two_new_runs(self):
  jobs,order=c.registry();self.assertEqual(len(order),2);self.assertEqual([jobs[x]['arm'] for x in order],['fixed_one_bin','matched_one_bin']);self.assertTrue(preflight.check()['passed']);self.assertNotIn('native',order)
 def test_numerical_kernels_byte_equal(self):
  rows=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertIn('extensions/H3TemporalRouter/correspondence.py',rows)
  for name,row in rows.items():self.assertEqual(c.sha(ROOT/name),c.sha(ROOT/row['source_file']))
 def test_exact_graph_only_operator_changes(self):
  graphs=[c.read(ROOT/'configs/graphs'/(x+'.json')) for x in c.RUNS]
  for arm,g in zip(c.ARMS,graphs):
   for node in ('6','50','51','52'):g[node]['inputs']['run_id']='common'
   g['14']['inputs']['filename_prefix']='common';g['50']['inputs']['mode']='common'
  self.assertEqual(*graphs)
 def test_own_prefix_first_and_strict_paired_second(self):
  first=c.correspondence_configuration(c.RUNS[0]);second=c.correspondence_configuration(c.RUNS[1])
  self.assertEqual(first['prefix_manifest'],first['paired_prefix_manifest']);self.assertNotIn('paired_root',first)
  self.assertEqual(second['paired_prefix_manifest'],first['prefix_manifest']);self.assertEqual(second['paired_root'],first['root'])
  self.assertNotIn('/data4/',str(first)+str(second))
 def test_historical_reference_keeps_original_runtime(self):
  h=c.read(ROOT/'design/HISTORICAL_NATIVE.json');self.assertFalse(h['same_host_strict_comparison']);self.assertEqual(h['runtime']['host'],'H3_SERVER_B');self.assertEqual(c.read(ROOT/'configs/runtime.json')['host'],'H3_SERVER_A')
 def test_graph_tampering_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for folder in ('configs','design'):shutil.copytree(ROOT/folder,root/folder)
   f=root/'configs/graphs'/(c.RUNS[0]+'.json');g=c.read(f);g['50']['inputs']['step_start']=5;f.write_text(json.dumps(g))
   with self.assertRaises(ValueError):c.registry(root)
 def test_shared_condition_rename_only(self):
  a={'run_id':c.RUNS[0],'condition':{'sha':'abc'},'pair_snapshot':{'source':'shared'}};b=copy.deepcopy(a);b['run_id']=c.RUNS[1]
  self.assertTrue(parent_evidence.comparable_conditions(a,b));b['condition']['sha']='different';self.assertFalse(parent_evidence.comparable_conditions(a,b))
 def test_first_condition_self_scope_and_second_rejects_change(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'audit').mkdir();a={'run_id':c.RUNS[0],'x':1}
   p=parent_evidence.validate_parent_condition(a,'long_0174',root);self.assertEqual(p['comparison'],'self_integrity')
   (root/'audit'/(c.RUNS[0]+'_conditioning.json')).write_text(json.dumps(a))
   b={'run_id':c.RUNS[1],'x':1};p=parent_evidence.validate_parent_condition(b,'long_0174',root);self.assertEqual(p['comparison'],'two_new_arms_exact')
   b['x']=2
   with self.assertRaises(ValueError):parent_evidence.validate_parent_condition(b,'long_0174',root)
 def test_no_root_review_no_gpu_authorization(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'audit').mkdir();(root/'deploy_manifest.json').write_text('{}')
   (root/'audit/GPU_DEPLOYMENT_REVIEW.json').write_text(json.dumps({'approved':True,'reviewer':'root','scope':'r115-two-arm-host9-gpu-execution','producer_seal_sha256':'stale'}))
   with self.assertRaises(ValueError):c.root_gpu_review(root)
 def test_frozen_inputs_shape(self):
  jobs,_=c.registry()
  for row in jobs.values():
   self.assertEqual(row['case']['valid_frame_count'],145);self.assertEqual(row['case']['geometry']['frames'],158);self.assertEqual(row['case']['evaluation_crop_xywh'],[16,8,1280,720])
 def test_noise_requires_declared_seed_and_both_streams(self):
  shapes={'video':(1,2),'audio':(1,1)}
  with tempfile.TemporaryDirectory() as td,mock.patch.object(vp,'SHAPES',shapes):
   root=Path(td);(root/'audit').mkdir();t=[torch.tensor([[1.,2.]]),torch.tensor([[3.]])]
   signatures=[{k:vp.signature(x)[k] for k in ('shape','dtype','sha256')} for x in t]
   sig={'seed':c.SEED,'nested':True,'shapes':[[1,2],[1,1]],'dtypes':['torch.float32']*2,'batch_index':None}
   saved={'signature':sig,'hashes':signatures,'tensors':t};path=root/'audit'/(c.PAIR_ID+'_noise.pt');torch.save(saved,path)
   records=[{'run_id':r,'pair_id':c.PAIR_ID,'signature':copy.deepcopy(sig),'actual_noise_streams':copy.deepcopy(signatures)} for r in c.RUNS]
   vp.compare_initial_noise(root,records)
   records[1]['actual_noise_streams'][0]['sha256']='bad'
   with self.assertRaises(ValueError):vp.compare_initial_noise(root,records)
   saved['signature']['seed']+=1;torch.save(saved,path)
   with self.assertRaises(ValueError):vp.compare_initial_noise(root,records)
 def test_second_submission_requires_first_same_generation(self):
  import job
  owner={'pid':7,'identity':{'uid':1016,'start_ticks':'9'}}
  with tempfile.TemporaryDirectory() as td,mock.patch.object(job,'RUN',Path(td)):
   root=Path(td);(root/'logs').mkdir();j={'status':'success','service_pid':7,'service_identity':owner['identity']};h={'status':{'completed':True,'status_str':'success'}}
   (root/'logs'/(c.RUNS[0]+'_job.json')).write_text(json.dumps(j));(root/'logs'/(c.RUNS[0]+'_history.json')).write_text(json.dumps(h))
   job.require_native_generation({'arm':'matched_one_bin'},owner)
   j['service_pid']=8;(root/'logs'/(c.RUNS[0]+'_job.json')).write_text(json.dumps(j))
   with self.assertRaises(RuntimeError):job.require_native_generation({'arm':'matched_one_bin'},owner)
if __name__=='__main__':unittest.main()
