import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'extensions'));sys.path.insert(0,str(ROOT/'scripts'))
from H3AttentionStateProbe.probe import read_distribution, mapping, describe, SPANS
from H3AttentionStateProbe.core import Attention, router
from H3AttentionStateProbe.source import Source
from r46_contract import identity_schema, validate_job, registry

def dense(q,k,v):
    logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1])
    return logits.softmax(-1)@v, torch.logsumexp(logits,-1)

def fixture():
    q=torch.arange(40,dtype=torch.float64).reshape(1,2,5,4)/29
    k=torch.arange(48,dtype=torch.float64).reshape(1,2,6,4)/31-0.5
    v=torch.cos(k*3)
    lse=dense(q,torch.cat((k,k+0.2),2),torch.cat((v,v),2))[1]
    return q,k,v,lse

class ProbeTests(unittest.TestCase):
    def test_group_oracle_and_output_difference(self):
        q,k,v,lse=fixture();bins=[0,1,2,0,2]; calls=[]
        def counted(*args):calls.append(args[1].shape[2]);return dense(*args)
        result=read_distribution(q,k,v,lse,counted,bins=3,frame_rows=2,query_bins=bins,lse_atol=2e-12)
        logits=q@k.transpose(-1,-2)/2
        ref_lse=torch.logsumexp(logits,-1)
        probability=(logits-lse[...,None]).exp().reshape(1,2,5,3,2).sum(-1)
        mass=probability.sum(-1)
        self.assertTrue(torch.allclose(result['reference_mass'],mass,atol=2e-12,rtol=0))
        self.assertTrue(torch.allclose(result['probabilities'],probability/mass[...,None],atol=2e-12,rtol=0))
        expected_same=torch.stack([dense(q[:,:,j:j+1],k[:,:,b*2:(b+1)*2],v[:,:,b*2:(b+1)*2])[0][:,:,0] for j,b in enumerate(bins)],2)
        self.assertTrue(torch.equal(result['same_bin_output'],expected_same))
        self.assertTrue(torch.allclose(result['reference_output'],dense(q,k,v)[0],atol=2e-12,rtol=0))
        expected=(mass[...,None]*(expected_same.float()-dense(q,k,v)[0].float())).norm(dim=-1)
        self.assertTrue(torch.allclose(result['mass_weighted_readout_difference_l2'],expected,atol=2e-12,rtol=0))
        self.assertEqual(calls,[2,2,2,6]);self.assertEqual(result['quality']['status'],'PASS')
        self.assertNotIn('bin_outputs',result)

    def test_equal_values_zero_readout_difference(self):
        q,k,_,lse=fixture();v=torch.ones_like(k)
        r=read_distribution(q,k,v,lse,dense,bins=3,frame_rows=2,query_bins=[0,1,2,0,2])
        self.assertTrue(torch.equal(r['mass_weighted_readout_difference_l2'],torch.zeros_like(lse)))

    def test_invalid_lse_never_clamped(self):
        q,k,v,_=fixture();bad=torch.full(q.shape[:-1],-100.,dtype=q.dtype)
        r=read_distribution(q,k,v,bad,dense,bins=3,frame_rows=2,query_bins=[0,1,2,0,2])
        self.assertEqual(r['quality']['status'],'UNKNOWN_NUMERICAL');self.assertGreater(r['reference_mass'].min(),1)
        bad[0,0,0]=float('nan')
        r=read_distribution(q,k,v,bad,dense,bins=3,frame_rows=2,query_bins=[0,1,2,0,2])
        self.assertFalse(r['quality']['gates']['finite'])

    def test_unknown_probe_keeps_raw_evidence_and_fail_record(self):
        from H3AttentionStateProbe.core import State
        with tempfile.TemporaryDirectory() as tmp:
            state=State.__new__(State);state.output=Path(tmp);state.probe_calls=0;state.audit={}
            state.active=True;state.completed_blocks=25;state.attention_calls=25
            state.extra_conds_calls=1;state.output_head_calls=0
            # Strided expanded fixtures allocate no full QKV: only selected copies.
            base=torch.zeros(1,1,1,128,dtype=torch.bfloat16)
            q=base.expand(1,56,87592,128)
            lse=torch.zeros(1,56,87592)
            positions=MappingTests().positions()
            plan={'seq_len':87592,'frame_rows':943,'reference_video_segment':[7910,47516],'target_video_segment':[47986,87592]}
            def invalid(q,k,v):
                return torch.zeros_like(q),torch.full(q.shape[:-1],float('nan'),dtype=torch.float32)
            with patch.object(router,'flash_attention_lse',invalid):
                with self.assertRaisesRegex(ValueError,'numerical gate'):
                    try:state.capture(q,q,q,q,lse,plan,positions)
                    except ValueError as error:state.fail(error);raise
            report=json.loads((Path(tmp)/'report.json').read_text())
            self.assertEqual(report['status'],'failed')
            self.assertEqual(report['probe']['quality']['status'],'UNKNOWN_NUMERICAL')
            self.assertTrue((Path(tmp)/'attention.pt').exists())
            self.assertTrue(torch.equal(base,torch.zeros_like(base)))

    def test_wrong_bins_rejected(self):
        q,k,v,lse=fixture()
        for ids in (None,[0,1,3,0,1],[0]):
            with self.assertRaises(ValueError):read_distribution(q,k,v,lse,dense,bins=3,frame_rows=2,query_bins=ids)

    def test_inference_all_original_bytes_and_rng(self):
        with torch.inference_mode():
            q,k,v,lse=fixture();before=[x.clone() for x in (q,k,v,lse)];rng=torch.random.get_rng_state().clone()
            read_distribution(q.clone(),k.clone(),v.clone(),lse.clone(),dense,bins=3,frame_rows=2,query_bins=[0,1,2,0,2])
            self.assertTrue(all(torch.equal(a,b) for a,b in zip((q,k,v,lse),before)))
            self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))

    def test_attention_passthrough_tensor_identity(self):
        q=torch.arange(56*7*4,dtype=torch.float64).reshape(1,56,7,4)/200;k=q/2;v=q.cos()
        originals=[x.clone() for x in (q,k,v)]
        captures=[]
        state=types.SimpleNamespace(attention_calls=0,capture=lambda *args:captures.append(args))
        def attention_pytorch():raise AssertionError('wrapper requires exact inherited Flash path')
        expected,_=dense(q,k,v)
        with patch.object(router,'flash_attention_lse',dense):
            hook=Attention(state,25,{},None)
            actual=hook(attention_pytorch,q,k,v,56,skip_reshape=True)
        self.assertTrue(torch.equal(actual,expected.transpose(1,2).reshape(1,7,224)))
        self.assertEqual(len(captures),1);self.assertEqual(state.attention_calls,1)
        self.assertTrue(all(torch.equal(a,b) for a,b in zip((q,k,v),originals)))

class MappingTests(unittest.TestCase):
    def positions(self):
        area=math.sqrt(46*82)
        h=(torch.arange(23,dtype=torch.float64)*(46/area/23)+(1-46/area)/2)*32
        w=(torch.arange(41,dtype=torch.float64)*(82/area/41)+(1-82/area)/2)*32
        hh,ww=torch.meshgrid(h,w,indexing='ij')
        spatial=torch.stack([hh.reshape(-1),ww.reshape(-1)],-1)
        times=torch.cat([torch.zeros(1,dtype=torch.float64),(torch.tensor(SPANS,dtype=torch.float64)*5/3)[:-1].cumsum(0)])
        # Match actual model's multiplication order (FRAME_RESCALE * each integer).
        times=torch.cat([torch.zeros(1,dtype=torch.float64),torch.tensor([5/3*x for x in SPANS[:-1]],dtype=torch.float64).cumsum(0)])
        pos=torch.zeros(87592,3,dtype=torch.float64)
        for a,b,origin in [(7910,47516,6961.),(47986,87592,7196.)]:
            view=pos[a:b].reshape(42,943,3);view[:,:,0]=origin+times[:,None];view[:,:,1:]=spatial
        return pos
    def test_fixed_actual_mapping_and_edge_support(self):
        plan={'seq_len':87592,'frame_rows':943,'reference_video_segment':[7910,47516],'target_video_segment':[47986,87592]}
        pos=self.positions();m=mapping(plan,pos)
        self.assertEqual(len(m['queries']),1050);self.assertEqual(m['frame_intervals'][-1],[137,140])
        self.assertEqual(m['queries'][0]['packed_index'],47986+2*41+4)
        self.assertEqual(m['queries'][25]['bin'],1)
        pos[47986+943,0]+=1
        with self.assertRaises(ValueError):mapping(plan,pos)
    def test_descriptors_sign(self):
        p=torch.zeros(1,1,3,3);p[0,0,0,1]=1;p[0,0,1,1]=1;p[0,0,2,1]=1
        m={'frame_intervals':[[0,0],[1,4],[5,8]],'queries':[{'bin':i} for i in range(3)]}
        d=describe({'probabilities':p,'reference_mass':torch.ones(1,1,3)},m)
        self.assertEqual(d['expected_reference_center_minus_query_center_frames'].tolist(),[[[2.5,0.,-4.]]])
        self.assertEqual(d['same_or_adjacent_bin_mass'].tolist(),[[[1.,1.,1.]]])

class ContractTests(unittest.TestCase):
    def test_registered_graphs(self):
        for name in registry()[1]:validate_job(name)
    def test_identity_string_and_negative_types(self):
        good={'uid':1016,'start_ticks':'2624449931','cmdline_sha256':'a'*64}
        self.assertEqual(identity_schema(good,external=True),good)
        for bad in [2624449931,True,None,'not-a-tick']:
            with self.assertRaises(ValueError):identity_schema(dict(good,start_ticks=bad),external=True)
    def test_head_contract_exact_inheritance(self):
        old=Path('/Users/researcher/DevProjects/h3-timing-one-step-fork-r13-20261016/extensions/H3OneStepForkAudit/core.py')
        if not old.exists():self.skipTest('local source inheritance check only')
        def fun(p):return ast.dump(next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='output_head_contract'),include_attributes=False)
        self.assertEqual(fun(old),fun(ROOT/'extensions/H3AttentionStateProbe/head.py'))

if __name__=='__main__':unittest.main()
