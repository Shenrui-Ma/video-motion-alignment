import copy,pathlib,sys,types,unittest
import torch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'extensions'))
from H3PoseObserverRouter import transport as t
from H3PoseObserverRouter.live_observer import bridge10,parent_guard
from H3PoseObserverRouter.pair_gate import canonical_condition
class BridgeTest(unittest.TestCase):
 def test_exact_archived_bridge(self):
  files={k:t.read_json(R/'configs'/('bridge_'+k+'.json')) for k in ('decode','pose','observer')}
  self.assertTrue(bridge10({},files['observer'],files['pose'],files['decode'])['pass'])
 def test_changed_frame_rejected(self):
  files={k:t.read_json(R/'configs'/('bridge_'+k+'.json')) for k in ('decode','pose','observer')}
  files['decode']['preencode_rgb24_frame_sha256'][10]='bad'
  with self.assertRaises(ValueError):bridge10({},files['observer'],files['pose'],files['decode'])
 def test_two_UUID_exceptions_only(self):
  tree=t.read_json(R/'configs/parent_r10_audit.json')['counterfactual']['conditioning']['tree'];other=copy.deepcopy(tree)
  for k in ('original','processed'):other[k]['positive'][0]['uuid']='fresh'
  self.assertEqual(canonical_condition(tree),canonical_condition(other))
  other['original']['positive'][0]['cross_attn']['sha256']='changed'
  self.assertNotEqual(canonical_condition(tree),canonical_condition(other))
 def test_actual_grid_guard(self):
  options={'transformer_options':{'sample_sigmas':torch.tensor([1.,.5,0.])}}
  guider=types.SimpleNamespace(original_conds={},conds={},model_patcher=types.SimpleNamespace())
  s=types.SimpleNamespace(model=torch.nn.Linear(1,1),guider=guider,sample_options=options,grid=torch.tensor([1.,.5,0.]),original_sigmas=torch.tensor([1.,.5,0.]))
  x=torch.zeros(1);sigma=torch.ones(1);before=parent_guard(s,x,sigma,x)
  options['transformer_options']['sample_sigmas'][1]=.6
  self.assertNotEqual(before,parent_guard(s,x,sigma,x));self.assertEqual(s.grid.tolist(),[1.,.5,0.])
 def test_original_sampler_grid_guard(self):
  options={'transformer_options':{'sample_sigmas':torch.tensor([1.,.5,0.])}}
  s=types.SimpleNamespace(model=torch.nn.Linear(1,1),guider=types.SimpleNamespace(original_conds={},conds={},model_patcher=types.SimpleNamespace()),sample_options=options,grid=torch.tensor([1.,.5,0.]),original_sigmas=torch.tensor([1.,.5,0.]))
  x=torch.zeros(1);before=parent_guard(s,x,x,x);s.original_sigmas[1]=.6
  self.assertNotEqual(before,parent_guard(s,x,x,x))
if __name__=='__main__':unittest.main()
