import unittest,sys,json,tempfile,hashlib,copy
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'));sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'tests'))
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.dynamic_support import bins_for,make_gain
from H3AutomaticWindowRouter.pair_gate import HistoricalPairGate
from H3AutomaticWindowRouter import transport as t
from H3AutomaticWindowRouter.dependencies import router
from counterfactual_support import dense_attention
from pose_test_support import row,measurement
from r27_contract import validate_job
class Tests(unittest.TestCase):
 def test_policy_off_early_restart(self):
  self.assertFalse(Controller().select(0,measurement('always',0))['chosen_full'])
  c=Controller();ds=[c.select(i,measurement('restart',i)) for i in range(20)]
  self.assertEqual([i for i,d in enumerate(ds) if d['chosen_full']],[1,2,5]+list(range(7,20)))
  self.assertGreater(len(ds[1]['physical_intervals']),1)
 def test_unknown_breaks_and_technical_aborts(self):
  c=Controller();c.select(0,measurement('always',0));u=measurement('off',1);u['observer']['status']='unknown_visibility'
  self.assertFalse(c.select(1,u)['chosen_full']);self.assertFalse(c.select(2,measurement('always',2))['chosen_full'])
  self.assertTrue(c.select(3,measurement('always',3))['chosen_full'])
  with self.assertRaises(ValueError):c.select(4,{'status':'failed'})
 def test_shared_arm(self):
  c=Controller();a=measurement('off',0);a['observer']['windows']=[row(feature='left_arm_direction')];c.select(0,a)
  b=measurement('off',1);b['observer']['windows']=[row(feature='right_arm_direction')]
  self.assertFalse(c.select(1,b)['chosen_full'])
 def test_boundaries(self):
  bins,mapping=bins_for([[50,65],[66,81],[50,65]])
  self.assertEqual(bins,list(range(14,25)));self.assertEqual(bins_for([[0,0],[140,140]])[0],[0,41])
  for intervals in ([[1,141]],[[2,1]],[[1.0,2]],[[True,2]]):
   with self.assertRaises(ValueError):bins_for(intervals)
 def test_mask_algebra_rows_inputs_rng(self):
  gen=torch.Generator().manual_seed(21);q,k,v=[torch.randn(1,2,84,4,generator=gen,dtype=torch.float32) for _ in range(3)]
  plan={'seq_len':84,'frame_rows':1,'latent_interval_half_open':[0,42],'query_interval_half_open':[42,84],'reference_video_segment':[0,42]}
  old=[x.clone() for x in (q,k,v)];rng=torch.random.get_rng_state().clone()
  native=router.route_attention(q,k,v,2,plan,mode='native',attention=dense_attention)
  zero=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain([],(1,1)),attention=dense_attention)
  self.assertTrue(torch.equal(native,zero))
  full=router.route_attention(q,k,v,2,plan,mode='mass_preserve',attention=dense_attention)
  one=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain(list(range(42)),(1,1)),attention=dense_attention)
  self.assertTrue(torch.equal(full,one))
  bins=[0,14,15,40];out=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain(bins,(1,1)),attention=dense_attention)
  selected=[42+i for i in bins];others=[i for i in range(84) if i not in selected]
  self.assertTrue(torch.equal(out[:,others],native[:,others]));self.assertTrue(torch.equal(out[:,selected],full[:,selected]))
  for a,b in zip(old,(q,k,v)):self.assertTrue(torch.equal(a,b))
  self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))
 def test_inference_mode_mask(self):
  with torch.inference_mode():
   self.test_mask_algebra_rows_inputs_rng()
 def test_prefix_qualification_never_resets(self):
  g=HistoricalPairGate();s=type('S',(),{'audit':{'counterfactual':{}}})()
  g.decision(s,1,{'chosen_full':True});self.assertTrue(g.native_comparable(1));self.assertFalse(g.native_comparable(2))
  g.decision(s,3,{'chosen_full':False});self.assertFalse(g.native_comparable(4))
 def test_graphs(self):
  for case in json.loads((ROOT/'configs/protocol.json').read_text())['cases']:
   d=validate_job(case['run_id'],inputs=False);self.assertEqual(d['case'],case)
 def test_frozen_policy_copy(self):
  self.assertEqual((ROOT/'scripts/automatic_window_policy.py').read_bytes(),(ROOT/'extensions/H3AutomaticWindowRouter/automatic_window_policy.py').read_bytes())
 def test_request_bounds_both_seeds(self):
  self.assertEqual(t.case_for('r27_s05_bad1311_auto')['seed'],2026101311)
  self.assertEqual(t.case_for('r27_s05_normal1313_auto')['seed'],2026101313)
  with self.assertRaises(ValueError):t.case_for('unknown')

class NegativeTests(unittest.TestCase):
 def test_dense_oracle(self):
  import math
  gen=torch.Generator().manual_seed(44);q,k,v=[torch.randn(1,2,84,4,generator=gen) for _ in range(3)]
  plan={'seq_len':84,'frame_rows':1,'latent_interval_half_open':[0,42],'query_interval_half_open':[42,84],'reference_video_segment':[0,42]}
  bins=[0,14,41];prob=(q@k.transpose(-1,-2)/2).softmax(-1);before=prob.clone()
  for i in bins:
   qi=42+i;mass=prob[:,:,qi,:42].sum(-1);prob[:,:,qi,:42]=0;prob[:,:,qi,i]=mass
   self.assertTrue(torch.allclose(prob[:,:,qi,:42].sum(-1),before[:,:,qi,:42].sum(-1),atol=1e-7))
  expected=(prob@v).transpose(1,2).reshape(1,84,8)
  actual=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain(bins,(1,1)),attention=dense_attention)
  self.assertTrue(torch.allclose(actual,expected,atol=2e-6,rtol=2e-6))
 def test_invalid_mask(self):
  for bins in ([1,1],[3,2],[-1],[42],[True]):
   with self.assertRaises(ValueError):make_gain(bins)
 def test_stale_controller_never_stops_new_generation(self):
  import service
  from unittest.mock import patch
  old={'pid':1,'identity':{'start_ticks':'old'}};new={'pid':2,'identity':{'start_ticks':'new'}}
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'processes';p.mkdir();(p/'service.json').write_text(json.dumps(new))
   with patch.object(service,'RUN',Path(tmp)),patch.object(service.os,'kill') as kill:
    with self.assertRaisesRegex(RuntimeError,'stale controller'):service.stop(expected_record=old)
    kill.assert_not_called()
 def test_bad_scan_shape_aborts(self):
  from scan_current_pose import valid_pose
  d=json.loads((ROOT/'configs/source.pose.json').read_text());d['frames'][1]['time_s']=.99
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'bad.json';p.write_text(json.dumps(d))
   with self.assertRaises(ValueError):valid_pose(p)
 def test_missing_torso_unknown(self):
  from scan_current_pose import observe
  d=json.loads((ROOT/'configs/source.pose.json').read_text())
  for f in d['frames']:f['selected_person']=None
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'invisible.json';p.write_text(json.dumps(d));out=observe(ROOT/'configs/source.pose.json',p,0)
   self.assertEqual(out['status'],'unknown_visibility');self.assertEqual(out['windows'],[])

 def test_stale_controller_cannot_submit_to_new_generation(self):
  import job
  from unittest.mock import patch
  old={'pid':1,'identity':{'start_ticks':'old'}};new={'pid':2,'identity':{'start_ticks':'new'}}
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'processes').mkdir();(root/'logs').mkdir()
   with patch.object(job,'RUN',root),patch.object(job,'validate_job',return_value={}),patch.object(job,'active_service',return_value=new),patch.object(job,'request') as request:
    with self.assertRaisesRegex(RuntimeError,'stale controller'):job.submit('case',expected_owner=old)
    request.assert_not_called()

if __name__=='__main__':unittest.main()
