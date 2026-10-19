import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import contract as c,one_phase,minimal_download
P=c.read(c.HERE/'PROTOCOL.json')

def runtime_fixture():
 g={'passed':True,'checks':{},'runs':{}}
 for case in P['cases']:
  run=case['run_id'];g['runs'][run]={'NFE':20,'callback_count':20,'Euler_updates':20}
  for suffix in ('_actual_reference_equal_P0','_actual_initial_AV_noise_equal_P0','_20_actual_forwards','_actual_noise'):g['checks'][run+suffix]=True
 return g

class Pairing(unittest.TestCase):
 def test_actual_paired_runtime_gate_complete(self):self.assertTrue(c.check_runtime_gate(runtime_fixture(),P))
 def test_missing_false_runtime_equality_hard(self):
  for mode in ('missing','false','updates','missing_case'):
   g=runtime_fixture();run=P['cases'][0]['run_id']
   if mode=='missing':del g['checks'][run+'_actual_reference_equal_P0']
   if mode=='false':g['checks'][run+'_actual_initial_AV_noise_equal_P0']=False
   if mode=='updates':g['runs'][run]['Euler_updates']=21
   if mode=='missing_case':del g['runs'][run]
   with self.assertRaises(ValueError):c.check_runtime_gate(g,P)
 def test_pending_formal_deploy_refuses_before_network(self):
  with patch.object(one_phase.base,'P',dict(P,producer_state='PENDING_FORMAL_DEPLOYMENT')),patch.object(one_phase.subprocess,'run') as invoke,self.assertRaisesRegex(ValueError,'PENDING'):one_phase.prepare()
  invoke.assert_not_called()
 def test_P1_is_bundled_template_original_task_unchanged(self):
  producer=c.read(c.HERE.parents[1]/'configs/scientific_contract.json')
  self.assertTrue(c.check_declared_cases(P,producer))
  q=copy.deepcopy(P);q['cases'][0]['prompt']=q['cases'][0]['original_task']['edit_prompt']
  with self.assertRaises(ValueError):c.check_declared_cases(q,producer)
 def test_actual_original_source_scores_five_byte_bound(self):
  b=c.read(c.HERE/'SOURCE_SCORE_BINDINGS.json')
  self.assertEqual(set(b),set(P['source_order']))
  for case in P['cases']:
   row=copy.deepcopy(b[case['source_id']]);remap={case['source_id']:row}
   for file in row['files'].values():file['remote_file']=file['remote_file'] if str(c.HERE.parents[1])==P['root_remote'] else file['local_file']
   self.assertEqual(c.source_score_binding(case,remap)['valid_frames'],case['valid_frame_count'])
   row['files']['source_score.mp4']['sha256']='0'*64
   with self.assertRaises(ValueError):c.source_score_binding(case,remap)
 def test_minimal_download_retains_PT_and_originals_remote(self):
  for name in ('inputs/source.mp4','input/source.mp4','audit/x0/run/x0_step000.pt','configs/parents/a.pt'):
   self.assertFalse(minimal_download.original_selected(name),name)
  for name in ('output/run.mp4','logs/run_job.json','configs/scientific_contract.json','audit/x0/run/manifest.json'):
   self.assertTrue(minimal_download.original_selected(name),name)
  self.assertFalse(minimal_download.derived_selected('final/run/source_score.mp4'))
  self.assertTrue(minimal_download.derived_selected('final/run/edited_score.mp4'))
 def test_remote_fail_does_not_make_zero_score(self):
  import consume
  with self.assertRaises(ValueError):consume.result(type('Result',(),{'returncode':1,'stdout':'{"score":0}'})())

class ServiceBinding(unittest.TestCase):
 def test_actual_service_identity_is_not_only_pid(self):
  import bind_actual
  a={'uid':7,'start_ticks':'123','cmdline':'exact command '}
  self.assertTrue(bind_actual.validate_service_identity(a,dict(a),7))
  for k,v in [('uid',8),('start_ticks','124'),('cmdline','other command ')]:
   with self.assertRaises(ValueError):bind_actual.validate_service_identity(a,dict(a,**{k:v}),7)
 def test_formal_pending_preparation_is_not_deployment(self):
  import bind_actual
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);p=dict(P,root_remote=str(root));c.save(root/'deploy_manifest.json',{'status':'CPU_PREPARATION_GPU_PENDING','files':{}})
   with self.assertRaisesRegex(ValueError,'formal root'):bind_actual.validate_deployed(root,p)

if __name__=='__main__':unittest.main()
