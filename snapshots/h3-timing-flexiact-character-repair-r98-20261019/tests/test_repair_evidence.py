import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
from r98_contract import read,registry,RUN_ID
from verify_native import current_reference_checks
class RepairEvidence(unittest.TestCase):
 def setUp(self):
  self.c=read(ROOT/'design/R66_ACTUAL/r66_human2animal_1__game_man_4_seed2026101701_native_conditioning.json');self.case=registry()[0][RUN_ID]['case'];self.expected={'input_video':self.c['input_video'],'source_sha256':self.case['video_sha256']}
 def test_current_evidence_consistent(self):self.assertTrue(all(current_reference_checks(self.c,self.expected,self.case,self.c).values()))
 def test_host_pixel_expectation_strict(self):
  e=copy.deepcopy(self.expected);e['input_video']['sha256']='other';self.assertFalse(current_reference_checks(self.c,e,self.case,self.c)['actual_host9_input_pixels'])
 def test_different_host_latents_allowed_if_current_snapshot_consistent(self):
  c=copy.deepcopy(self.c);c['native_vae_calls'][0]['latent']['sha256']='new';c['pair_snapshot']['actual']['references'][0]['clean_latent']['sha256']='new'
  self.assertTrue(all(current_reference_checks(c,self.expected,self.case,self.c).values()))
 def test_inconsistent_clean_latent_rejected(self):
  c=copy.deepcopy(self.c);c['native_vae_calls'][0]['latent']['sha256']='wrong';self.assertFalse(current_reference_checks(c,self.expected,self.case,self.c)['current_clean_reference_snapshot_consistency'])
 def test_wrong_reference_identity_or_semantic_fps_rejected(self):
  c=copy.deepcopy(self.c);c['pair_snapshot']['actual']['references'][0]['kind']='video';self.assertFalse(current_reference_checks(c,self.expected,self.case,self.c)['current_clean_reference_snapshot_consistency'])
  c=copy.deepcopy(self.c);c['qwen_presentation'][1]['sampling']['semantic_fps']=4;self.assertFalse(current_reference_checks(c,self.expected,self.case,self.c)['Qwen_physical_sampling_unchanged'])
 def test_prompt_six_sections_and_reference_roles(self):
  p=self.case['prompt'];head=['subject_definitions:','summary:','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:'];self.assertEqual(sorted(head,key=p.index),head)
  self.assertIn('[reference generation]',p);self.assertIn('[Shot 1]',p);self.assertIn('dark trousers with pale crossing harness straps',p);self.assertIn('plain white backdrop',p);self.assertNotIn('white trousers',p)
  self.assertEqual(self.case['reference_image_expected']['expected_native_ref_image_size_match_width_height'],[960,608]);self.assertEqual(self.case['valid_frame_count'],147)
if __name__=='__main__':unittest.main()
