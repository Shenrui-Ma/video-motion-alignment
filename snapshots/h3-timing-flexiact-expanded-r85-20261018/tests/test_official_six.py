import copy,csv,importlib.util,json,math,shutil,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
import r85_contract as c,verify_pair,execution_gate,check_storage
class SixPairsTests(unittest.TestCase):
 def test_official_candidates_exact_and_complete(self):
  fixed=c.read(ROOT/'design/SELECTED_PAIRS.json');want=[x['source']+'__'+Path(x['target']).stem for x in fixed['pairs'] ]
  self.assertEqual(list(c.PAIR_KEYS),want);self.assertEqual(len(c.definitions()),3);self.assertEqual(len({p['motion_source_id'] for p in c.definitions()}),3)
  for p in c.definitions():
   file=ROOT/'design/official_metadata'/f"flexiact_hf__benchmark__captions__human__{p['motion_source_id']}__val_image.csv"
   with file.open() as handle:row=list(csv.DictReader(handle))[p['official_csv_row_zero_based']]
   self.assertEqual(row['path'],p['identity']);self.assertEqual(row['caption'],p['official_target_caption'])
 def test_p1_all_roles_and_source_first_caption_review(self):
  for p in c.definitions():
   if p['prompt_version']=='P0':continue
   value=c.prompt_values(ROOT,p['pair_key']);self.assertIn('[reference generation]',value)
   self.assertIn('No specific music is requested.',value);self.assertIn(p['p1_fields']['source_caption'],value)
  p=next(p for p in c.definitions() if p['pair_key']=='crouch__movie_man_5')
  self.assertIn('resistance machine',p['official_target_caption']);self.assertNotIn('resistance',p['prompt']);self.assertIn('squat',p['prompt'])
 def test_pair_specific_shared_caches(self):
  jobs,order=c.registry();condition=[];noise=[]
  for a,b in zip(order[::2],order[1::2]):
   x=c.read(ROOT/'configs/graphs'/f'{a}.json');y=c.read(ROOT/'configs/graphs'/f'{b}.json')
   self.assertEqual(x['5']['inputs'],y['5']['inputs']);self.assertEqual(x['6']['inputs']['pair_id'],y['6']['inputs']['pair_id']);condition.append(x['5']['inputs']['run_id']);noise.append(x['6']['inputs']['pair_id'])
  self.assertEqual(len(set(condition)),3);self.assertEqual(len(set(noise)),3)
 def test_target_shapes_use_native_area_round32_formula(self):
  for p in c.definitions():
   im=Image.open(ROOT/'inputs'/p['portrait']);w,h=im.size;im.close();z=p['reference_image_expected'];scale=min(1.,math.sqrt(1152*768/(w*h)));tw=max(32,round(w*scale/32)*32);th=max(32,round(h*scale/32)*32)
   self.assertEqual([w,h],z['original_width_height']);self.assertEqual([tw,th],z['expected_native_ref_image_size_match_width_height']);self.assertEqual([1,24,1,th//16,tw//16],z['expected_clean_reference_latent_shape']);self.assertEqual(th//32*(tw//32),z['expected_DiT_visual_patch_tokens'])
 def test_all158_pixel_mapping_records(self):
  for source in ['one_leg','crouch','rotate']:
   p=c.read(ROOT/'inputs'/f'source_{source}_provenance.json');self.assertTrue(p['all158_decoded_frames_match_declared_source_exactly']);self.assertEqual(p['input_to_original'],[min(i//3,48) for i in range(158)]);self.assertEqual(p['input_frame_md5'],[p['source_scaled_frame_md5'][i] for i in p['input_to_original']]);self.assertEqual(p['evaluate_indices'],list(range(0,147,3)))
 def test_wrong_pair_image_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);shutil.copytree(ROOT/'configs',r/'configs');shutil.copytree(ROOT/'design',r/'design');p=r/'configs/scientific_contract.json';s=c.read(p);s['cases'][0]['portrait']='target_movie_man_5.jpg';p.write_text(json.dumps(s))
   with self.assertRaisesRegex(ValueError,'frozen pair input'):c.registry(r)
 def test_p1_word_change_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);shutil.copytree(ROOT/'configs',r/'configs');shutil.copytree(ROOT/'design',r/'design');p=r/'configs/prompts/crouch__movie_man_5.txt';p.write_text(p.read_text().replace('timing','speed'))
   with self.assertRaisesRegex(ValueError,'frozen P1 prompt'):c.registry(r)
 def test_six_kernels_exact(self):
  d=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertEqual(len(d),6)
  for p,row in d.items():self.assertTrue(row['byte_equal']);self.assertEqual(c.sha(ROOT/p),row['parent_sha256'])
 def test_gpu7_fresh_admission(self):
  runtime=c.read(ROOT/'configs/runtime.json');self.assertEqual((runtime['expected_gpu_index'],runtime['gpu_uuid'],runtime['port']),(3,'GPU-REDACTED',8550));self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch']);self.assertFalse((ROOT/'processes/service.json').exists())
 def test_seal_binds_p1_definition_and_postrun(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   for folder in ['scripts','extensions','configs','design','tests','analysis/postrun']:shutil.copytree(ROOT/folder,r/folder)
   (r/'audit').mkdir();shutil.copy2(ROOT/'audit/root_run_batch.py',r/'audit/root_run_batch.py')
   files=execution_gate.seal(r)['files']
   for p in ['design/PAIR_DEFINITIONS.json','configs/prompts/crouch__movie_man_5.txt','analysis/postrun/verify_pair.py','configs/prompt_ancestry.json','configs/storage_policy.json']:self.assertIn(p,files)
   self.assertNotIn('configs/admission.json',files)
 def test_disk_failure_before_launch(self):
  with self.assertRaisesRegex(ValueError,'filesystem'):check_storage.check(ROOT,usage=lambda p:SimpleNamespace(free=1,total=1))

class ReferenceGeometryTests(unittest.TestCase):
 def fixture(self,pair):
  p=next(p for p in c.definitions() if p['pair_key']==pair);im=p['reference_image_expected'];w,h=im['expected_native_ref_image_size_match_width_height'];shape=im['expected_clean_reference_latent_shape'];offset=0;segments=[]
  for size,label in zip([80,im['expected_DiT_visual_patch_tokens'],40608,526,40608],['text','ref_img','ref_img','audio','video']):segments.append([offset,offset+size,label]);offset+=size
  shapes=[list(c.SHAPES[k]) for k in ('video','audio')]
  cond={'native_vae_calls':[{'prepared_frames':{'shape':[1,h,w,3]},'latent':{'shape':shape}},{'prepared_frames':{'shape':[158,768,1152,3]},'latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'seq_len':offset,'segments':segments},'pair_snapshot':{'actual':{'references':[{'kind':'image','clean_latent':{'shape':shape}},{'kind':'video','clean_latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'seq_len':offset,'segments':segments}}}}
  plan={'reference_image_segments':[segments[1][:2]],'reference_video_segment':segments[2][:2],'target_video_segment':segments[4][:2]};return cond,{'reference_image_expected':im},plan
 def test_all_six_actual_vae_geometry_contracts(self):
  for pair in c.PAIR_KEYS:
   with self.subTest(pair=pair):self.assertTrue(verify_pair.reference_geometry_matches(*self.fixture(pair)))
 def test_different_image_shape_fails(self):
  cond,case,plan=self.fixture(c.PAIR_KEYS[0]);cond['native_vae_calls'][0]['latent']['shape']=[1,24,1,42,62];self.assertFalse(verify_pair.reference_geometry_matches(cond,case,plan))
 def test_different_token_layout_fails(self):
  cond,case,plan=self.fixture(c.PAIR_KEYS[-1]);plan['reference_image_segments'][0][1]+=1;self.assertFalse(verify_pair.reference_geometry_matches(cond,case,plan))
 def test_all_six_router_layouts(self):
  spec=importlib.util.spec_from_file_location('layout74',ROOT/'extensions/H3TemporalRouter/layout.py');layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
  for pair in c.PAIR_KEYS:
   cond,case,plan=self.fixture(pair);shape=case['reference_image_expected']['expected_clean_reference_latent_shape'];refs=[{'kind':'image','index':0,'latent_t':1,'latent_h':shape[-2],'latent_w':shape[-1],'frame_rows':shape[-2]*shape[-1]//4,'ref_audio_t':0},{'kind':'video','index':1,'latent_t':47,'latent_h':48,'latent_w':72,'frame_rows':864,'ref_audio_t':0}]
   got=layout.validate_layout({'text_len':80,'context_shape':[1,80,5120],'refs':refs},SimpleNamespace(signature=(80,47,48,72,263),seq_len=cond['packed_layout']['seq_len'],segments=cond['packed_layout']['segments']),0,146)
   for k,v in plan.items():self.assertEqual(got[k],v)
   self.assertEqual(got['latent_interval_half_open'],[0,44])
if __name__=='__main__':unittest.main(verbosity=2)
