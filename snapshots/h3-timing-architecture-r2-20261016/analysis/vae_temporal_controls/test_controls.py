"""CPU-only helpers and actual temporal-loop semantics; no VAE weights/GPU."""
import ast
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import unittest
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
import torch.nn.functional as F

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('control',HERE/'encode_controls.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ControlsTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(1)

    def test_frame_controls_preserve_exact_length_pixels_and_input(self):
        rgb=torch.arange(141*2*3*3,dtype=torch.float32).reshape(141,2,3,3);saved=rgb.clone()
        for arm in m.ARMS:
            out=m.control_pixels(rgb,arm);self.assertEqual(out.shape,rgb.shape)
            torch.testing.assert_close(out,torch.stack([rgb[i] for i in m.indices_for(arm)]),atol=0,rtol=0)
        self.assertTrue(torch.equal(rgb,saved))
        self.assertEqual(m.indices_for('delay4')[:6],[0,0,0,0,0,1])
        self.assertEqual(m.indices_for('delay8')[-1],132)
        self.assertTrue(torch.equal(m.control_pixels(rgb,'constant0')[0],m.control_pixels(rgb,'constant0')[-1]))

    def test_geometry_is_actual_nonuniform17_to5(self):
        spans,t=m.time_geometry();self.assertEqual(spans[-1],(137,140))
        self.assertEqual(t[1]-t[0],2.5);self.assertEqual(t[2]-t[1],4)
        self.assertEqual(t[6]-t[1],17)

    def test_constant_latent_is_unknown_phase_not_perfect_motion_score(self):
        z=torch.ones(1,2,42,3,4);r=m.phase_statistics(z)
        self.assertTrue(r['adjacent_bins_bitwise_equal']);self.assertTrue(r['period5_bitwise_equal'])
        self.assertIsNone(r['five_phase_explained_fraction'])
        self.assertTrue(all(v is None for v in r['signed_derivative_autocorrelation_lag_bins1to10'].values()))
        scan=m.signed_scan(m.signed_signal(z),m.signed_signal(z),(50,65));self.assertIsNone(scan['best'])

    def test_nonconstant_five_phase_is_explicitly_detected(self):
        z=(torch.arange(42)%5).float().reshape(1,1,42,1,1).expand(1,2,42,3,4)
        r=m.phase_statistics(z)
        self.assertFalse(r['adjacent_bins_bitwise_equal']);self.assertTrue(r['period5_bitwise_equal'])
        self.assertEqual(r['five_phase_explained_fraction'],1.)
        self.assertAlmostEqual(r['signed_derivative_autocorrelation_lag_bins1to10']['5'],1.)
        self.assertGreater(r['adjacent_bin_rms'],0)

    def test_actual_encode_temporal_source_has_independent_repeated_chunks(self):
        # Actual frozen loop, fake causal encoder: validates chunk/reset mechanics only.
        source=(HERE/'encode_temporal_source.txt').read_text();scope={'math':math,'torch':torch};exec(compile(ast.parse(source),'<actual encode_temporal>','exec'),scope)
        class Fake:
            clip_length=17;token_drop=3
            encode_temporal=scope['encode_temporal']
            def _normalize_pixels(self,x):return x
            def _adaptive_encode(self,x):
                kernel=torch.ones(1,3,3,1,1)
                return F.conv3d(F.pad(x,(0,0,0,0,2,0)),kernel,stride=(4,1,1))
        x=torch.ones(1,3,141,2,2);before=x.clone();z=Fake().encode_temporal(x,torch.device('cpu'))
        self.assertEqual(z.shape,(1,1,42,2,2));self.assertTrue(torch.equal(x,before))
        self.assertTrue(torch.equal(z[:,:,5:],z[:,:,:-5]));self.assertFalse(torch.equal(z[:,:,1:],z[:,:,:-1]))
        self.assertEqual(z[0,0,:5,0,0].tolist(),[3.,9.,9.,9.,9.])

    def test_tensor_sha_detects_change_without_gpu(self):
        x=torch.zeros(2,3);a=m.tensor_info(x);x[0,0]=1
        self.assertNotEqual(a['sha256'],m.tensor_info(x)['sha256'])

    def test_wrong_gpu_rejected_before_nvidia_or_core_import(self):
        with self.assertRaisesRegex(ValueError,'pinned to .41'):m.admit_gpu('GPU-other')
        self.assertFalse(torch.cuda.is_initialized())


if __name__=='__main__':unittest.main()
