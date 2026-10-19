"""Small CPU archive corruption tests; no video/model inference."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import verify_completed as v
from H3X0Readout.core import CAPTURE_STEPS

class NativeCaptureTests(unittest.TestCase):
 def setUp(self):
  torch.set_num_threads(1);self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.run='r30_s05_forward_full_reverse_block_6to14';self.grid=torch.linspace(1,0,21).tolist();self.shapes={'video':(1,24,2,2,2),'audio':(1,32,2,8)};self.patcher=patch.object(v,'SHAPES',self.shapes);self.patcher.start()
  self.man={'schema':'h3-x0-readout-v1','status':'complete','callback_count':20,'expected_callback_count':20,'run_id':self.run,'capture_steps_zero_based':list(range(20)),'sigmas_video':self.grid,'seed':2026101311,'sampler':'sample_euler','audio_scale':4,'video_latent_scale_factor':1,'normalization_stage':'after_process_latent_out','geometry':{'width':1312,'height':736,'frames':141,'fps':24},'target_latent_shapes':[list(s) for s in self.shapes.values()],'captures':[]}
  for i in range(21):
   final=i==20;n=min(i,19);sv=0 if final else self.grid[n];tensors={k:torch.full(s,float(i)) for k,s in self.shapes.items()};meta={k:self.man[k] for k in ('seed','geometry','normalization_stage','audio_scale','video_latent_scale_factor')};meta.update(schema='h3-x0-readout-v1',run_id=self.run,total_steps=20,snapshot_kind='sampler_final' if final else 'x0_estimate',step_zero_based=n,model_call_one_based=n+1,sigma_video=sv,sigma_audio=sv/(4-3*sv),sigma_next_video=self.grid[n+1],**{k:v.signature(t) for k,t in tensors.items()})
   name='sampler_final.pt' if final else f'x0_step{n:03d}.pt';record={'file':name,**meta};torch.save(dict(tensors,metadata=meta),self.folder/name)
   if final:self.man['final_sampler_result']=record
   else:self.man['captures'].append(dict(record,capture_seconds=.01))
  self.save()
 def tearDown(self):self.patcher.stop();self.tmp.cleanup()
 def save(self):(self.folder/'manifest.json').write_text(json.dumps(self.man))
 def inspect(self):return v.inspect_capture(self.folder,self.run,self.grid,2026101311)
 def test_complete_all_step_inventory(self):
  self.assertEqual(CAPTURE_STEPS,tuple(range(20)));m,files,prefix=self.inspect();self.assertEqual(len(files),21);self.assertEqual(float(prefix['video'].flatten()[0]),5)
 def test_missing_step_rejected(self):
  (self.folder/'x0_step003.pt').unlink()
  with self.assertRaises(ValueError):self.inspect()
 def test_corrupt_seed_even_self_consistent_metadata_rejected(self):
  record=self.man['final_sampler_result'];record['seed']=2026101312;p=self.folder/record['file'];d=torch.load(p,weights_only=True);d['metadata']['seed']=2026101312;torch.save(d,p);self.save()
  with self.assertRaisesRegex(ValueError,'semantics'):self.inspect()
 def test_nonfinite_payload_rejected(self):
  p=self.folder/'x0_step012.pt';d=torch.load(p,weights_only=True);d['video'].flatten()[0]=float('nan');torch.save(d,p)
  with self.assertRaises(ValueError):self.inspect()
 def test_wrong_schema_rejected(self):
  self.man['captures'][0]['schema']='bad';self.save()
  with self.assertRaisesRegex(ValueError,'semantics'):self.inspect()
 def test_capture_subset_rejected(self):
  self.man['capture_steps_zero_based']=[5,10,15,19];self.save()
  with self.assertRaises(ValueError):self.inspect()
 def test_final_sigma_not_last_prediction_sigma(self):
  self.man['final_sampler_result']['sigma_next_video']=self.grid[19];self.save()
  with self.assertRaises(ValueError):self.inspect()
 def test_extra_pt_rejected(self):
  (self.folder/'extra.pt').write_bytes(b'extra')
  with self.assertRaises(ValueError):self.inspect()
 def test_manifest_schema_rejected(self):
  self.man['schema']='other';self.save()
  with self.assertRaises(ValueError):self.inspect()
class ConditionStorageTests(unittest.TestCase):
 def test_actual_embedding_cpu_copy_bytes_rng_unchanged(self):
  from H3EventAudit import Store
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);store=Store(root);x=torch.arange(40,dtype=torch.float32).reshape(1,5,8).to(torch.bfloat16);before=x.clone();rng=torch.get_rng_state().clone();rec=store.tensor(x);loaded=torch.load(root/rec['tensor_file'],weights_only=True)
   self.assertTrue(torch.equal(loaded,x));self.assertTrue(torch.equal(x,before));self.assertTrue(torch.equal(rng,torch.get_rng_state()));loaded[0,0,0]=99;self.assertTrue(torch.equal(x,before));self.assertEqual(store.tensor(x),rec)
if __name__=='__main__':unittest.main()
