import ast
import copy
import hashlib
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'extensions'), str(ROOT/'analysis/postrun')]
from H3TemporalRouter.reference_origin import (TemporalPhaseRotation, origin_attention,
    ReferenceOriginState, ReferenceOriginBlockPatch)
from H3TemporalRouter.core import route_attention
from fixtures import fixture, MODEL, CANONICAL
from verify_reference_origin import check_reference_origin
import r132_contract as contract


def dense(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class MathTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(17)
        self.q, self.k, self.v = [torch.randn(1, 2, 22, 128, dtype=torch.float64) for _ in range(3)]
        self.plan = {'reference_video_segment':[3,9], 'target_video_segment':[14,22],
                     'query_interval_half_open':[14,22]}
        self.inv = torch.linspace(.1, .9, 16, dtype=torch.float64)
        self.rotation = TemporalPhaseRotation(self.inv, -17.5)

    def apply(self, **kw):
        return origin_attention(self.q, self.k, self.v, 2, self.plan,
                                kw.pop('rotation', self.rotation), attention=dense, **kw)

    def test_alpha_zero_is_bitwise_native(self):
        native = route_attention(self.q,self.k,self.v,2,self.plan,attention=dense)
        self.assertTrue(torch.equal(self.apply(alpha=0),native))

    def test_delta_zero_is_bitwise_native_and_uses_one_call(self):
        calls=[]
        def counted(*a):calls.append(1);return dense(*a)
        out=origin_attention(self.q,self.k,self.v,2,self.plan,TemporalPhaseRotation(self.inv,0),attention=counted)
        self.assertEqual(len(calls),1)
        self.assertTrue(torch.equal(out,route_attention(self.q,self.k,self.v,2,self.plan,attention=dense)))

    def test_mass_and_nonreference_probabilities_preserved_dense_oracle(self):
        logits=self.q@self.k.transpose(-1,-2)/math.sqrt(128)
        original=logits.softmax(-1)
        new=original.clone();qa,qb=self.plan['query_interval_half_open'];ra,rb=self.plan['reference_video_segment']
        shifted=self.rotation(self.q[:,:,qa:qb])@self.k[:,:,ra:rb].transpose(-1,-2)/math.sqrt(128)
        mass=original[:,:,qa:qb,ra:rb].sum(-1,keepdim=True)
        new[:,:,qa:qb,ra:rb]=mass*shifted.softmax(-1)
        self.assertTrue(torch.allclose(new.sum(-1),torch.ones_like(new.sum(-1)),atol=2e-15,rtol=0))
        self.assertTrue(torch.allclose(new[:,:,qa:qb,ra:rb].sum(-1,keepdim=True),mass,atol=2e-15,rtol=0))
        self.assertTrue(torch.equal(new[:,:,:,:ra],original[:,:,:,:ra]))
        self.assertTrue(torch.equal(new[:,:,:,rb:],original[:,:,:,rb:]))
        expected=(new@self.v).transpose(1,2).reshape(1,22,256)
        self.assertTrue(torch.allclose(self.apply(),expected,atol=1e-14,rtol=1e-14))
        # Group-LSE compensation is an independent logit-space oracle.
        compensated=logits.clone()
        compensated[:,:,qa:qb,ra:rb]=shifted+logits[:,:,qa:qb,ra:rb].logsumexp(-1,keepdim=True)-shifted.logsumexp(-1,keepdim=True)
        self.assertTrue(torch.allclose(compensated.softmax(-1),new,atol=2e-15,rtol=1e-14))

    def test_original_qkv_and_nonvideo_queries_bitwise_unchanged(self):
        before=[x.clone() for x in (self.q,self.k,self.v)]
        output=self.apply();native=route_attention(self.q,self.k,self.v,2,self.plan,attention=dense)
        self.assertTrue(torch.equal(output[:,:14],native[:,:14]))
        for x,y in zip((self.q,self.k,self.v),before):self.assertTrue(torch.equal(x,y))
        self.assertFalse(torch.equal(output[:,14:],native[:,14:]))

    def test_partial_video_window_leaves_other_video_rows_unchanged(self):
        self.plan['query_interval_half_open']=[16,20]
        out=self.apply();native=route_attention(self.q,self.k,self.v,2,self.plan,attention=dense)
        self.assertTrue(torch.equal(out[:,:16],native[:,:16]));self.assertTrue(torch.equal(out[:,20:],native[:,20:]))

    def test_reference_key_value_joint_permutation_invariance(self):
        expected=self.apply();perm=torch.tensor([0,1,2,8,5,7,3,6,4]+list(range(9,22)))
        actual=origin_attention(self.q,self.k[:,:,perm],self.v[:,:,perm],2,self.plan,self.rotation,attention=dense)
        self.assertTrue(torch.allclose(actual,expected,atol=1e-14,rtol=1e-14))

    def test_time_channels_only_and_rotation_composition(self):
        out=self.rotation(self.q)
        self.assertTrue(torch.equal(out[...,16:48],self.q[...,16:48]));self.assertTrue(torch.equal(out[...,64:],self.q[...,64:]))
        undone=TemporalPhaseRotation(self.inv,17.5)(out)
        self.assertTrue(torch.allclose(undone,self.q,atol=2e-15,rtol=2e-15))
        self.assertEqual(len(self.rotation.cache),1)

    def test_R17_rotation_and_operator_equivalence(self):
        source=(ROOT/'design/R17_core.py').read_text()
        nodes=[n for n in ast.parse(source).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('TemporalRotation','phase_attention')]
        env={'torch':torch,'math':math,'hashlib':hashlib,'FRAME_RESCALE':5/3,'flash_attention_lse':dense}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'bound_R17','exec'),env)
        rot=env['TemporalRotation'](self.inv,-17.5/(5/3))
        expected=env['phase_attention'](self.q,self.k,self.v,2,self.plan,rotation=rot,attention=dense)
        self.assertTrue(torch.allclose(self.apply(),expected,atol=1e-14,rtol=1e-14))

    def test_invalid_batch_scope_and_frequencies_rejected(self):
        with self.assertRaises(ValueError):origin_attention(self.q.repeat(2,1,1,1),self.k.repeat(2,1,1,1),self.v.repeat(2,1,1,1),2,self.plan,self.rotation,attention=dense)
        self.plan['query_interval_half_open']=[1,2]
        with self.assertRaises(ValueError):self.apply()
        with self.assertRaises(ValueError):TemporalPhaseRotation(torch.ones(15),1)
        with self.assertRaises(ValueError):TemporalPhaseRotation(torch.full((16,),float('nan')),1)


class LayoutTests(unittest.TestCase):
    def test_actual_canonical_delta_and_source_origin_variation(self):
        from H3TemporalRouter.alignment import aligned_positions
        for text in (7,4839,6001):
            meta,_,args=fixture()
            meta['text_len']=text;meta['context_shape'][1]=text
            layout=MODEL['PackedLayout'](text,*args[1:],refs=meta['refs'])
            original=layout.position_ids.clone();derived,details=aligned_positions(layout,meta)
            canonical=CANONICAL['PackedLayout'](text,*args[1:],refs=meta['refs'])
            self.assertEqual(details['reference_origin'],float(text))
            self.assertAlmostEqual(details['target_time_displacement'],-178.33333333333334)
            self.assertTrue(torch.equal(derived,canonical.position_ids))
            self.assertTrue(torch.equal(layout.position_ids,original))

    def test_single_video_equal_grid_rejects_image_audio_mixed_batch(self):
        from H3TemporalRouter.alignment import aligned_positions
        for change in ('image','two_refs','audio','grid','batch'):
            meta,layout,_=fixture(True)
            if change=='image':meta['refs'][0]['kind']='image'
            if change=='two_refs':meta['refs'].append(copy.deepcopy(meta['refs'][0]))
            if change=='audio':meta['refs'][0]['ref_audio_t']=1
            if change=='grid':meta['refs'][0]['latent_h']+=2
            if change=='batch':meta['context_shape'][0]=2
            with self.subTest(change=change),self.assertRaises(ValueError):aligned_positions(layout,meta)

    def test_relative_logits_match_canonical_query_rotation_in_float64(self):
        from H3TemporalRouter.alignment import aligned_positions
        meta,layout,_=fixture(True);_,details=aligned_positions(layout,meta)
        inv=torch.linspace(.01,1,16,dtype=torch.float64)
        torch.manual_seed(8);baseq=torch.randn(1,2,1,128,dtype=torch.float64);basek=torch.randn_like(baseq)
        originalq=TemporalPhaseRotation(inv,details['original_target_origin'])(baseq)
        refk=TemporalPhaseRotation(inv,details['reference_origin'])(basek)
        aux=TemporalPhaseRotation(inv,details['target_time_displacement'])(originalq)
        canonicalq=TemporalPhaseRotation(inv,details['reference_origin'])(baseq)
        self.assertTrue(torch.allclose(aux@refk.transpose(-1,-2),canonicalq@refk.transpose(-1,-2),atol=1e-13,rtol=1e-13))


if __name__=='__main__':
    torch.set_num_threads(2)
    unittest.main()
