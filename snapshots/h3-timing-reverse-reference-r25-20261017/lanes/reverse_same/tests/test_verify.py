import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
import verify_completed as v
from H3X0Readout.core import tensor_signature
class VerifyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.shapes={'video':(1,2),'audio':(1,3)}
  self.tensors={'video':torch.tensor([[1.,2.]]),'audio':torch.tensor([[3.,4.,5.]])};self.meta={'run_id':'test',**{k:tensor_signature(x) for k,x in self.tensors.items()}};self.record={'file':'x.pt',**self.meta};self.save()
 def tearDown(self):self.tmp.cleanup()
 def save(self):torch.save({**self.tensors,'metadata':self.meta},self.root/'x.pt')
 def test_actual_snapshot_pass(self):
  with patch.object(v,'SHAPES',self.shapes):value,info=v.checked_snapshot(self.root,self.record,'test')
  self.assertEqual(info['sha256'],v.digest(self.root/'x.pt'));self.assertTrue(torch.equal(value['video'],self.tensors['video']))
 def test_actual_tensor_corruption(self):
  self.tensors['video'][0,0]=8;self.save()
  with patch.object(v,'SHAPES',self.shapes),self.assertRaises(ValueError):v.checked_snapshot(self.root,self.record,'test')
 def test_metadata_and_nonfinite(self):
  self.meta=dict(self.meta,run_id='other');self.save()
  with patch.object(v,'SHAPES',self.shapes),self.assertRaises(ValueError):v.checked_snapshot(self.root,self.record,'test')
  with self.assertRaises(ValueError):v.signature(torch.tensor([float('nan')]))
 def test_path_escape(self):
  for p in ('../outside','/tmp/outside'):
   with self.assertRaises(ValueError):v.safe_file(self.root,p)
 def test_per_record_semantics_corruption(self):
  good={'seed':2026101311,'geometry':{'width':1312,'height':736,'frames':141,'fps':24},'normalization_stage':'after_process_latent_out','audio_scale':4,'video_latent_scale_factor':1,'total_steps':20,'schema':'h3-x0-readout-v1'}
  v.check_record_semantics(good,2026101311)
  for key,value in [('seed',0),('audio_scale',1),('total_steps',19),('normalization_stage','raw'),('geometry',{'fps':30})]:
   with self.assertRaises(ValueError):v.check_record_semantics(dict(good,**{key:value}),2026101311)
 def test_captures_fixed_eight_plus_final(self):self.assertEqual(v.CAPTURES,(5,6,7,8,9,10,15,19))
if __name__=='__main__':unittest.main()
