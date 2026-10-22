import json
from pathlib import Path
import tempfile
import time
import unittest
import torch
from qk_motion_probe import (QKMotionProbe, adjacent_match, geometry, inverse_time_rope_copy,
                             physical_bins, selected_heads)

torch.set_num_threads(4)


def fixture(bins=32, rows=12, cols=16, heads=4, dtype=torch.float32):
    length = 5 + 2*bins*rows*cols + 2
    a,b = 5,5+bins*rows*cols
    c,d = b+2,length
    plan = dict(seq_len=length, signature=[5,bins,rows*2,cols*2,1],frame_rows=rows*cols,
                reference_video_segment=[a,b],target_video_segment=[c,d])
    pos = torch.zeros((length,3),dtype=torch.float64)
    start=0
    for t in range(bins):
        pos[a+t*rows*cols:a+(t+1)*rows*cols,0]=5+start*5/3
        pos[c+t*rows*cols:c+(t+1)*rows*cols,0]=185+start*5/3
        start += (1,4,4,4,4)[t%5]
    gen=torch.Generator().manual_seed(142)
    q=torch.randn((1,heads,length,128),generator=gen,dtype=dtype)
    k=q.clone()
    return q,k,plan,pos


class Tests(unittest.TestCase):
    def test_head_and_physical_geometry(self):
        self.assertEqual(selected_heads(32),[0,10,21,31])
        table=physical_bins(32,105,24)
        self.assertEqual(len(table),32)
        self.assertEqual(table[5]['frame_span'],[17,17])
        self.assertEqual(table[31]['frame_span'],[103,106])
        self.assertFalse(table[31]['fully_valid'])
        self.assertTrue(table[30]['fully_valid'])

    def test_translation_direction_and_reverse_consistency(self):
        g=geometry(12,16,'cpu')
        gen=torch.Generator().manual_seed(7)
        source=torch.randn(4,12,16,128,generator=gen)
        target=source.roll((1,1),(1,2))
        out=adjacent_match(source.flatten(1,2),target.flatten(1,2),g)
        good=out[:,3]>0
        self.assertTrue(good.any())
        self.assertTrue(torch.allclose(out[good,:2],torch.ones_like(out[good,:2])))
        self.assertTrue(torch.allclose(out[good,2],torch.full_like(out[good,2],2**.5)))

    def test_static_and_ambiguous(self):
        g=geometry(12,16,'cpu')
        source=torch.randn(4,192,128,generator=torch.Generator().manual_seed(2))
        static=adjacent_match(source,source,g)
        self.assertEqual(float(static[:,2].max()),0)
        self.assertGreater(float(static[:,3].max()),0)
        ambiguous=adjacent_match(torch.ones_like(source),torch.ones_like(source),g)
        self.assertEqual(float(ambiguous[:,3].max()),0)
        zeros=adjacent_match(torch.zeros_like(source),torch.zeros_like(source),g)
        self.assertTrue(torch.isfinite(zeros).all())
        self.assertEqual(float(zeros[:,3].max()),0)

    def test_time_only_inverse_and_nonmutation(self):
        x=torch.randn(4,192,128,generator=torch.Generator().manual_seed(3))
        original=x.clone(); inv=torch.linspace(.001,1,16)
        rotated=inverse_time_rope_copy(x,-7,inv)
        restored=inverse_time_rope_copy(rotated,7,inv)
        self.assertTrue(torch.equal(x,original))
        self.assertTrue(torch.allclose(x,restored,atol=5e-6,rtol=1e-6))
        self.assertTrue(torch.equal(x[...,16:48],rotated[...,16:48]))
        self.assertTrue(torch.equal(x[...,64:],rotated[...,64:]))
        self.assertNotEqual(x.data_ptr(),rotated.data_ptr())

    def test_full32_bins_small_payload_no_mutation(self):
        q,k,plan,pos=fixture()
        original=[x.clone() for x in (q,k,pos)]
        rng=torch.random.get_rng_state().clone()
        with tempfile.TemporaryDirectory() as root:
            p=QKMotionProbe(root,inv_freq=torch.linspace(.001,1,16),valid_frames=105)
            started=time.perf_counter()
            r=p.observe(q,k,plan,pos,physical_step=7,pass_kind='ordinary',block_index=25)
            elapsed=time.perf_counter()-started
            file=Path(root)/'step007_block025.json'
            self.assertLess(file.stat().st_size,100000)
            self.assertEqual(len(r['transition_start_bins']),30)
            self.assertEqual(r['physical_euler_step'],7)
            self.assertIsNone(r['intervention_decision'])
            self.assertFalse(r['tensor_bounds']['full_sequence_matrix'])
            self.assertLessEqual(r['tensor_bounds']['maximum_local_feature_elements'],4*12*25*128)
            self.assertEqual(p.observe(q,k,plan,pos,physical_step=7,pass_kind='full',block_index=25),None)
            self.assertEqual(p.observe(q,k,plan,pos,physical_step=8,pass_kind='ordinary',block_index=24),None)
            with self.assertRaisesRegex(ValueError,'duplicate'):
                p.observe(q,k,plan,pos,physical_step=7,pass_kind='ordinary',block_index=25)
            print(json.dumps({'test':'32bins','seconds':elapsed,'payload_bytes':file.stat().st_size,
                              'bounds':r['tensor_bounds']}))
        for x,y in zip((q,k,pos),original): self.assertTrue(torch.equal(x,y))
        self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))

    def test_native_attention_inputs_outputs_and_calls(self):
        q,k,plan,pos=fixture(bins=2,rows=3,cols=4,heads=1)
        v=q*.3
        expected=torch.nn.functional.scaled_dot_product_attention(q,k,v)
        calls=[]
        def native(q,k,v):
            calls.append(1)
            return torch.nn.functional.scaled_dot_product_attention(q,k,v)
        with tempfile.TemporaryDirectory() as root:
            p=QKMotionProbe(root,inv_freq=torch.linspace(.001,1,16),valid_frames=5)
            p.observe(q,k,plan,pos,physical_step=0,pass_kind='ordinary',block_index=25)
            output=native(q,k,v)
        self.assertEqual(len(calls),1)
        self.assertTrue(torch.equal(output,expected))

    def test_static_unknown_after_actual_time_inverse(self):
        q,k,plan,pos=fixture(bins=2,rows=3,cols=4,heads=1)
        inv=torch.linspace(.001,1,16)
        base=torch.randn((1,12,128),generator=torch.Generator().manual_seed(12))
        for field in ('reference_video_segment','target_video_segment'):
            a,b=plan[field]
            for t in range(2):
                start=a+t*12
                rotated=inverse_time_rope_copy(base,-float(pos[start,0]),inv)
                q[0,:,start:start+12]=rotated
                k[0,:,start:start+12]=rotated
        with tempfile.TemporaryDirectory() as root:
            p=QKMotionProbe(root,inv_freq=inv,valid_frames=5)
            result=p.observe(q,k,plan,pos,physical_step=0,pass_kind='ordinary',block_index=25)
        for name in ('inverse_time_only_reference','inverse_time_only_target'):
            self.assertEqual(result['descriptors'][name]['transition_status'],['UNKNOWN'])

    def test_identical_position_clone_across_steps_and_changed_coordinates(self):
        q,k,plan,pos=fixture(bins=32,rows=3,cols=4,heads=1)
        with tempfile.TemporaryDirectory() as root:
            p=QKMotionProbe(root,inv_freq=torch.ones(16),valid_frames=105)
            first=p.observe(q,k,plan,pos,physical_step=0,pass_kind='ordinary',block_index=25)
            second=p.observe(q,k,dict(plan),pos.clone(),physical_step=1,pass_kind='ordinary',block_index=25)
            self.assertEqual(first['descriptors'],second['descriptors'])
            self.assertEqual(second['physical_euler_step'],1)
            self.assertEqual(first['bins'],second['bins'])
            changed=pos.clone()
            changed[plan['target_video_segment'][0],1]+=1
            with self.assertRaisesRegex(ValueError,'coordinates changed'):
                p.observe(q,k,plan,changed,physical_step=2,pass_kind='ordinary',block_index=25)
            self.assertNotIn(2,p.seen)

    def test_invalid_geometry_and_zero_norm(self):
        q,k,plan,pos=fixture(bins=2,rows=3,cols=4,heads=1)
        with tempfile.TemporaryDirectory() as root:
            p=QKMotionProbe(root,inv_freq=torch.ones(16),valid_frames=5)
            pos[6,0]+=1
            with self.assertRaisesRegex(ValueError,'time positions'):
                p.observe(q,k,plan,pos,physical_step=0,pass_kind='ordinary',block_index=25)

if __name__=='__main__': unittest.main(verbosity=2)
