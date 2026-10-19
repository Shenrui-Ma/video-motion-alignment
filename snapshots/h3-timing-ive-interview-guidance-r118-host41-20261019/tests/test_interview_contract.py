import copy, importlib.util, json, shutil, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
import r118_contract as c
import verify_pair as v
import preflight
from execution_gate import seal

class InterviewContract(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();r=Path(t.name)
  for name in ('configs','design','inputs','scripts','extensions','source_snapshot','tests','analysis/postrun'):
   shutil.copytree(ROOT/name,r/name,ignore=shutil.ignore_patterns('__pycache__'))
  return t,r
 def mutate(self,rel,fn):
  t,r=self.fixture()
  try:
   p=r/rel;d=c.read(p);fn(d);p.write_text(json.dumps(d));c.registry(r)
  finally:t.cleanup()
 def test_single_new_forced_only(self):
  rows,order=c.registry();self.assertEqual(order,['r118_long_0047_seed2026101701_forced']);self.assertEqual(rows[order[0]]['arm'],'forced')
 def test_no_extra_native_queue(self):
  with self.assertRaisesRegex(ValueError,'queue'):
   self.mutate('configs/queue.json',lambda x:x['jobs'].append('fresh_native'))
 def test_parent_prompt_exact(self):
  row=next(iter(c.registry()[0].values()));g=c.expected_graph(ROOT,row['case']);self.assertEqual(g['5']['inputs']['prompt'],c.read(ROOT/'design/historical_native/native_graph.json')['5']['inputs']['prompt'])
 def test_prompt_mutation_rejected(self):
  with self.assertRaisesRegex(ValueError,'graph'):
   self.mutate('configs/graphs/r118_long_0047_seed2026101701_forced.json',lambda x:x['5']['inputs'].update(prompt='different'))
 def test_seed_mutation_rejected(self):
  with self.assertRaisesRegex(ValueError,'graph'):
   self.mutate('configs/graphs/r118_long_0047_seed2026101701_forced.json',lambda x:x['6']['inputs'].update(noise_seed=9))
 def test_guide_schedule_mutation_rejected(self):
  with self.assertRaisesRegex(ValueError,'graph'):
   self.mutate('configs/graphs/r118_long_0047_seed2026101701_forced.json',lambda x:x['50']['inputs'].update(step_start=5))
 def test_historical_native_evidence_passes(self):self.assertTrue(c.verify_historical_native()['passed'])
 def test_historical_native_evidence_tamper(self):
  with self.assertRaisesRegex(ValueError,'historical evidence'):
   self.mutate('design/historical_native/native_job.json',lambda x:x.update(status='error'))
 def test_source_plan_tamper(self):
  with self.assertRaisesRegex(ValueError,'source event plan'):
   self.mutate('design/SOURCE_REVIEW_PLAN.json',lambda x:x.update(extra='changed'))
 def test_routing_padding_derived_from_frame_support(self):
  case=c.definitions()[0];route=c.routing_layout(case);sizes=[(1,4,4,4,4)[i%5] for i in range(32)];starts=[];n=0
  for size in sizes:starts.append(n);n+=size
  expected=sum(start<97 for start in starts)
  self.assertEqual(route['latent_interval_half_open'],[0,expected]);self.assertEqual(route['position_bin_coverage_inclusive'],[0,sum(sizes[:expected])-1]);self.assertEqual(route['pure_pad_bins'],[29,30,31])
 def test_current_source_and_noise_match_old_raw_data(self):
  old=c.read(ROOT/'design/historical_native/binding_00.json');noise=c.read(ROOT/'design/historical_native/binding_01.json')
  self.assertTrue(all(v.source_inputs_match(old,noise,ROOT).values()))
 def test_noisy_stream_change_rejected(self):
  old=c.read(ROOT/'design/historical_native/binding_00.json');noise=c.read(ROOT/'design/historical_native/binding_01.json');noise['actual_noise_streams'][0]['sha256']='bad'
  self.assertFalse(v.source_inputs_match(old,noise,ROOT)['initial_AV_noise_matches_R96_source'])
 def test_encoded_feature_difference_is_recorded_not_crosshost_gate(self):
  old=c.read(ROOT/'design/historical_native/binding_00.json');noise=c.read(ROOT/'design/historical_native/binding_01.json');old['native_vae_calls'][0]['latent']['sha256']='host_specific'
  self.assertTrue(all(v.source_inputs_match(old,noise,ROOT).values()))
 def test_pixel_difference_rejected(self):
  old=c.read(ROOT/'design/historical_native/binding_00.json');noise=c.read(ROOT/'design/historical_native/binding_01.json');old['native_vae_calls'][0]['prepared_frames']['sha256']='bad'
  self.assertFalse(v.source_inputs_match(old,noise,ROOT)['prepared_RGB_match_R96_source'])
 def test_graph_difference_exactly_mode_and_admin(self):
  case=c.definitions()[0];a=c.read(ROOT/case['parent_graph']);b=c.expected_graph(ROOT,case)
  changed={(node,key) for node in a for key in a[node]['inputs'] if a[node]['inputs'][key]!=b[node]['inputs'][key]}
  expected={('5','audit_dir'),('5','run_id'),('6','audit_dir'),('6','run_id'),('6','pair_id'),('14','filename_prefix'),('50','audit_dir'),('50','run_id'),('50','mode'),('51','source_audit_dir'),('51','source_run_id'),('51','run_id'),('52','output_dir'),('52','run_id')}
  self.assertEqual(changed,expected)
 def test_cpu_preflight(self):self.assertTrue(preflight.check()['passed'])
 def test_predecessor_is_r117_on_same_gpu(self):
  p=c.read(ROOT/'configs/predecessor.json');self.assertEqual(p['required'],[]);self.assertEqual(c.read(ROOT/'configs/runtime.json')['expected_gpu_index'],2)
 def test_root_gpu_review_gate_precedes_launch(self):
  s=(ROOT/'audit/root_run_control.py').read_text();self.assertLess(s.index("review=read(ROOT/'audit/GPU_DEPLOYMENT_REVIEW.json')"),s.index("run(['python3','-u','scripts/launch_remote.py'"))
 def test_current_run_route_and_temporal_counts(self):
  s=(ROOT/'analysis/postrun/verify_pair.py').read_text();self.assertIn("'routed_calls':450",s);self.assertIn("'completed_forward_calls':20",s)
 def test_single_output_gate_owner_and_completion_compatible(self):
  s=(ROOT/'analysis/postrun/verify_pair.py').read_text();self.assertIn("'service_owner':owner",s);self.assertIn('r118-historical-native-guidance-runtime-gate-v1',s)

if __name__=='__main__':unittest.main()
