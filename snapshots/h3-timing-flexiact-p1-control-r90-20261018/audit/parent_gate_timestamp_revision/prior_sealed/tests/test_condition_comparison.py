import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'analysis/postrun'))
from verify_native import compare_parent_conditions,read
class ParentConditionComparison(unittest.TestCase):
 def setUp(self):self.old=read(ROOT/'design/R85_ACTUAL/r85_one_leg__movie_man_9_seed2026101701_native_conditioning.json')
 def test_identical_visual_inputs_pass(self):self.assertTrue(all(compare_parent_conditions(self.old,self.old).values()))
 def test_text_embedding_text_positions_and_prompt_may_change(self):
  d=copy.deepcopy(self.old);d['prompt']='P1';d['conditioning_embedding']={'different':'embedding'};d['token_tags']={'different':'text tags'};d['packed_layout']={'different':'positions'};d['pair_snapshot']['actual']['conditioning_embedding']={'different':'joint text'}
  self.assertTrue(all(compare_parent_conditions(d,self.old).values()))
 def test_actual_input_pixels_change_rejected(self):
  d=copy.deepcopy(self.old);d['input_video']['sha256']='changed';self.assertFalse(compare_parent_conditions(d,self.old)['original_input_pixels'])
 def test_image_or_video_latent_change_rejected(self):
  for index in (0,1):
   d=copy.deepcopy(self.old);d['native_vae_calls'][index]['latent']['sha256']='changed';self.assertFalse(compare_parent_conditions(d,self.old)['actual_prepared_RGB_and_clean_VAE'])
 def test_vae_prepared_rgb_change_rejected(self):
  d=copy.deepcopy(self.old);d['native_vae_calls'][1]['prepared_frames']['sha256']='changed';self.assertFalse(compare_parent_conditions(d,self.old)['actual_prepared_RGB_and_clean_VAE'])
 def test_reference_order_or_kind_change_rejected(self):
  d=copy.deepcopy(self.old);d['pair_snapshot']['actual']['references'].reverse();self.assertFalse(compare_parent_conditions(d,self.old)['actual_reference_snapshot'])
 def test_qwen_visual_sampling_change_rejected(self):
  d=copy.deepcopy(self.old);d['qwen_presentation'][1]['sampling']['semantic_fps']=4;self.assertFalse(compare_parent_conditions(d,self.old)['Qwen_visual_sampling'])
 def test_latent_target_shape_change_rejected(self):
  d=copy.deepcopy(self.old);d['pair_snapshot']['actual']['target_latent_shapes'][0][2]=48;self.assertFalse(compare_parent_conditions(d,self.old)['target_shapes_and_dtype'])
if __name__=='__main__':unittest.main()
