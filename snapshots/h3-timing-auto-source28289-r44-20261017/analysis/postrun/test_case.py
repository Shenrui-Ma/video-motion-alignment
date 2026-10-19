"""New source bindings and normal-preservation scope, without model execution."""
import ast,copy,os,subprocess,sys,unittest
from pathlib import Path
import contract as c
import evaluate

class CaseTests(unittest.TestCase):
 def setUp(self):
  self.p=c.read(c.HERE/'PROTOCOL.json');self.root=c.HERE.parents[1]
 def test_normal_case_and_complete_fixed_assessment(self):
  p=self.p;self.assertEqual(p['project'],44);self.assertEqual(len(p['cases']),1);case=p['cases'][0]
  self.assertEqual((case['source_id'],case['seed'],case['run_id']),('28289',2026101701,'r44_source28289_seed2026101701_auto'))
  self.assertEqual(case['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140]])
  self.assertEqual(case['descriptive_windows'],[[0,140]]);self.assertEqual(p['fixed_visual_frames'],[0,24,48,72,96,120,140])
  self.assertEqual(p['fixed_clip_inclusive'],[0,140]);self.assertEqual(case['comparators'],['native']);self.assertEqual(set(p['parents']),{'native'})
  self.assertEqual((p['scan_rows'],p['max_lag'],p['thresholds']),(186,24,[.3,.5]))
  self.assertEqual(p['case_role'],c.read(self.root/'configs/CASE_ROLE_ADDENDUM.json'))
  self.assertEqual(p['future_manual_reference']['status'],'NOT_PLANNED_NOT_GENERATED_NOT_EVALUATED');self.assertNotIn('video',p['future_manual_reference']);self.assertNotIn('plan',p['future_manual_reference'])
 def test_actual_parent_entities_and_source_provenance(self):
  parent=self.p['parents']['native'];pose=c.HERE/parent['pose'];source=self.root/self.p['source_pose'];n,s=c.read(pose),c.read(source)
  self.assertEqual(c.sha(pose),parent['pose_sha256']);self.assertEqual(c.sha(source),self.p['source_pose_sha256']);self.assertEqual(n['video']['sha256'],parent['video_sha256']);self.assertEqual(n['provenance'],s['provenance'])
  inventory=c.read(self.root/'configs/parent_file_inventory.json');self.assertEqual(inventory['output/'+self.p['cases'][0]['parent_run']+'_00001_.mp4']['sha256'],parent['video_sha256'])
  job=c.read(c.HERE/parent['job']);self.assertEqual(job['status'],'success');self.assertEqual(job['name'],self.p['cases'][0]['parent_run']);self.assertEqual(c.sha(c.HERE/parent['job']),parent['job_sha256'])
  self.assertEqual(c.sha(self.root/'deploy_manifest.json'),self.p['producer_manifest_sha256']);self.assertEqual(c.sha(self.root/'configs/protocol.json'),self.p['producer_protocol_sha256'])
  evidence=c.read(c.HERE/'EVIDENCE_BINDING.json')
  for name,sha in evidence['parent_archive_closure'].items():self.assertEqual(c.sha(self.root/'configs'/name),sha)
 def test_provenance_mismatch_is_technical_failure(self):
  p=c.read(self.root/'configs/source.pose.json')['provenance'];self.assertTrue(evaluate.check_provenance(p,p,[p],'video')['exact'])
  for name in p:
   bad=copy.deepcopy(p);bad[name]='changed'
   with self.subTest(field=name),self.assertRaises(ValueError):evaluate.check_provenance(p,bad,[p],'video')
 def test_RGB_and_latent_outcomes_separate(self):
  a=['a']*141;b=a.copy();b[70]='different'
  r=evaluate.pixel_outcome(True,a,b);self.assertIs(r['all_OFF_141RGB_equal'],False);self.assertEqual(r['all_OFF_final_AV'],'independently checked by verify_single');self.assertTrue(r['RGB_equality_is_not_inferred_from_latents'])
  self.assertIs(evaluate.pixel_outcome(True,a,a)['all_OFF_141RGB_equal'],True)
  self.assertIsNone(evaluate.pixel_outcome(False,a,b)['all_OFF_141RGB_equal'])
  with self.assertRaises(ValueError):evaluate.pixel_outcome(True,a,b[:-1])
 def test_frozen_math_and_lifecycle_functions_reused(self):
  parent=Path('/Users/researcher/DevProjects/h3-timing-auto-source51310-r40-20261017/analysis/postrun')
  def defs(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
  before,after=defs(parent/'evaluate.py'),defs(c.HERE/'evaluate.py')
  for name in ('check_provenance','pixel_outcome','fixed_metrics','region_sets','common_regions','media_and_pixels'):self.assertEqual(before[name],after[name],name)
  for name in ('contract.py','remote_consume.py','consume.py','test_phase_dependencies.py','test_postrun.py'):self.assertEqual((parent/name).read_bytes(),(c.HERE/name).read_bytes(),name)
 def test_readonly_single_verifier_actual87366(self):
  def defs(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
  before,after=defs(self.root/'scripts/verify_completed.py'),defs(c.HERE/'verify_single.py')
  for name in ('check_record_semantics','check_submission','check_owner_evidence'):self.assertEqual(before[name],after[name],name)
  text=(c.HERE/'verify_single.py').read_text();self.assertIn('from r44_contract import validate_job',text);self.assertIn('validate_job(run,root,inputs=False)',text)
  condition=c.read(self.root/'configs/parent_conditioning.json');self.assertEqual(condition['packed_layout']['seq_len'],87366)
 def test_no_default_execution_or_placeholder_approval(self):
  b=c.read(c.HERE/'BINDING.template.json');self.assertIs(b['approved_for_consumer_start'],False);self.assertIsNone(b['service_record']);self.assertEqual(b['protocol_sha256'],c.sha(c.HERE/'PROTOCOL.json'))
  result=subprocess.run([sys.executable,str(c.HERE/'one_phase.py')],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=20)
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Prepared only',result.stdout)
 def test_fresh_import_no_GPU_or_consumer(self):
  env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
  code='import sys;sys.path.insert(0,'+repr(str(c.HERE))+');import contract,consume,one_phase,remote_consume,evaluate,verify_single;sys.path.insert(0,'+repr(str(self.root/'scripts'))+');import timing_metrics,pairwise_gain,physical_tolerance,scan_current_pose;print("ALL_IMPORTS_PASS")'
  result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
  self.assertEqual(result.returncode,0,result.stderr);self.assertIn('ALL_IMPORTS_PASS',result.stdout)
if __name__=='__main__':unittest.main()
