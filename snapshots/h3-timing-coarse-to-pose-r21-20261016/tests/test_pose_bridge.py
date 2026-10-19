import copy,json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
import torch
R=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'extensions'))
from H3CoarsePoseObserverRouter import transport as t
from H3CoarsePoseObserverRouter.live_observer import bridge10,parent_guard
from H3CoarsePoseObserverRouter import pair_gate as pg
class BridgeTest(unittest.TestCase):
 def test_exact_archived_normal_bridge(self):
  files={k:t.read_json(R/'configs'/('bridge_'+k+'.json')) for k in ('decode','pose','observer')}
  self.assertTrue(bridge10({},files['observer'],files['pose'],files['decode'])['pass'])
  for value in files['observer']['diagnostics']['50:65'].values():
   for feature in ('arm_direction','wrist_relative'):self.assertEqual(value[feature]['reliable_lag_frames'],-1)
 def test_changed_frame_rejected(self):
  files={k:t.read_json(R/'configs'/('bridge_'+k+'.json')) for k in ('decode','pose','observer')}
  files['decode']['preencode_rgb24_frame_sha256'][10]='bad'
  with self.assertRaises(ValueError):bridge10({},files['observer'],files['pose'],files['decode'])
 def test_producer_evidence_not_processed_certificate(self):
  old=t.read_json(R/'configs/parent_r14_conditioning.json');actual=copy.deepcopy(old);actual['run_id']='new'
  pg.condition_audit_matches(actual,old)
  actual['native_vae_calls'][1]['latent']['sha256']='bad'
  with self.assertRaises(ValueError):pg.condition_audit_matches(actual,old)
 def test_augmentation_seed_not_noise_seed(self):
  tree={'processed':{'positive':[{'model_conds':{'minimax_payload':{'cond':{'seed':2026101313}}}}]}}
  self.assertFalse(pg.augmentation_contract(tree)['historical_post_augmentation_tensor_available'])
  for key,value in [('seed',2026101311),('seed',True),('visual_cond_noise_aug',1.0),('audio_cond_noise_aug',.999)]:
   bad=copy.deepcopy(tree);bad['processed']['positive'][0]['model_conds']['minimax_payload']['cond'][key]=value
   with self.assertRaises(ValueError):pg.augmentation_contract(bad)
 def test_first_ON_current_native_then_permanent_NA(self):
  with tempfile.TemporaryDirectory() as folder:
   root=pathlib.Path(folder);old=root/'audit/x0'/pg.OLD_RUN;old.mkdir(parents=True)
   video=torch.ones(1);audio=torch.ones(1)*2
   signatures=[pg.readout.tensor_signature(v) for v in (video,audio)]
   endpoint=root/'current.pt';torch.save({'video':video,'audio':audio},endpoint);torch.save({'video':video,'audio':audio},old/'x0_step006.pt')
   gate=pg.HistoricalPairGate();gate.records={6:{'file':'x0_step006.pt','sigma_video':.9,'sigma_next_video':.8,'video':signatures[0],'audio':signatures[1]}}
   state=types.SimpleNamespace(audit={'counterfactual':{'pair_gates':[]}})
   row={'physical_index':6,'branch':'native','sigma':.9,'sigma_next':.8,'normalized_stream_signatures':signatures,'file':str(endpoint)}
   with patch.object(pg,'OLD_ROOT',root):gate.branch(state,None,None,row)
   self.assertEqual(gate.done,{6});gate.decision(state,6,{'chosen_full':True})
   self.assertTrue(gate.native_comparable(6));self.assertFalse(gate.native_comparable(7))
   gate.branch(state,None,None,dict(row,branch='full'))
   gate.decision(state,7,{'chosen_full':False});gate.branch(state,None,None,dict(row,physical_index=10))
   self.assertEqual(gate.first_on,6);self.assertFalse(gate.native_comparable(10))
   self.assertEqual(state.audit['counterfactual']['normal_preservation']['status'],'scientific_failure')
   self.assertEqual([g.get('status') for g in state.audit['counterfactual']['pair_gates']],[None,'not_applicable','not_applicable'])
 def test_first_ON_at10_keeps_native10_bridge_eligible(self):
  g=pg.HistoricalPairGate();s=types.SimpleNamespace(audit={'counterfactual':{'pair_gates':[]}})
  g.decision(s,10,{'chosen_full':True});self.assertTrue(g.native_comparable(10));self.assertFalse(g.native_comparable(11))
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
