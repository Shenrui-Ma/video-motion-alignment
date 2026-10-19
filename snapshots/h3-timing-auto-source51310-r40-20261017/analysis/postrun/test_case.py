"""R40-only bindings, actual imports and independent pixel result scope."""
import ast,copy,hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
import contract as c
import evaluate

class CaseTests(unittest.TestCase):
 def setUp(self):
  self.p=c.read(c.HERE/'PROTOCOL.json');self.root=c.HERE.parents[1]
 def test_frozen_source_windows_and_absent_manual(self):
  self.assertEqual(self.p['project'],40);self.assertEqual(len(self.p['cases']),1)
  case=self.p['cases'][0]
  self.assertEqual((case['source_id'],case['seed'],case['run_id']),('51310',2026101701,'r40_source51310_seed2026101701_auto'))
  self.assertEqual(case['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140]])
  self.assertEqual(self.p['fixed_visual_frames'],[0,24,48,72,96,120,140]);self.assertEqual(self.p['fixed_clip_inclusive'],[0,140])
  self.assertEqual(case['comparators'],['native']);self.assertEqual(set(self.p['parents']),{'native'})
  self.assertEqual((self.p['scan_rows'],self.p['max_lag'],self.p['thresholds']),(186,24,[.3,.5]))
  future=self.p['future_manual_reference'];self.assertEqual(future['status'],'NOT_GENERATED_NOT_EVALUATED');self.assertIs(future['not_current_comparator'],True)
  self.assertEqual(c.sha(c.HERE/future['plan']),future['plan_sha256']);self.assertNotIn('video',future)
 def test_actual_Native_inputs_and_provenance(self):
  parent=self.p['parents']['native'];p=c.HERE/parent['pose'];source=self.root/self.p['source_pose'];native=c.read(p);s=c.read(source)
  self.assertEqual(c.sha(p),parent['pose_sha256']);self.assertEqual(c.sha(source),self.p['source_pose_sha256']);self.assertEqual(native['video']['sha256'],parent['video_sha256']);self.assertEqual(native['provenance'],s['provenance'])
  inv=c.read(self.root/'configs/parent_file_inventory.json');name='output/'+self.p['cases'][0]['parent_run']+'_00001_.mp4';self.assertEqual(inv[name]['sha256'],parent['video_sha256'])
  job=c.read(c.HERE/parent['job']);self.assertEqual(job['status'],'success');self.assertEqual(job['name'],self.p['cases'][0]['parent_run']);self.assertEqual(c.sha(c.HERE/parent['job']),parent['job_sha256'])
  self.assertEqual(c.sha(self.root/'deploy_manifest.json'),self.p['producer_manifest_sha256']);self.assertEqual(c.sha(self.root/'configs/protocol.json'),self.p['producer_protocol_sha256'])
 def test_generated_provenance_changes_rejected(self):
  s=c.read(self.root/'configs/source.pose.json')['provenance'];self.assertTrue(evaluate.check_provenance(s,s,[s],'video')['exact'])
  for key in s:
   altered=copy.deepcopy(s);altered[key]='not-original'
   with self.subTest(key=key),self.assertRaises(ValueError):evaluate.check_provenance(s,altered,[s],'video')
 def test_RGB_mismatch_preserved_without_claiming_AV_failure(self):
  a=['a']*141;b=a.copy();b[70]='b'
  result=evaluate.pixel_outcome(True,a,b);self.assertIs(result['all_OFF_141RGB_equal'],False);self.assertIs(result['actual_141RGB_equal_to_Native'],False);self.assertEqual(result['all_OFF_final_AV'],'independently checked by verify_single')
  self.assertIs(evaluate.pixel_outcome(True,a,a)['all_OFF_141RGB_equal'],True)
  self.assertIsNone(evaluate.pixel_outcome(False,a,b)['all_OFF_141RGB_equal'])
  with self.assertRaises(ValueError):evaluate.pixel_outcome(True,a,b[:-1])
 def test_original_metric_functions_byte_AST_equivalent(self):
  old=Path('/Users/researcher/DevProjects/h3-timing-auto-bedside-r35-20261017/analysis/postrun/evaluate.py')
  def defs(p):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef)}
  before,after=defs(old),defs(c.HERE/'evaluate.py')
  for name in ('fixed_metrics','region_sets','common_regions','media_and_pixels'):self.assertEqual(before[name],after[name],name)
 def test_readonly_single_verifier_helpers_exact(self):
  def defs(p):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef)}
  before,after=defs(self.root/'scripts/verify_completed.py'),defs(c.HERE/'verify_single.py')
  for name in ('check_record_semantics','check_submission','check_owner_evidence'):self.assertEqual(before[name],after[name])
  source=(c.HERE/'verify_single.py').read_text();self.assertIn('validate_job(run,root,inputs=False)',source);self.assertIn('case[\'run_id\']!=run_id:continue',source)
 def test_no_default_execution_or_root_approval(self):
  b=c.read(c.HERE/'BINDING.template.json');self.assertIs(b['approved_for_consumer_start'],False);self.assertIsNone(b['service_record']);self.assertEqual(b['protocol_sha256'],c.sha(c.HERE/'PROTOCOL.json'))
  e=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
  r=subprocess.run([sys.executable,str(c.HERE/'one_phase.py')],env=e,capture_output=True,text=True,timeout=20)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('Prepared only',r.stdout)
 def test_all_imports_fresh_process_without_GPU(self):
  e=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
  code="import sys;sys.path.insert(0,"+repr(str(c.HERE))+ ");import contract,consume,one_phase,remote_consume,evaluate,verify_single;sys.path.insert(0,"+repr(str(self.root/'scripts'))+");import timing_metrics,pairwise_gain,physical_tolerance,scan_current_pose;print('ALL_IMPORTS_PASS')"
  r=subprocess.run([sys.executable,'-c',code],env=e,capture_output=True,text=True,timeout=30)
  self.assertEqual(r.returncode,0,r.stderr);self.assertIn('ALL_IMPORTS_PASS',r.stdout)

if __name__=='__main__':unittest.main()
