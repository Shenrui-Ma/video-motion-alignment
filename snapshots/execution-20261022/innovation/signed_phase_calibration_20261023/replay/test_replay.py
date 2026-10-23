import unittest
from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
import torch
from reconstruct import pack,unpack,raw_x0,initialize,euler_update,sigma_grid
from source_oracles import actual_euler,actual_attention_and_layout
from capture import PassiveQKCapture,ProbeLayout,content_rms,inverse_actual_rope

torch.set_num_threads(1)
torch.set_grad_enabled(False)

class EulerTests(unittest.TestCase):
    def test_original_ast_every_intermediate_state(self):
        torch.manual_seed(12)
        streams=[torch.randn(1,24,3,2,4),torch.randn(1,32,2,5)]
        x=pack(streams);schedule=torch.linspace(1,0,21,dtype=torch.float32)
        denoised=[pack([torch.randn_like(streams[0]),4*torch.randn_like(streams[1])]) for _ in range(20)]
        actual=[];i=0
        def model(state,sigma,**kwargs):
            nonlocal i
            actual.append(state.clone());v=denoised[i];i+=1;return v
        final=actual_euler()(model,initialize(x,noise_scale=1.,initial_sigma=schedule[0]),schedule)
        state=initialize(x,noise_scale=1.,initial_sigma=schedule[0])
        for j in range(20):
            self.assertTrue(torch.equal(state,actual[j]))
            state=euler_update(state,denoised[j],schedule[j],schedule[j+1])
        self.assertTrue(torch.equal(final,state))
    def test_audio_restore_binary_scale(self):
        v=torch.randn(1,24,3,2,4);a=torch.randn(1,32,2,5)
        self.assertTrue(torch.equal(raw_x0(dict(video=v,audio=a/4),4),pack([v,a])))
    def test_audio_video_sigma_not_audio_sigma(self):
        x=torch.randn(1,1,10);d=torch.randn_like(x);s=torch.tensor(.93617022);sn=torch.tensor(.92307692)
        correct=euler_update(x,d,s,sn);sa=s/(4-3*s);san=sn/(4-3*sn)
        self.assertFalse(torch.equal(correct,euler_update(x,d,sa,san)))
    def test_pack_roundtrip(self):
        ss=[torch.randn(1,2,3,4),torch.randn(1,1,2,5)]
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(ss,unpack(pack(ss),[x.shape for x in ss]))))
    def test_reject_partial_sigma_initialization(self):
        with self.assertRaises(ValueError): initialize(torch.ones(1,1,3),noise_scale=1,initial_sigma=.9)
    def test_reject_altered_noise_scale(self):
        with self.assertRaises(ValueError): initialize(torch.ones(1,1,3),noise_scale=.9,initial_sigma=1)
    def test_grid_exact_fp32(self):
        s=torch.linspace(1,0,21);self.assertTrue(torch.equal(sigma_grid(s.double().tolist()),s))
        with self.assertRaises(ValueError):sigma_grid([1-i/20 for i in range(21)])
    def test_incomplete_audio_rejected(self):
        with self.assertRaises(ValueError):pack([torch.ones(1,1,1)])

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.inference=torch.inference_mode();self.inference.__enter__()
        torch.manual_seed(928)
        self.s=actual_attention_and_layout();t,h,w=4,4,8
        refs=[dict(kind='video',latent_t=t,latent_h=h,latent_w=w,ref_audio_t=0)]
        self.layout=self.s['PackedLayout'](3,t,h,w,2,refs=refs)
        self.plan=ProbeLayout.from_actual(self.layout,(1,24,t,h,w),13)
        self.attn=self.s['Attention'](16,2,8,1e-5,operations=torch.nn).eval()
        pos=self.layout.position_ids.float();half=torch.cat([pos*.01,pos*.02],-1)[:,:3]
        self.rope=self.s['rope_rotation_table'](torch.cat([half,half],-1),torch.float32)
        self.x=torch.randn(self.layout.seq_len,16)
    def tearDown(self):self.inference.__exit__(None,None,None)
    def test_real_source_attention_exact_passive(self):
        original=self.x.clone();rng=torch.get_rng_state().clone()
        base=self.attn(self.x,self.rope)
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with cap: observed=self.attn(self.x,self.rope)
        self.assertTrue(torch.equal(base,observed));self.assertTrue(torch.equal(self.x,original));self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertEqual(len(self.attn._forward_hooks),0);self.assertEqual(len(self.attn.qkv_proj._forward_hooks),0)
    def test_raw_and_actual_exact_source_values(self):
        a=self.attn;raw=a.qkv_proj(self.x).detach().clone();q,k,_=raw.split(16,-1)
        ci,ri=self.plan.indices('cpu')
        cap=PassiveQKCapture(a,self.plan,step=19)
        with cap:a(self.x,self.rope)
        for name,src,ix,norm in [('Q_C',q,ci,a.q_norm),('Q_R',q,ri,a.q_norm),('K_R',k,ri,a.k_norm)]:
            want=src[ix].reshape(4,8,2,8)
            self.assertTrue(torch.equal(cap.data['raw_'+name],want))
            rt=self.rope[:,ix]
            one=want.reshape(1,32,2,8)
            actual=self.s['comfy'].quant_ops.ck.rms_rope_split_half(one,one,rt,norm.weight,norm.weight,epsilon=norm.eps,rot_dim=6)[0]
            self.assertTrue(torch.equal(actual.reshape(4,8,2,8),cap.data['actual_'+name]))
    def test_snapshots_do_not_alias_buffer(self):
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with cap:self.attn(self.x,self.rope)
        old=cap.data['raw_Q_C'].clone()
        self.attn(self.x*2,self.rope)
        self.attn.q_norm.weight.data.zero_()
        self.assertTrue(torch.equal(old,cap.data['raw_Q_C']))
        self.assertFalse(torch.equal(self.attn.q_norm.weight,cap.data['q_norm_weight']))
    def test_content_inverse_rope_fp32(self):
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with cap:self.attn(self.x,self.rope)
        norm=content_rms(cap.data['raw_Q_C'],cap.data['q_norm_weight'],cap.data['q_norm_eps'])
        inv=inverse_actual_rope(cap.data['actual_Q_C'],cap.data['rope_canvas'],6)
        self.assertTrue(torch.allclose(norm.double(),inv,atol=4e-7,rtol=4e-7))
    def test_no_implicit_step_zero(self):
        with self.assertRaises(ValueError):PassiveQKCapture(self.attn,self.plan,step=0)
    def test_reentrant_duplicate_rejected_and_removed(self):
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with self.assertRaises(RuntimeError):
            with cap:
                self.attn(self.x,self.rope);self.attn(self.x,self.rope)
        self.assertFalse(self.attn._forward_hooks)
    def test_missing_rope_rejected(self):
        with self.assertRaises(ValueError):
            with PassiveQKCapture(self.attn,self.plan,step=9):self.attn(self.x)
    def test_failure_removes_hooks(self):
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with self.assertRaises(RuntimeError):
            with cap:raise RuntimeError('injected')
        self.assertFalse(self.attn._forward_hooks);self.assertFalse(self.attn.qkv_proj._forward_hooks)
    def test_actual_full_geometry_and_mask(self):
        for t,valid,nvalid in [(32,105,31),(47,144,42)]:
            refs=[dict(kind='video',latent_t=t,latent_h=46,latent_w=82,ref_audio_t=0)]
            l=self.s['PackedLayout'](127,t,46,82,178,refs=refs)
            p=ProbeLayout.from_actual(l,(1,24,t,46,82),valid)
            self.assertEqual(sum(p.valid_bins),nvalid);self.assertEqual(p.frame_rows,943)
            self.assertEqual(p.spatial_ids,(0,135,269,404,538,673,807,942))
    def test_multiple_reference_rejected(self):
        self.layout.segments.append((0,32,'ref_img'))
        with self.assertRaises(ValueError):ProbeLayout.from_actual(self.layout,(1,24,4,4,8),13)
    def test_save_exclusive(self):
        cap=PassiveQKCapture(self.attn,self.plan,step=9)
        with cap:self.attn(self.x,self.rope)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'capture.pt';cap.save(p)
            with self.assertRaises(FileExistsError):cap.save(p)
    def test_training_rejected(self):
        self.attn.train()
        with self.assertRaises(ValueError):PassiveQKCapture(self.attn,self.plan,step=9,in_training=True)

if __name__=='__main__':unittest.main()
