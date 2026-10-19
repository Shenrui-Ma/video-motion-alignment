import copy,importlib.util,json,math,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
import r66_contract as contract,verify_pair,service,resource_gate,execution_gate

class ExpandedPairsTests(unittest.TestCase):
 def test_pair_keys_prevent_cache_collision(self):
  jobs,order=contract.registry(ROOT);conditioning={};noise={}
  for run in order:
   c=jobs[run]['case'];g=contract.read(ROOT/'configs/graphs'/f'{run}.json');k=c['pair_key']
   conditioning.setdefault(k,set()).add(g['5']['inputs']['run_id']);noise.setdefault(k,set()).add(g['6']['inputs']['pair_id'])
   self.assertEqual(g['5']['inputs']['run_id'],g['51']['inputs']['source_run_id']);self.assertNotIn('/',run)
  self.assertEqual(len(conditioning),8);self.assertTrue(all(len(v)==1 for v in conditioning.values()));self.assertTrue(all(len(v)==1 for v in noise.values()))
  self.assertEqual(len(set.union(*conditioning.values())),8);self.assertEqual(len(set.union(*noise.values())),8)
 def test_group_denominators(self):
  pairs=contract.frozen_pairs(ROOT)
  self.assertEqual(sum(x['group']=='official_assets_crosspair_extension' for x in pairs),6)
  self.assertEqual(sum(x['group']=='official_csv_identity_generalization' for x in pairs),2)
  self.assertEqual(len({x['action'] for x in pairs}),5)
  self.assertEqual(len({x['action'] for x in pairs if x['source_is_new_motion_content']}),3)
 def test_target_original_size_to_match_formula(self):
  from PIL import Image
  data=contract.read(ROOT/'configs/source_selection/EXPECTED_SHAPES.json')['reference_images']
  for name,row in data.items():
   with Image.open(ROOT/'inputs'/name) as im:w,h=im.size
   scale=min(1.,math.sqrt(1152*768/(w*h)));tw=max(32,round(w*scale/32)*32);th=max(32,round(h*scale/32)*32)
   self.assertEqual([w,h],row['original_width_height']);self.assertEqual([tw,th],row['expected_native_ref_image_size_match_width_height'])
   self.assertEqual([1,24,1,th//16,tw//16],row['expected_clean_reference_latent_shape']);self.assertEqual(th//32*(tw//32),row['expected_DiT_visual_patch_tokens'])
 def test_changed_pair_target_metadata_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   r=Path(temp);shutil.copytree(ROOT/'configs',r/'configs');p=r/'configs/scientific_contract.json';s=contract.read(p);s['cases'][0]['portrait']='target_game_man_4.jpg';p.write_text(json.dumps(s))
   with self.assertRaisesRegex(ValueError,'frozen pair input'):contract.registry(r)
 def test_action_only_cache_graph_rejected(self):
  with tempfile.TemporaryDirectory() as temp:
   r=Path(temp);shutil.copytree(ROOT/'configs',r/'configs');name=contract.registry(r)[1][0];p=r/'configs/graphs'/f'{name}.json';g=contract.read(p);g['6']['inputs']['pair_id']='r66_human2animal_1_seed2026101701';p.write_text(json.dumps(g))
   with self.assertRaisesRegex(ValueError,'graph numerical'):contract.registry(r)
 def test_runtime_gpu2_and_no_launch_admission(self):
  r=contract.read(ROOT/'configs/runtime.json');self.assertEqual((r['gpu_uuid'],r['expected_gpu_index'],r['port']),('GPU-REDACTED',2,8536))
  self.assertEqual((r['memory_mode'],r['reserve_vram']),('normal',8));self.assertFalse(contract.read(ROOT/'configs/admission.json')['ready_for_launch'])
  self.assertFalse((ROOT/'processes/service.json').exists())
 def test_seal_includes_verifier_and_frozen_selection(self):
  with tempfile.TemporaryDirectory() as temp:
   r=Path(temp)
   for f in ['scripts','extensions','configs','analysis/postrun']:shutil.copytree(ROOT/f,r/f)
   s=execution_gate.seal(r)
   self.assertIn('analysis/postrun/verify_pair.py',s['files']);self.assertIn('configs/source_selection/PREPARED_8_PAIRS.json',s['files'])
   self.assertNotIn('configs/admission.json',s['files'])

class ReferenceGeometryTests(unittest.TestCase):
 def fixture(self,name):
  image=contract.read(ROOT/'configs/source_selection/EXPECTED_SHAPES.json')['reference_images'][name];w,h=image['expected_native_ref_image_size_match_width_height'];shape=image['expected_clean_reference_latent_shape'];count=image['expected_DiT_visual_patch_tokens'];offset=0;segments=[]
  for size,label in zip([80,count,40608,526,40608],['text','ref_img','ref_img','audio','video']):segments.append([offset,offset+size,label]);offset+=size
  shapes=[list(contract.SHAPES[k]) for k in ('video','audio')]
  c={'native_vae_calls':[{'prepared_frames':{'shape':[1,h,w,3]},'latent':{'shape':shape}},{'prepared_frames':{'shape':[158,768,1152,3]},'latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'seq_len':offset,'segments':segments},'pair_snapshot':{'actual':{'references':[{'kind':'image','clean_latent':{'shape':shape}},{'kind':'video','clean_latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'seq_len':offset,'segments':segments}}}}
  plan={'reference_image_segments':[segments[1][:2]],'reference_video_segment':segments[2][:2],'target_video_segment':segments[4][:2]}
  return c,{'reference_image_expected':image},plan
 def test_both_actual_image_geometries_pass(self):
  for name in ['target_movie_man_11.jpg','target_game_man_4.jpg']:
   with self.subTest(name=name):self.assertTrue(verify_pair.reference_geometry_matches(*self.fixture(name)))
 def test_image_size_from_other_target_fails(self):
  c,case,plan=self.fixture('target_movie_man_11.jpg');c['native_vae_calls'][0]['latent']['shape']=[1,24,1,38,60]
  self.assertFalse(verify_pair.reference_geometry_matches(c,case,plan))
 def test_wrong_image_token_segment_fails(self):
  c,case,plan=self.fixture('target_game_man_4.jpg');plan['reference_image_segments'][0][1]+=1
  self.assertFalse(verify_pair.reference_geometry_matches(c,case,plan))
 def test_wrong_video_reference_shape_fails(self):
  c,case,plan=self.fixture('target_movie_man_11.jpg');c['native_vae_calls'][1]['latent']['shape']=[1,24,27,46,82]
  self.assertFalse(verify_pair.reference_geometry_matches(c,case,plan))
 def test_layout_accepts_variable_reference_image_positions(self):
  spec=importlib.util.spec_from_file_location('r66layout',ROOT/'extensions/H3TemporalRouter/layout.py');layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
  for name in ['target_movie_man_11.jpg','target_game_man_4.jpg']:
   c,case,expected=self.fixture(name);shape=case['reference_image_expected']['expected_clean_reference_latent_shape'];refs=[{'kind':'image','index':0,'latent_t':1,'latent_h':shape[-2],'latent_w':shape[-1],'frame_rows':shape[-2]*shape[-1]//4,'ref_audio_t':0},{'kind':'video','index':1,'latent_t':47,'latent_h':48,'latent_w':72,'frame_rows':864,'ref_audio_t':0}]
   plan=layout.validate_layout({'text_len':80,'context_shape':[1,80,5120],'refs':refs},SimpleNamespace(signature=(80,47,48,72,263),seq_len=c['packed_layout']['seq_len'],segments=c['packed_layout']['segments']),0,146)
   for key,value in expected.items():self.assertEqual(plan[key],value)
   self.assertEqual(plan['latent_interval_half_open'],[0,44])

class PeerAdmissionTests(unittest.TestCase):
 def check(self,rows,own,allowed):
  identities={pid:{'uid':1004,'start_ticks':str(pid),'cmdline_sha256':str(pid)} for pid in own}
  admission={'permitted_compute_processes':[{'pid':pid,'identity':identities[pid]} for pid in allowed]}
  with patch.object(resource_gate,'admission_document',return_value=admission),patch.object(service.os,'getuid',return_value=1004),patch.object(service,'proc_uid',side_effect=lambda pid:1004 if pid in own else 9999),patch.object(service,'external_identity',side_effect=lambda pid:identities[pid]):
   return service.check_admission(admission,rows,{'queue_running':[],'queue_pending':[]})
 def test_registered_peer_and_foreign_on_three_other_cards_allowed(self):
  rows=[{'gpu_uuid':'GPU-peer1','pid':10}]+[{'gpu_uuid':f'GPU-foreign{i}','pid':100+i} for i in range(3)]+[{'gpu_uuid':service.GPU,'pid':200}]
  self.check(rows,{10},{10})
 def test_second_registered_peer_creating_third_own_card_rejected(self):
  with self.assertRaises(resource_gate.ResourceUnavailable):self.check([{'gpu_uuid':'GPU-peer1','pid':10},{'gpu_uuid':'GPU-peer2','pid':11}],{10,11},{10,11})
 def test_unregistered_own_peer_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'Unexpected own compute'):self.check([{'gpu_uuid':'GPU-peer1','pid':10}],{10},set())
 def test_peer_same_generation_required(self):
  admission={'permitted_compute_processes':[{'pid':10,'identity':{'uid':1004,'start_ticks':'old'}}]}
  with patch.object(resource_gate,'admission_document',return_value=admission),patch.object(service.os,'getuid',return_value=1004),patch.object(service,'proc_uid',return_value=1004),patch.object(service,'external_identity',return_value={'uid':1004,'start_ticks':'new'}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own compute'):service.check_admission(admission,[{'gpu_uuid':'GPU-peer1','pid':10}],{'queue_running':[],'queue_pending':[]})

if __name__=='__main__':unittest.main(verbosity=2)
