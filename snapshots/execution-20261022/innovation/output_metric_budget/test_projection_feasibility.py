import unittest
import torch
from projection_feasibility import regular_hadamard,rotate_rows,streamed_weight_sketch,row_quantized_surrogate

class FeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def test_streamed_sketch_matches_full_dequant_with_cross_head_rotation(self):
        gen=torch.Generator().manual_seed(71)
        q=torch.randint(-127,128,(17,32),generator=gen,dtype=torch.int8)
        scale=torch.rand(17,generator=gen,dtype=torch.float64)*.05
        R=torch.randn(17,7,generator=gen,dtype=torch.float64)/7**.5
        W=rotate_rows(q.double()*scale[:,None],16)
        B=streamed_weight_sketch(q,scale,R,group_size=16,row_chunk=3)
        self.assertTrue(torch.allclose(B,W.T@R,atol=1e-12,rtol=1e-12))
        # Two 8-d heads per 16-d ConvRot group: splitting before inversion is wrong.
        raw=q.double().T@(scale[:,None]*R)
        self.assertFalse(torch.allclose(raw[:8],B[:8]))
        D=torch.randn(4,5,8,generator=gen,dtype=torch.float64)
        projected=torch.einsum('hpd,hdk->hpk',D,B.reshape(4,8,7))
        Gram=torch.einsum('hpk,gpk->hg',projected,projected)
        self.assertGreaterEqual(float(torch.linalg.eigvalsh(Gram).min()),-1e-10)
    def test_dynamic_input_quantization_is_not_additive(self):
        gen=torch.Generator().manual_seed(92)
        q=torch.randint(-120,121,(13,32),generator=gen,dtype=torch.int8)
        scale=torch.rand(13,generator=gen,dtype=torch.float64)*.05
        x=torch.randn(6,32,generator=gen,dtype=torch.float64)
        d=torch.randn(6,32,generator=gen,dtype=torch.float64)*.03
        f=lambda z:row_quantized_surrogate(z,q,scale,group_size=16)
        discrepancy=f(x+d)-f(x)-f(d)
        self.assertGreater(float(discrepancy.norm()),.01)
        # Every quantized row is independent of the other batch rows in this reference.
        self.assertTrue(torch.allclose(f(x[:3]),f(x)[:3],atol=1e-12,rtol=1e-12))
    def test_adaptive_sketch_nullspace_requires_independent_validation(self):
        gen=torch.Generator().manual_seed(13)
        R=torch.randn(32,8,generator=gen,dtype=torch.float64)/8**.5
        Q=torch.linalg.qr(R,mode='complete').Q
        # An optimizer may deliberately pick a direction invisible in its training sketch.
        z=Q[:,8]
        self.assertLess(float((z@R).norm()),1e-12)
        self.assertAlmostEqual(float(z.square().sum()),1.,places=12)
        holdout=torch.randn(32,64,generator=gen,dtype=torch.float64)/8
        self.assertGreater(float((z@holdout).square().sum()),.5)
    def test_rotation_orthogonality_and_bad_shape_guards(self):
        h=regular_hadamard(16);self.assertTrue(torch.allclose(h@h.T,torch.eye(16,dtype=h.dtype),atol=1e-12))
        with self.assertRaises(ValueError):regular_hadamard(8)
        with self.assertRaises(ValueError):rotate_rows(torch.ones(3,18),16)
        with self.assertRaises(ValueError):streamed_weight_sketch(torch.zeros(4,16),torch.ones(4),torch.ones(4,2),group_size=16)

if __name__=='__main__':unittest.main()
