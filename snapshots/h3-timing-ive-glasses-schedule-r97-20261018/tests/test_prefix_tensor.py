"""Tiny CPU tensors exercise actual saved-prefix reader; no CUDA/model loading."""
import importlib.util,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
HAS_TORCH=importlib.util.find_spec('torch') is not None
@unittest.skipUnless(HAS_TORCH,'CPU torch unavailable in local interpreter; required on actual target')
class ActualPrefix(unittest.TestCase):
 def fixture(self):
  import torch
  from capture_checks import signature
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);base=Path(d.name);manifests=[]
  for name in ('new','old'):
   folder=base/name;folder.mkdir();records=[]
   for i in range(15):
    v=torch.tensor([[float(i)]]);a=torch.tensor([[float(i+1)]])
    metadata={'run_id':name,'step_zero_based':i,'model_call_one_based':i+1,'video':signature(v),'audio':signature(a)}
    fn=f'x0_step{i:03d}.pt';torch.save({'video':v,'audio':a,'metadata':metadata},folder/fn);records.append(dict(file=fn,**metadata))
   manifests.append({'captures':records})
  return base,manifests
 def compare(self,base,m):
  from verify_control import compare_prefix
  return compare_prefix(base/'new',m[0],'new',base/'old',m[1],'old',{'video':(1,1),'audio':(1,1)})
 def test_exact_15_predictions_in_both_streams(self):
  b,m=self.fixture();rows=self.compare(b,m);self.assertEqual([r['step_zero_based'] for r in rows],list(range(15)));self.assertTrue(all(r[k] for r in rows for k in ('video','audio')))
 def test_changed_prediction14_detected(self):
  import torch
  from capture_checks import signature
  b,m=self.fixture();p=b/'new/x0_step014.pt';v=torch.load(p,weights_only=True);v['audio']+=.125;v['metadata']['audio']=signature(v['audio']);torch.save(v,p);m[0]['captures'][14]['audio']=signature(v['audio'])
  rows=self.compare(b,m);self.assertFalse(rows[-1]['audio']);self.assertTrue(rows[-1]['video'])
 def test_step15_is_outside_required_prefix(self):
  b,m=self.fixture();(b/'new/x0_step015.pt').write_bytes(b'not consumed');self.assertEqual(len(self.compare(b,m)),15)
 def test_metadata_wrong_index_rejected(self):
  import torch
  b,m=self.fixture();p=b/'new/x0_step014.pt';v=torch.load(p,weights_only=True);v['metadata']['model_call_one_based']=14;torch.save(v,p);m[0]['captures'][14]['model_call_one_based']=14
  with self.assertRaisesRegex(ValueError,'index mismatch'):self.compare(b,m)
 def test_mutated_tensor_without_manifest_update_rejected(self):
  import torch
  b,m=self.fixture();p=b/'new/x0_step000.pt';v=torch.load(p,weights_only=True);v['video']+=1;torch.save(v,p)
  with self.assertRaisesRegex(ValueError,'signature mismatch'):self.compare(b,m)
if __name__=='__main__':unittest.main()
