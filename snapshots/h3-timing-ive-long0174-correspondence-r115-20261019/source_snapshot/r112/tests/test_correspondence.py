import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import torch
import hashlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'))
sys.path.insert(0,str(ROOT/'scripts'))
from H3TemporalRouter import correspondence as c
from H3TemporalRouter import core


def dense(q,k,v):
    dtype=torch.float64 if q.dtype==torch.float64 else torch.float32
    scores=q.to(dtype)@k.to(dtype).transpose(-1,-2)/math.sqrt(q.shape[-1])
    return (scores.softmax(-1)@v.to(dtype)).to(q.dtype),scores.logsumexp(-1)


def fixture(dtype=torch.float64):
    gen=torch.Generator().manual_seed(112)
    q,k,v=[torch.randn(1,2,33,8,generator=gen,dtype=torch.float64).to(dtype) for _ in range(3)]
    for t in range(4):
        for s in range(3):
            ident=(s-t)%3
            for h in range(2):
                value=torch.zeros(8,dtype=dtype);value[ident]=1;value[3]=.15*t*(ident+1);value[4]=.1*(h+1)
                v[0,h,6+t*3+s]=value
    plan={'seq_len':33,'segments':[(0,2,'text'),(2,4,'ref_img'),(4,6,'ref_audio'),(6,18,'ref_img'),(18,21,'audio'),(21,33,'video')],
          'reference_image_segments':[[2,4]],'reference_video_segment':[6,18],'target_video_segment':[21,33],
          'query_interval_half_open':[21,30],'latent_interval_half_open':[0,3],'frame_rows':3}
    bank,_=c.build_bank(v[:,:,6:18],frame_rows=3,valid_bins=3,block=0)
    return q,k,v,plan,bank


def explicit(q,k,v,plan,bank,mode,alpha=1.):
    # An independent probability scatter, without the production gather maps.
    a=(q.double()@k.double().transpose(-1,-2)/math.sqrt(q.shape[-1])).softmax(-1)
    b=a.clone();ra,rb=plan['reference_video_segment'];qa,qb=plan['query_interval_half_open'];p=plan['frame_rows'];valid=bank.metadata['geometry']['valid_bins']
    for qi in range(qa,qb):
        tau=plan['latent_interval_half_open'][0]+(qi-qa)//p
        b[:,:,qi,ra:rb]=(1-alpha)*a[:,:,qi,ra:rb]
        for t in range((rb-ra)//p):
            for s in range(p):
                u,j=t,s
                if t<valid and t!=tau:
                    u=t+(1 if tau>t else -1)
                    match=int(bank.forward[t,s] if u>t else bank.backward[u,s])
                    if match>=0:j=match if mode=='matched_one_bin' else s
                    else:u=t
                b[:,:,qi,ra+u*p+j]+=alpha*a[:,:,qi,ra+t*p+s]
    return a,b,(b@v.double()).transpose(1,2).reshape(1,q.shape[-2],-1)


def prefix(directory,delta=0.):
    root=Path(directory);root.mkdir(parents=True)
    result={'geometry':{'width':32,'height':32},'target_latent_shapes':[[1,2],[1,1]],'sigmas_video':[1.,.5,0.],
            'sampler':'sample_euler','seed':2026101701,'audio_scale':1.,'video_latent_scale_factor':1.,'normalization_stage':'test',
            'noise':{'sha256':'test-identical-noise'},'captures':[]}
    for i in range(6):
        payload={'video':torch.tensor([[float(i)+delta,2.]]),'audio':torch.tensor([[float(i)]])}
        name=f'x0_step{i:03d}.pt';torch.save(payload,root/name)
        row={'file':name,'step_zero_based':i}
        for k,x in payload.items():row[k]={'shape':list(x.shape),'dtype':str(x.dtype),'bytes':x.numel()*x.element_size(),'sha256':hashlib.sha256(x.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
        result['captures'].append(row)
    file=root/'manifest.json';file.write_text(json.dumps(result));return file


class CorrespondenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def setUp(self):self.q,self.k,self.v,self.plan,self.bank=fixture()
    def run_mode(self,mode='matched_one_bin',**kwargs):
        return core.route_attention(self.q,self.k,self.v,2,self.plan,mode=mode,attention=dense,correspondence_bank=self.bank,**kwargs)

    def test_independent_probability_scatter_both_arms(self):
        for mode in c.MODES:
            for alpha in (0.,.2,1.):
                _,_,expected=explicit(self.q,self.k,self.v,self.plan,self.bank,mode,alpha)
                torch.testing.assert_close(self.run_mode(mode,alpha=alpha),expected,atol=2e-12,rtol=2e-12)

    def test_original_qk_ref_mass_nonref_and_positive_weights(self):
        for mode in c.MODES:
            a,b,_=explicit(self.q,self.k,self.v,self.plan,self.bank,mode)
            self.assertGreaterEqual(float(b.min()),0.)
            torch.testing.assert_close(a.sum(-1),b.sum(-1),atol=1e-15,rtol=1e-15)
            torch.testing.assert_close(a[:,:,:,6:18].sum(-1),b[:,:,:,6:18].sum(-1),atol=1e-15,rtol=1e-15)
            self.assertTrue(torch.equal(a[:,:,:,:6],b[:,:,:,:6]));self.assertTrue(torch.equal(a[:,:,:,18:],b[:,:,:,18:]))
        old=[x.clone() for x in (self.q,self.k,self.v)];self.run_mode()
        for a,b in zip(old,(self.q,self.k,self.v)):self.assertTrue(torch.equal(a,b))

    def test_same_accept_mask_direction_and_time_distance(self):
        fi,bi,identity=c.transport_maps(self.bank,'fixed_one_bin','cpu');fm,bm,_=c.transport_maps(self.bank,'matched_one_bin','cpu')
        self.assertTrue(torch.equal(fi//3,fm//3));self.assertTrue(torch.equal(bi//3,bm//3))
        self.assertTrue(torch.equal(fi!=identity,fm!=identity));self.assertTrue(torch.equal(bi!=identity,bm!=identity))
        self.assertLessEqual(int(((fi//3)-(identity//3)).abs().max()),1)
        self.assertLessEqual(int(((bi//3)-(identity//3)).abs().max()),1)

    def test_zero_path_bitwise_native_and_no_matching(self):
        native=self.run_mode('native')
        with mock.patch.object(core,'one_bin_attention',side_effect=AssertionError('zero path invoked operator')):
            for mode in c.MODES:self.assertTrue(torch.equal(native,self.run_mode(mode,alpha=0.)))

    def test_empty_correspondence_native(self):
        empty=torch.full_like(self.bank.forward,-1);self.bank=c.FrozenBank(empty,empty,self.bank.metadata)
        for mode in c.MODES:torch.testing.assert_close(self.run_mode(mode),self.run_mode('native'),atol=1e-12,rtol=1e-12)

    def test_track_constant_values_zero_correction(self):
        for t in range(4):self.v[:,:,6+t*3:9+t*3,3]=0.
        self.bank,_=c.build_bank(self.v[:,:,6:18],frame_rows=3,valid_bins=3,block=0)
        torch.testing.assert_close(self.run_mode(),self.run_mode('native'),atol=1e-12,rtol=1e-12)

    def test_identity_correspondence_arms_agree(self):
        identity=torch.arange(3).expand(2,3).clone();self.bank=c.FrozenBank(identity,identity,self.bank.metadata)
        self.assertTrue(torch.equal(self.run_mode('fixed_one_bin'),self.run_mode('matched_one_bin')))

    def test_padding_and_all_other_queries_bitwise_native(self):
        for mode in c.MODES:
            out=self.run_mode(mode);native=self.run_mode('native')
            self.assertTrue(torch.equal(out[:,:21],native[:,:21]));self.assertTrue(torch.equal(out[:,30:],native[:,30:]))
            f,b,identity=c.transport_maps(self.bank,mode,'cpu')
            self.assertTrue(torch.equal(f[3],identity[3]));self.assertTrue(torch.equal(b[3],identity[3]))

    def test_character_image_text_audio_and_bad_boundary_rejected(self):
        for key,value in [('query_interval_half_open',[2,11]),('reference_video_segment',[2,14]),('target_video_segment',[18,30]),('latent_interval_half_open',[1,4]),('reference_image_segments',[[7,9]])]:
            with self.subTest(key=key):
                plan=dict(self.plan);plan[key]=value
                with self.assertRaises(ValueError):core.route_attention(self.q,self.k,self.v,2,plan,mode='matched_one_bin',attention=dense,correspondence_bank=self.bank)

    def test_mixed_batch_rejected(self):
        with self.assertRaises(ValueError):core.route_attention(self.q.repeat(2,1,1,1),self.k.repeat(2,1,1,1),self.v.repeat(2,1,1,1),2,self.plan,mode='matched_one_bin',attention=dense,correspondence_bank=self.bank)

    def test_global_spatial_permutation_equivariance(self):
        order=torch.arange(33);per=torch.tensor([2,0,1])
        for start in (6,21):
            for t in range(4):order[start+t*3:start+(t+1)*3]=start+t*3+per
        for mode in c.MODES:
            before=self.run_mode(mode);q,k,v=[x[:,:,order] for x in (self.q,self.k,self.v)]
            bank,_=c.build_bank(v[:,:,6:18],frame_rows=3,valid_bins=3,block=0)
            out=core.route_attention(q,k,v,2,self.plan,mode=mode,attention=dense,correspondence_bank=bank)
            torch.testing.assert_close(out,before[:,order],atol=2e-12,rtol=2e-12)

    def test_matching_is_head_order_invariant(self):
        bank,_=c.build_bank(self.v[:,[1,0],6:18],frame_rows=3,valid_bins=3,block=0)
        self.assertTrue(torch.equal(bank.forward,self.bank.forward));self.assertTrue(torch.equal(bank.backward,self.bank.backward))

    def test_zero_ties_nonfinite_and_prefix_step(self):
        values=torch.ones_like(self.v[:,:,6:18]);bank,_=c.build_bank(values,frame_rows=3,valid_bins=3,block=0)
        self.assertTrue(bool((bank.forward==-1).all()))
        bank,_=c.build_bank(torch.zeros_like(values),frame_rows=3,valid_bins=3,block=0)
        self.assertTrue(bool((bank.forward==-1).all()))
        values[0,0,0,0]=torch.nan
        with self.assertRaises(ValueError):c.build_bank(values,frame_rows=3,valid_bins=3,block=0)
        with self.assertRaises(ValueError):c.build_bank(self.v[:,:,6:18],frame_rows=3,valid_bins=3,block=0,source_step=6)

    def test_capture_rng_grad_inputs_unchanged(self):
        rng=torch.get_rng_state().clone();original=self.v.clone();grad=torch.is_grad_enabled()
        precision=torch.get_float32_matmul_precision();tf32=torch.backends.cuda.matmul.allow_tf32
        bank,_=c.build_bank(self.v[:,:,6:18],frame_rows=3,valid_bins=3,block=0)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()));self.assertEqual(torch.is_grad_enabled(),grad);self.assertTrue(torch.equal(original,self.v))
        self.assertEqual(torch.get_float32_matmul_precision(),precision);self.assertEqual(torch.backends.cuda.matmul.allow_tf32,tf32)
        self.assertEqual(bank.metadata['numeric_context']['float32_matmul_precision'],precision)
        self.assertEqual(bank.metadata['numeric_context']['cuda_matmul_allow_tf32'],tf32)

    def test_bounded_audit_and_attention_support_mass(self):
        audit=[];self.run_mode(correspondence_diagnostics=audit,collect_support=True)
        records=audit[0]['sampled_accepted_attention']['records'];self.assertLessEqual(len(records),8*12)
        a=(self.q.double()@self.k.double().transpose(-1,-2)/math.sqrt(8)).softmax(-1)
        for row in records:
            h=row['head'];tau=row['query_latent_bin'];qi=21+tau*3+row['query_position'];chosen=[]
            for t in range(3):
                if t==tau:continue
                for s in range(3):
                    if int(self.bank.forward[t,s] if t<tau else self.bank.backward[t-1,s])>=0:chosen.append(6+t*3+s)
            wanted=float(a[0,h,qi,chosen].sum())
            self.assertAlmostEqual(row['accepted_full_attention_mass'],wanted,places=6)
        _,capture=c.build_bank(self.v[:,:,6:18],frame_rows=3,valid_bins=3,block=0)
        self.assertLessEqual(len(capture['samples']),30)

    def test_frozen_similarity_diagnostic_does_not_update_bank(self):
        digest=self.bank.manifest.copy();before=self.v.clone()
        rows=c.sample_bank_similarity(self.v[:,:,6:18],self.bank)['records']
        self.assertLessEqual(len(rows),30);self.assertGreater(len(rows),0)
        for row in rows:
            t,s,j=[row[x] for x in ('source_bin','source_position','target_position')]
            a=self.v[0,:,6+t*3+s].float();b=self.v[0,:,6+(t+1)*3+j].float()
            wanted=float(torch.nn.functional.cosine_similarity(a,b,dim=-1).mean())
            self.assertAlmostEqual(row['current_match_cosine'],wanted,places=6)
        self.assertEqual(self.bank.manifest,digest);self.assertTrue(torch.equal(before,self.v))
        empty=torch.full_like(self.bank.forward,-1);empty_bank=c.FrozenBank(empty,empty,self.bank.metadata)
        self.assertEqual(c.sample_bank_similarity(self.v[:,:,6:18],empty_bank)['records'],[])

    def test_bank_persistence_tamper_and_pair_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bank';self.bank.save(path);again=c.FrozenBank.load(path)
            self.assertEqual(again.manifest,self.bank.manifest)
            again.forward[0,0]=-1
            with self.assertRaises(ValueError):again.verify()
            data=path/'indices.npz';data.write_bytes(data.read_bytes()+b'tamper')
            with self.assertRaises(ValueError):c.FrozenBank.load(path)

    def test_frozen_cross_step_reuse_and_complete_prefix_pairing(self):
        with tempfile.TemporaryDirectory() as d:
            first=c.BankStore(Path(d)/'first',num_blocks=2,valid_bins=3)
            first.capture(0,5,self.v[:,:,6:18],3)
            with self.assertRaises(ValueError):first.get(0,6)
            first.capture(1,5,self.v[:,:,6:18],3)
            digest=first.receipt()['collection_sha256']
            for step in range(6,15):self.assertIs(first.get(0,step),first.banks[0])
            self.assertEqual(first.receipt()['collection_sha256'],digest)
            second=c.BankStore(Path(d)/'second',paired_root=Path(d)/'first',num_blocks=2,valid_bins=3)
            for b in range(2):second.capture(b,5,self.v[:,:,6:18],3)
            self.assertEqual(second.receipt()['collection_sha256'],digest)
            bad=c.BankStore(Path(d)/'bad',paired_root=Path(d)/'first',num_blocks=2,valid_bins=3)
            changed=self.v[:,:,6:18].clone();changed[0,0,0,0]+=.1
            with self.assertRaises(ValueError):bad.capture(0,5,changed,3)
            self.assertFalse((Path(d)/'bad/block_00').exists())
            with self.assertRaises(ValueError):first.capture(0,5,self.v[:,:,6:18],3)
            with self.assertRaises(ValueError):first.get(0,15)

    def test_bf16_error_bound(self):
        self.q,self.k,self.v,self.plan,self.bank=fixture(torch.bfloat16)
        for mode in c.MODES:
            _,_,expected=explicit(self.q,self.k,self.v,self.plan,self.bank,mode)
            self.assertLess(float((self.run_mode(mode).double()-expected).abs().max()),.025)

    def test_previous_modes_bitwise_unchanged(self):
        from H3TemporalRouter import r111_reference
        self.q,self.k,self.v,self.plan,self.bank=fixture(torch.float32)
        for mode in ('native','mass_preserve','hard_route','dynamic_residual','static_component','spatial_marginal'):
            old=r111_reference.route_attention(self.q,self.k,self.v,2,self.plan,mode=mode,attention=dense)
            new=core.route_attention(self.q,self.k,self.v,2,self.plan,mode=mode,attention=dense)
            self.assertTrue(torch.equal(old,new),mode)

    def test_actual_prefix_files_and_noise_signature_checked(self):
        with tempfile.TemporaryDirectory() as d:
            first=prefix(Path(d)/'first');second=prefix(Path(d)/'second')
            self.assertTrue(c.verify_common_prefix(second,first)['passed'])
            different=prefix(Path(d)/'different',delta=.5)
            with self.assertRaises(ValueError):c.verify_common_prefix(different,first)
            content=json.loads(second.read_text());content['noise']['sha256']='different';second.write_text(json.dumps(content))
            with self.assertRaises(ValueError):c.verify_common_prefix(second,first)
            content['noise']['sha256']='test-identical-noise';second.write_text(json.dumps(content))
            torch.save({'video':torch.zeros(1,2),'audio':torch.zeros(1,1)},second.parent/'x0_step005.pt')
            with self.assertRaises(ValueError):c.verify_common_prefix(second,first)

    def test_lifecycle_captures_once_and_freezes_for_nine_steps(self):
        def attention_pytorch(*args,**kwargs):raise AssertionError('native stub')
        original_route=core.route_attention
        def cpu_route(*args,**kwargs):
            kwargs['attention']=dense
            return original_route(*args,**kwargs)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);manifest=prefix(root/'prefix')
            config={'root':str(root/'banks'),'valid_bins':3,'prefix_manifest':str(manifest)}
            state=core.RouterState({},'matched_one_bin',1.,0,0,0,7,0,2,6,15,'lifecycle',str(root/'audit'),num_blocks=2,correspondence_config=config)
            with mock.patch.object(core,'route_attention',side_effect=cpu_route):
                for step in range(20):
                    state.forward_index=step;state.audit['routed_by_forward'].append(0)
                    for b in range(2):
                        out=core.TemporalAttentionOverride(state,self.plan,b)(attention_pytorch,self.q,self.k,self.v,2,skip_reshape=True,mask=None)
                        if step<6 or step>=15:self.assertTrue(torch.equal(out,self.run_mode('native')))
                    state.finish_forward()
            self.assertEqual(state.audit['native_override_calls'],40)
            self.assertEqual(state.audit['routed_calls'],18)
            self.assertEqual(len(state.audit['correspondence_bank_captures']),2)
            self.assertEqual(state.audit['routed_by_forward'],[0]*6+[2]*9+[0]*5)
            self.assertTrue(state.audit['correspondence_prefix_gate']['passed'])
            self.assertEqual(len(list((root/'banks').glob('block_*'))),2)
            json.loads(state.path.read_text())


if __name__=='__main__':unittest.main()
