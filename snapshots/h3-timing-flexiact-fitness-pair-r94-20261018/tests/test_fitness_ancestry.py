import json,sys,unittest,copy,tempfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r94_contract as c

class FitnessAncestry(unittest.TestCase):
 def test_exact_actual_p1_and_two_fresh_graphs(self):
  jobs,order=c.registry();self.assertEqual(order,['r94_fitness__game_man_5_seed2026101701_native','r94_fitness__game_man_5_seed2026101701_forced'])
  h=c.read(ROOT/'design/ancestry/r72_fitness_p1_actual_history.json');self.assertTrue(h['status']['completed']);self.assertEqual(h['status']['status_str'],'success')
  old=c.read(ROOT/'configs/parent_graphs/r72_fitness__game_man_5_seed2026101701_p1.json');self.assertEqual(h['prompt'][2],old)
  for run in order:
   case=jobs[run]['case'];graph=c.read(ROOT/'configs/graphs'/(run+'.json'));self.assertEqual(case['prompt_version'],'P1');self.assertEqual(case['prompt_sha256'],'483333ae6c3ac5d5afa7956579c241b524c3e8d12268f386f8262cffd927a150');self.assertEqual(graph['5']['inputs']['prompt'],old['5']['inputs']['prompt']);self.assertEqual(graph['6']['inputs']['noise_seed'],2026101701);self.assertEqual(graph['6']['inputs']['pair_id'],'r94_fitness__game_man_5_seed2026101701')
  self.assertTrue(c.read(ROOT/'configs/queue.json')['finalize'])
 def test_input_bytes_and_reference_image_geometry(self):
  case=c.registry()[0][c.registry()[1][0]]['case']
  for key in ['video','portrait','provenance']:self.assertEqual(c.sha(ROOT/'inputs'/case[key]),case[key+'_sha256'])
  self.assertEqual(case['video_sha256'],'168eca8e9b2ebcfcb4b61ece44730a99889726ee0106078bbd063330eb72a686');self.assertEqual(case['portrait_sha256'],'fb2f5f3f0bfb2d1023b47711be93e424f4d954933c901268e12e8a110d47c0e2')
  image=case['reference_image_expected'];self.assertEqual(image['expected_clean_reference_latent_shape'],[1,24,1,44,78]);self.assertEqual(image['expected_DiT_visual_patch_tokens'],858)
 def test_actual_repeat3_and_padding_provenance(self):
  p=c.read(ROOT/'inputs/source_fitness_provenance.json');self.assertEqual(p['input_to_original'][:147],[i//3 for i in range(147)]);self.assertEqual(p['input_to_original'][147:],[48]*11);self.assertTrue(p['all158_decoded_frames_match_declared_source_exactly']);self.assertEqual(p['evaluate_indices'],list(range(0,147,3)))
 def test_six_numerical_sources_unchanged(self):
  d=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertEqual(len(d),6)
  for name,row in d.items():self.assertEqual(c.sha(ROOT/name),row['parent_sha256']);self.assertTrue(row['byte_equal'])
 def test_changed_prompt_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)
   for f in ['configs','design']:shutil.copytree(ROOT/f,r/f)
   p=r/'configs/prompts/fitness__game_man_5.txt';p.write_text(p.read_text()+'altered')
   with self.assertRaisesRegex(ValueError,'frozen P1'):c.registry(r)
 def test_changed_sampler_or_ref_image_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t)
   for f in ['configs','design']:shutil.copytree(ROOT/f,r/f)
   p=r/'configs/graphs/r94_fitness__game_man_5_seed2026101701_native.json';v=c.read(p);v['8']['inputs']['sampler_name']='heun';p.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'graph numerical'):c.registry(r)
 def test_planned_release_after_one_pair(self):
  r=(ROOT/'audit/root_run_batch.py').read_text();self.assertIn('service.wait_cuda_release(owner)',r);self.assertLess(r.index("audit/'ROOT_EXIT_RECEIPT.json'"),r.index("audit/'pair_verify.log'"));self.assertNotIn('FIRST_PAIR_REVIEW_HOLD',r);self.assertIn("signal.signal(signal.SIGTERM,interrupted)",r)
 def test_correct_host_resources(self):
  d=c.read(ROOT/'configs/runtime.json');self.assertEqual((d['port'],d['expected_gpu_index'],d['reserve_vram'],d['memory_mode']),(8559,3,8,'normal'));self.assertEqual(d['gpu_uuid'],'GPU-REDACTED');self.assertEqual(c.read(ROOT/'configs/predecessor.json')['service_pid'],16003)

if __name__=='__main__':unittest.main()
