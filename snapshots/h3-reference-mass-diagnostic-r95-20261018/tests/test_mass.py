import copy,hashlib,json,math,sys,unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from r95_kernel import route_attention,MODES
from r95_kernel.snapshot import core as parent
from oracle import fixture,dense_attention,dense_oracle

torch.set_num_threads(2)
class MassTests(unittest.TestCase):
 def call(self,mode,*,dtype=torch.float64,gain=3,alpha=1,bias=None,**kw):
  q,k,v,p=fixture(dtype,bias);return route_attention(q,k,v,2,p,mode=mode,reference_gain=gain,alpha=alpha,attention=dense_attention,**kw),(q,k,v,p)
 def test_group_gain_matches_log_bias(self):
  for r in (.1,.5,1.01,3,100):
   with self.subTest(r=r):
    out,(q,k,v,p)=self.call('reference_group_gain',gain=r)
    torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=r,mode='reference_group_gain'),rtol=2e-6,atol=2e-6)
 def test_combined_matches_normalized_samebin_logits(self):
  for r in (.1,.5,1.01,3,100):
   with self.subTest(r=r):
    out,(q,k,v,p)=self.call('samebin_group_gain',gain=r)
    torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=r,mode='samebin_group_gain'),rtol=2e-6,atol=2e-6)
 def test_naive_mask_plus_gain_is_different(self):
  out,(q,k,v,p)=self.call('samebin_group_gain')
  wrong=dense_oracle(q,k,v,p,gain=3,mode='samebin_group_gain',naive_samebin_bias=True)
  self.assertGreater((out-wrong).abs().max().item(),.01)
 def test_gain_one_exact_parent_paths(self):
  for dtype in (torch.float64,torch.float32,torch.float16,torch.bfloat16):
   for mode,legacy in [('reference_group_gain','native'),('samebin_group_gain','mass_preserve')]:
    for alpha in (.25,1):
     with self.subTest(dtype=dtype,mode=mode,alpha=alpha):
      q,k,v,p=fixture(dtype)
      a=route_attention(q,k,v,2,p,mode=mode,reference_gain=1,alpha=alpha,attention=dense_attention)
      b=parent.route_attention(q,k,v,2,p,mode=legacy,alpha=alpha,attention=dense_attention)
      self.assertTrue(torch.equal(a,b))
 def test_alpha_zero_exact_native(self):
  for dtype in (torch.float64,torch.float32,torch.float16,torch.bfloat16):
   for mode in MODES:
    for r in (1e-300,.1,1,3,1e300):
     with self.subTest(dtype=dtype,mode=mode,r=r):
      q,k,v,p=fixture(dtype)
      a=route_attention(q,k,v,2,p,mode=mode,reference_gain=r,alpha=0,attention=dense_attention)
      b=parent.route_attention(q,k,v,2,p,mode='native',attention=dense_attention)
      self.assertTrue(torch.equal(a,b))
 def test_alpha_blend(self):
  for mode in MODES:
   out,(q,k,v,p)=self.call(mode,alpha=.25)
   torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=3,mode=mode,alpha=.25),rtol=2e-6,atol=2e-6)
 def test_other_modality_queries_exact(self):
  for mode in MODES:
   out,(q,k,v,p)=self.call(mode,dtype=torch.bfloat16)
   native=parent.route_attention(q,k,v,2,p,mode='native',attention=dense_attention)
   self.assertTrue(torch.equal(out[:,:24],native[:,:24]))
 def test_inputs_unmodified(self):
  q,k,v,p=fixture();before=[x.clone() for x in (q,k,v)];pp=copy.deepcopy(p)
  route_attention(q,k,v,2,p,mode='samebin_group_gain',reference_gain=3,attention=dense_attention)
  for x,y in zip((q,k,v),before):self.assertTrue(torch.equal(x,y))
  self.assertEqual(p,pp)
 def test_gain_invalid_even_if_disabled(self):
  q,k,v,p=fixture()
  for r in (0,-1,float('nan'),float('inf'),-float('inf'),True,'3',None):
   for alpha in (0,1):
    with self.subTest(r=r,alpha=alpha),self.assertRaises(ValueError):route_attention(q,k,v,2,p,reference_gain=r,alpha=alpha,attention=dense_attention)
 def test_alpha_invalid(self):
  q,k,v,p=fixture()
  for a in (-.1,1.1,float('nan'),float('inf'),True):
   with self.subTest(a=a),self.assertRaises(ValueError):route_attention(q,k,v,2,p,alpha=a,attention=dense_attention)
 def test_invalid_mode_and_ranges(self):
  q,k,v,p=fixture()
  with self.assertRaises(ValueError):route_attention(q,k,v,2,p,mode='hard_route',reference_gain=3,attention=dense_attention)
  bad={**p,'reference_video_segment':(6,99)}
  with self.assertRaises(ValueError):route_attention(q,k,v,2,bad,reference_gain=3,attention=dense_attention)
 def test_mass_near_zero_one(self):
  for bias in (-40,40):
   for mode in MODES:
    for r in (.1,3,1e-300,1e300):
     with self.subTest(bias=bias,mode=mode,r=r):
      out,(q,k,v,p)=self.call(mode,bias=bias,gain=r)
      torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=r,mode=mode),rtol=2e-6,atol=2e-6)
      self.assertTrue(torch.isfinite(out).all())
 def test_half_precision_oracle(self):
  for dtype,tol in [(torch.float16,.003),(torch.bfloat16,.025),(torch.float32,2e-6)]:
   for mode in MODES:
    for r in (.1,3,100):
     for bias in (None,-40,40):
      with self.subTest(dtype=dtype,mode=mode,r=r,bias=bias):
       out,(q,k,v,p)=self.call(mode,dtype=dtype,gain=r,bias=bias)
       expected=dense_oracle(q,k,v,p,gain=r,mode=mode)
       torch.testing.assert_close(out,expected,rtol=tol,atol=tol)
 def test_half_precision_extreme_finite_gains(self):
  for dtype in (torch.float16,torch.bfloat16):
   for mode in MODES:
    for r in (1e-300,1e300):
     for bias in (-40,40):
      out,(q,k,v,p)=self.call(mode,dtype=dtype,gain=r,bias=bias)
      self.assertTrue(torch.isfinite(out).all())
      torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=r,mode=mode),rtol=.025,atol=.025)
 def test_below_one_explicit_complement_recorded(self):
  logs=[];out,_=self.call('samebin_group_gain',gain=.1,audit=logs)
  self.assertEqual(logs[0]['execution_path'],'gain_below_one_explicit_complement');self.assertEqual(logs[0]['additional_attention_calls'],1)
 def test_stats_measure_boost_and_actual_change(self):
  logs=[];out,_=self.call('samebin_group_gain',audit=logs)
  s=logs[0]['stats'];self.assertGreater(s['boosted_ref_mass_mean'],s['ref_mass_mean']);self.assertGreater(s['written_delta_rms'],0);self.assertTrue(s['finite'])
  self.assertEqual(logs[0]['additional_attention_calls'],0)
 def test_effective_mass_with_partial_alpha(self):
  logs=[];self.call('samebin_group_gain',alpha=.25,audit=logs)
  s=logs[0]['stats']
  torch.testing.assert_close(s['effective_ref_mass_mean'],.75*s['ref_mass_mean']+.25*s['boosted_ref_mass_mean'])
 def test_snapshot_byte_identity(self):
  source=ROOT.parent/'h3-timing-flexiact-expanded-r85-20261018/extensions/H3TemporalRouter'
  for name in ('core.py','layout.py'):
   self.assertEqual((source/name).read_bytes(),(ROOT/'r95_kernel/snapshot'/name).read_bytes())
 def test_fallback_audit(self):
  logs=[];self.call('samebin_group_gain',gain=1,audit=logs)
  self.assertEqual(logs[0]['execution_path'],'r85_exact_mass_preserve')
  self.assertTrue(torch.equal(logs[0]['stats']['ref_mass_mean'],logs[0]['stats']['boosted_ref_mass_mean']))
 def test_neighbor_geometry_reused(self):
  for offset in (-5,0,5):
   out,(q,k,v,p)=self.call('samebin_group_gain',radius=1,time_offset=offset)
   torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=3,mode='samebin_group_gain',radius=1,time_offset=offset),rtol=2e-6,atol=2e-6)
 def test_reference_all_keys(self):
  q,k,v,p=fixture();p={**p,'reference_video_segment':(0,32),'latent_interval_half_open':(6,8)}
  for r in (.1,3):
   for mode in MODES:
    out=route_attention(q,k,v,2,p,mode=mode,reference_gain=r,attention=dense_attention)
    torch.testing.assert_close(out,dense_oracle(q,k,v,p,gain=r,mode=mode),rtol=2e-6,atol=2e-6)
 def test_no_cuda_initialization(self):self.assertFalse(torch.cuda.is_initialized())

if __name__=='__main__':unittest.main(verbosity=2)
