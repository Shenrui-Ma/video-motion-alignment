import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'analysis/postrun')]
import r103_contract as c,verify_pair as v,predecessor

class RepairContract(unittest.TestCase):
 def test_fixed_two_original_tasks(self):
  jobs,order=c.registry();self.assertEqual(len(order),4)
  self.assertEqual(c.SOURCES,('human2animal_2__game_man_4','chest__game_girl_1'))
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

class PredecessorRelease(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name);self.old=self.r/'old';self.owner={'pid':99,'identity':{'uid':1004,'start_ticks':'11'},'port':8560}
  self.put(self.old/'deploy_manifest.json',{'files':{}});self.put(self.old/'processes/service.json',self.owner)
  self.complete={'passed':True,'all_sources_reviewed':True,'GPU_released':True,'remaining_sources':[],'terminal_sources':[{'source_id':'a'}]}
  self.exit={'passed':True,'owner':self.owner,'process_absent':True,'CUDA_allocation_absent':True}
  self.put(self.old/'audit/attempt/COMPLETE.json',self.complete);self.put(self.old/'audit/attempt/ROOT_EXIT_RECEIPT.json',self.exit)
  self.put(self.r/'configs/predecessor.json',{'remote_root':str(self.old),'owner':self.owner,'producer_seal_sha256':c.sha(self.old/'deploy_manifest.json'),'attempt':'attempt','required_terminal_sources':['a']})
 def put(self,p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
 def check(self,identity=None,compute=None):return predecessor.check(self.r,current_identity=lambda p:identity,compute_processes=lambda:compute or [])
 def test_complete_absent_passes(self):self.assertTrue(self.check()['passed'])
 def test_incomplete_review_rejected(self):
  self.complete['all_sources_reviewed']=False;self.put(self.old/'audit/attempt/COMPLETE.json',self.complete)
  with self.assertRaises(ValueError):self.check()
 def test_live_old_pid_rejected(self):
  with self.assertRaises(ValueError):self.check(self.owner['identity'])
 def test_old_cuda_allocation_rejected(self):
  with self.assertRaises(ValueError):self.check(compute=[{'pid':99}])
 def test_foreign_cuda_is_not_predecessor(self):self.assertTrue(self.check(compute=[{'pid':1234}])['passed'])
 def test_changed_generation_rejected(self):
  changed=copy.deepcopy(self.owner);changed['identity']['start_ticks']='12';self.put(self.old/'processes/service.json',changed)
  with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main()
