import math,sys,unittest
from pathlib import Path
from unittest import mock
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from H3TemporalRouter.combined import combined_attention
from H3TemporalRouter.reference_origin import TemporalPhaseRotation
from H3TemporalRouter.core import route_attention

def dense(q,k,v):
 logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);return logits.softmax(-1)@v,logits.logsumexp(-1).float()

class CombinedTests(unittest.TestCase):
 def setUp(self):
  torch.manual_seed(148);self.q,self.k,self.v=[torch.randn(1,2,16,128,dtype=torch.float64) for _ in range(3)]
  self.plan={'query_interval_half_open':[12,16],'reference_video_segment':[2,8],
             'target_video_segment':[10,16],'latent_interval_half_open':[1,3],'frame_rows':2}
  self.rotation=TemporalPhaseRotation(torch.linspace(.01,.2,16,dtype=torch.float64),-7.)
 def run_op(self,**kw):return combined_attention(self.q,self.k,self.v,2,self.plan,kw.pop('rotation',self.rotation),attention=kw.pop('attention',dense),**kw)
 def test_phase_zero_exact_existing_fixed(self):
  old=route_attention(self.q,self.k,self.v,2,self.plan,mode='mass_preserve',attention=dense)
  self.assertTrue(torch.equal(old,self.run_op(rotation=TemporalPhaseRotation(self.rotation.inv_freq,0))))
 def test_alpha_zero_exact_native_single_call(self):
  calls=[]
  def backend(*a):calls.append(a);return dense(*a)
  old=route_attention(self.q,self.k,self.v,2,self.plan,attention=dense)
  self.assertTrue(torch.equal(old,self.run_op(alpha=0,attention=backend)));self.assertEqual(len(calls),1)
 def test_original_mass_unshifted_and_exact_local_keys(self):
  calls=[];mass=[]
  def backend(*a):calls.append(tuple(x.clone() for x in a));return dense(*a)
  def stats(before,changed,m,logm):mass.append((m.clone(),logm.clone()));return torch.zeros(5)
  with mock.patch('H3TemporalRouter.combined._bounded_stats',stats):self.run_op(attention=backend,diagnostics=[])
  self.assertEqual(len(calls),3)
  self.assertTrue(torch.equal(calls[0][0],self.q));self.assertTrue(torch.equal(calls[1][0],self.q[:,:,12:16]))
  _,full_lse=dense(self.q,self.k,self.v);_,ref_lse=dense(self.q[:,:,12:16],self.k[:,:,2:8],self.v[:,:,2:8])
  self.assertTrue(torch.equal(mass[0][1],ref_lse.float()-full_lse[:,:,12:16].float()))
  self.assertTrue(torch.equal(calls[2][1][0:1],self.k[:,:,4:6]));self.assertTrue(torch.equal(calls[2][1][1:2],self.k[:,:,6:8]))
 def test_dense_single_correction_and_unchanged_other_queries(self):
  full,fl=dense(self.q,self.k,self.v);original,rl=dense(self.q[:,:,12:16],self.k[:,:,2:8],self.v[:,:,2:8])
  local=torch.cat([dense(self.rotation(self.q[:,:,12+i*2:14+i*2]),self.k[:,:,4+i*2:6+i*2],self.v[:,:,4+i*2:6+i*2])[0] for i in range(2)],dim=2)
  expected=full.clone();expected[:,:,12:16]=(full[:,:,12:16].float()+(rl.float()-fl[:,:,12:16].float()).clamp(max=0).exp().unsqueeze(-1)*(local.float()-original.float())).to(full.dtype)
  actual=self.run_op().reshape(1,16,2,128).transpose(1,2)
  self.assertTrue(torch.equal(actual,expected));self.assertTrue(torch.equal(actual[:,:,:12],full[:,:,:12]))
 def test_inputs_and_frequency_unmodified(self):
  old=[x.clone() for x in (self.q,self.k,self.v,self.rotation.inv_freq)];rng=torch.random.get_rng_state().clone()
  self.run_op()
  for a,b in zip((self.q,self.k,self.v,self.rotation.inv_freq),old):self.assertTrue(torch.equal(a,b))
  self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))
 def test_rejects_changed_local_selection(self):
  for kw in ({'radius':1},{'time_offset':1}):
   with self.assertRaises(ValueError):self.run_op(**kw)

if __name__=='__main__':unittest.main()
