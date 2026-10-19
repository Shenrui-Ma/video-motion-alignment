import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'analysis/postrun'))
import verify_native as verify,capture_checks as cap
import torch

class PairVerifierTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source='short_0230';self.runs=[f'r80_{self.source}_seed2026101701_{a}' for a in ('native',)];self.jobs={};self.shapes={'video':(1,2),'audio':(1,3)}
  r=self.root
  for p in ('configs/graphs','processes','logs','output','audit/router','audit/tensor_blobs'): (r/p).mkdir(parents=True,exist_ok=True)
  self.put(r/'configs/runtime.json',{'gpu_uuid':'GPU-test','port':8529})
  self.put(r/'deploy_manifest.json',{'files':{'configs/runtime.json':{'sha256':verify.sha(r/'configs/runtime.json')}}})
  owner={'pid':101,'identity':{'uid':1000,'start_ticks':'123'},'gpu_uuid':'GPU-test','port':8529};self.put(r/'processes/service.json',owner)
  base=verify.read(ROOT/'tests/fixtures/R54_captures.json');self.grid=base['sigmas_video']
  blobs=[]
  for i in range(6):
   value=torch.full((2,),float(i));file=f'tensor_blobs/blob{i}.pt';torch.save(value,r/'audit'/file);sig=cap.signature(value);blobs.append({**{k:sig[k] for k in ('shape','dtype','sha256')},'tensor_file':file})
  # Each prompt has its own conditioning audit manifest.
  sig={'seed':2026101701,'nested':True};noise=[torch.zeros((2,)),torch.ones((3,))];hashes=[{k:cap.signature(x)[k] for k in ('shape','dtype','sha256')} for x in noise];pair_id=f'r80_{self.source}_seed2026101701';torch.save({'signature':sig,'hashes':hashes,'tensors':noise},r/'audit'/f'{pair_id}_noise.pt')
  self.put(r/'configs/expected_input_pixels.json',{self.source:{'input_video':{'sha256':'rgb'}}})
  for arm,run in zip(('native',),self.runs):
   shared=r/'audit'/f'r80_{self.source}_{arm}_shared_conditioning.json';self.put(shared,{'blobs':blobs})
   full=False;graph={'9':{'inputs':{'sigmas':','.join(map(str,self.grid))}}};self.put(r/'configs/graphs'/f'{run}.json',graph)
   row={'arm':arm,'source_id':self.source,'seed':2026101701,'graph_sha256':verify.sha(r/'configs/graphs'/f'{run}.json'),'case':{'prompt':arm.upper(),'reference_cache_id':f'r80_{self.source}_{arm}_shared','valid_frame_count':86,'evaluation_crop_xywh':[16,8,1280,720]}};self.jobs[run]=row
   video=r/'output'/f'{run}.mp4';video.write_bytes(b'fixture-video')
   self.put(r/'logs'/f'{run}_history.json',{'status':{'completed':True,'status_str':'success'},'prompt':[0,'prompt-'+run,graph],'outputs':{'14':{'images':[{'type':'output','filename':video.name}]}}})
   self.put(r/'logs'/f'{run}_job.json',{'service_pid':101,'service_identity':owner['identity'],'status':'success','name':run,'prompt_id':'prompt-'+run,'graph_sha256':row['graph_sha256'],'submitted_unix':1.,'observed_unix':2.})
   c={'run_id':run,'prompt':arm.upper(),'input_video':{'sha256':'rgb'},'native_vae_calls':[{'prepared_frames':{'shape':[90,736,1312,3]},'latent':{'shape':[1,24,27,46,82]}}],'qwen_presentation':[{'actual_sampled_frames':'rgb-subset','sampling':[0,12,24]}],'target_latent_shapes':[[1,2],[1,3]],'conditioning_embedding':{'sha256':'joint-'+arm},'token_tags':[arm],'packed_layout':{'seq_len':20},'blobs':blobs,'pair_snapshot':{'verified':True,'source_run_id':f'r80_{self.source}_{arm}_shared','source_manifest_sha256':verify.sha(shared)}};self.put(r/'audit'/f'{run}_conditioning.json',c)
   self.put(r/'audit'/f'{run}_noise.json',{'run_id':run,'pair_id':pair_id,'signature':sig,'actual_noise_streams':hashes})
   router={'run_id':run,'mode':'mass_preserve' if full else 'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[0,20],'pixel_interval_inclusive':[0,89],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450 if full else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':cap.expected_routing(full),'routed_by_block':[9 if full else 0]*50,'sample_sigmas':self.grid,'expected_sampling_steps':20,'validated_layout':{'frame_rows':943,'latent_interval_half_open':[0,27],'query_interval_half_open':[1,10],'target_video_segment':[1,10],'key_interval_half_open':[10,19],'reference_video_segment':[10,19]},'first_attention':{'qkv_shape':[1,56,20,128]},'forward_summaries':[{'sampled_finite':True}]*20};self.put(r/'audit/router'/f'{run}.json',router)
   folder=r/'audit/x0'/run;folder.mkdir(parents=True);m=copy.deepcopy(base);m['run_id']=run;m['target_latent_shapes']=[list(self.shapes[k]) for k in ('video','audio')]
   for record in m['captures']+[m['final_sampler_result']]:
    record['run_id']=run;values={k:torch.full(shape,float(record['step_zero_based'])+(1 if arm=='p1' else 0)) for k,shape in self.shapes.items()}
    for k,v in values.items():record[k]=cap.signature(v)
    metadata={k:v for k,v in record.items() if k not in ('file','capture_seconds')};torch.save({**values,'metadata':metadata},folder/record['file'])
   self.put(folder/'manifest.json',m)
  self.patches=[patch.object(verify,'registry',return_value=(self.jobs,self.runs)),patch.object(verify,'validate_job',side_effect=lambda run,root:self.jobs[run]),patch.object(verify,'video_properties',return_value={'width':1312,'height':736,'nb_read_frames':'90','avg_frame_rate':'24/1'}),patch.object(cap,'SHAPES',self.shapes)]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 @staticmethod
 def put(path,value):path.write_text(json.dumps(value))
 def test_actual_native_integrity_passes(self):
  result=verify.verify(self.root,self.source);self.assertTrue(result['passed']);self.assertEqual(result['runs']['native']['valid_frames'],86);self.assertEqual(result['runs']['native']['routed_blocks'],0)
 def test_wrong_input_pixels_fail(self):
  p=self.root/'audit'/f'{self.runs[0]}_conditioning.json';v=verify.read(p);v['input_video']['sha256']='changed';self.put(p,v)
  result=verify.verify(self.root,self.source);self.assertFalse(result['passed']);self.assertFalse(result['checks']['actual_original_input_pixels'])
 def test_router_activation_rejected(self):
  p=self.root/'audit/router'/f'{self.runs[0]}.json';v=verify.read(p);v['routed_calls']=1;self.put(p,v)
  result=verify.verify(self.root,self.source);self.assertFalse(result['passed']);self.assertFalse(result['checks']['native_actual_execution_counts'])
 def test_condition_blob_corruption_rejected(self):
  torch.save(torch.ones(2)*100,self.root/'audit/tensor_blobs/blob0.pt')
  with self.assertRaisesRegex(ValueError,'actual condition tensor'):verify.verify(self.root,self.source)
 def test_noise_corruption_rejected(self):
  p=self.root/'audit'/f'r80_{self.source}_seed2026101701_noise.pt';v=torch.load(p,weights_only=True);v['tensors'][0]+=1;torch.save(v,p)
  result=verify.verify(self.root,self.source);self.assertFalse(result['passed']);self.assertFalse(result['checks']['native_actual_noise_cache'])
 def test_missing_prediction_rejected(self):
  (self.root/'audit/x0'/self.runs[0]/'x0_step009.pt').unlink()
  with self.assertRaisesRegex(ValueError,'actual endpoint inventory'):verify.verify(self.root,self.source)
if __name__=='__main__':unittest.main()
