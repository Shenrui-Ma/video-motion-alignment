import copy,json,sys,tempfile,unittest,uuid,hashlib
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'extensions'))
from H3ForwardReverseRouter.sampler_gate import actual_prefix,signature,canonical_condition
class PrefixTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.ready=[torch.ones(1,2),torch.zeros(1,3)];rows=[]
  for i in range(6):
   meta={'physical_index':i,'branch':'native','seed':2026101311,'sigma':1-i/20,'sigma_next':1-(i+1)/20};p=self.root/f'{i}.pt';torch.save(dict(video=self.ready[0],audio=self.ready[1],metadata=meta),p);rows.append(dict(meta,file=str(p),file_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),normalized_stream_signatures=[signature(t) for t in self.ready]))
  self.binding={'native_0to5':rows};p=self.root/'native005.pt';meta=dict(schema='h3-x0-readout-v1',seed=2026101311,step_zero_based=5,normalization_stage='after_process_latent_out',audio_scale=4,video_latent_scale_factor=1);torch.save(dict(video=self.ready[0],audio=self.ready[1],metadata=meta),p);self.native={'file':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 def tearDown(self):self.tmp.cleanup()
 def test_all_six_actual_files(self):
  for i in range(6):self.assertTrue(actual_prefix(self.ready,i,self.binding,self.native)['actual_tensor_equal'])
 def test_wrong_current_tensor(self):
  with self.assertRaisesRegex(ValueError,'prefix mismatch'):actual_prefix([self.ready[0]+1,self.ready[1]],0,self.binding,self.native)
 def test_corrupt_file(self):
  Path(self.binding['native_0to5'][0]['file']).write_bytes(b'bad')
  with self.assertRaisesRegex(ValueError,'SHA'):actual_prefix(self.ready,0,self.binding,self.native)
 def test_bad_order_or_subset(self):
  for rows in (self.binding['native_0to5'][:5],list(reversed(self.binding['native_0to5']))):
   with self.assertRaises(ValueError):actual_prefix(self.ready,0,{'native_0to5':rows},self.native)
 def test_old_metadata_even_rehashed_rejected(self):
  row=self.binding['native_0to5'][0];p=Path(row['file']);v=torch.load(p,weights_only=True);v['metadata']['branch']='full';torch.save(v,p);row['file_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  with self.assertRaisesRegex(ValueError,'metadata'):actual_prefix(self.ready,0,self.binding,self.native)
 def test_native005_independent_file_required(self):
  self.native['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'R3 Native005'):actual_prefix(self.ready,5,self.binding,self.native)
 def test_only_two_corresponding_UUIDs_ignored(self):
  def tree():
   u=str(uuid.uuid4());return {'original':{'positive':[{'uuid':u,'condition':[1]}]},'processed':{'positive':[{'uuid':u,'value':2}]}}
  a,b=tree(),tree();self.assertEqual(canonical_condition(a),canonical_condition(b));b['processed']['positive'][0]['value']=3;self.assertNotEqual(canonical_condition(a),canonical_condition(b));b['processed']['positive'][0]['uuid']=str(uuid.uuid4())
  with self.assertRaises(ValueError):canonical_condition(b)
if __name__=='__main__':unittest.main()
