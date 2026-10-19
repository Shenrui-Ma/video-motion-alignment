import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
import r105_contract as c,verify_pair as v,predecessor

class RepairContract(unittest.TestCase):
 def test_fixed_two_original_tasks(self):
  jobs,order=c.registry();self.assertEqual(len(order),6)
  self.assertEqual(c.SOURCES,('human2animal_2__movie_man_11', 'crouch__movie_man_4', 'human2animal_3__game_man_4'))
  for name in order:c.validate_job(name)
 def test_same_pair_only_route_mode_is_scientific_difference(self):
  jobs,order=c.registry()
  for a,b in zip(order[::2],order[1::2]):
   ga=c.read(ROOT/'configs/graphs'/(a+'.json'));gb=c.read(ROOT/'configs/graphs'/(b+'.json'))
   def clean(g):
    g=copy.deepcopy(g)
    for n in ('6','50','51','52'):g[n]['inputs'].pop('run_id')
    g['14']['inputs'].pop('filename_prefix');g['50']['inputs'].pop('mode');return g
   self.assertEqual(clean(ga),clean(gb))
 def test_prompt_exact_approved_proposal(self):
  e=c.read(ROOT/'design/EVIDENCE.json')
  for item,pair in zip(e['items'],c.definitions()):
   self.assertEqual(item['candidate_prompt']['sha256'],pair['prompt_sha256'])
   prompt=pair['prompt'];self.assertIn('[reference generation]',prompt);self.assertIn('[Shot 1]',prompt)
   for field in ('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music'):self.assertIn(field+':',prompt)
 def test_numerical_source_bytes(self):
  for path,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():
   self.assertEqual(c.sha(ROOT/path),row['parent_sha256']);self.assertTrue(row['byte_equal'])
 def test_reference_shapes_and_exact_packed_segments(self):
  for pair in c.definitions():
   case=next(x for x in c.read(ROOT/'configs/scientific_contract.json')['cases'] if x['pair_key']==pair['pair_key'])
   image=case['reference_image_expected'];w,h=image['expected_native_ref_image_size_match_width_height'];shape=image['expected_clean_reference_latent_shape'];n=image['expected_DiT_visual_patch_tokens'];shapes=[list(c.SHAPES[k]) for k in ('video','audio')]
   offset=0;segments=[]
   for size,label in zip([80,n,40608,526,40608],['text','ref_img','ref_img','audio','video']):segments.append([offset,offset+size,label]);offset+=size
   condition={'native_vae_calls':[{'prepared_frames':{'shape':[1,h,w,3]},'latent':{'shape':shape}},{'prepared_frames':{'shape':[158,768,1152,3]},'latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'segments':segments,'seq_len':offset},'pair_snapshot':{'actual':{'references':[{'kind':'image','clean_latent':{'shape':shape}},{'kind':'video','clean_latent':{'shape':shapes[0]}}],'target_latent_shapes':shapes,'packed_layout':{'segments':segments,'seq_len':offset}}}}
   plan={'reference_image_segments':[segments[1][:2]],'reference_video_segment':segments[2][:2],'target_video_segment':segments[4][:2]}
   self.assertTrue(v.reference_geometry_matches(condition,case,plan))
   bad=copy.deepcopy(plan);bad['reference_image_segments']=[];self.assertFalse(v.reference_geometry_matches(condition,case,bad))
   bad=copy.deepcopy(condition);bad['native_vae_calls'][0]['prepared_frames']['shape'][1]+=32;self.assertFalse(v.reference_geometry_matches(bad,case,plan))
   bad=copy.deepcopy(condition);bad['packed_layout']['segments'][2][0]+=1;self.assertFalse(v.reference_geometry_matches(bad,case,plan))

if __name__=='__main__':unittest.main()
