"""Additional boundary coverage; both old/new operators are imported unchanged.

Existing package tests cover the primary FP32 equation. These tests add real
mixed-modality layout, BF16/FP16 arithmetic, mask rejection and the actual H3
Attention.forward output-projection boundary. No checkpoint or GPU is loaded.
"""
import ast
import importlib
import math
from pathlib import Path
import sys
import types
import unittest

import torch
from torch import nn

ROOT = Path(__file__).resolve().parent


def source_package(name, path):
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package
    return package


source_package('old_router', ROOT / 'sources' / 'old_router')
old = importlib.import_module('old_router.core')
layout = importlib.import_module('old_router.layout')
NEW = {}
for kind in ('feature_anchor', 'feature_gain_field', 'feature_layer_budget'):
    source_package(kind, ROOT / 'sources' / kind)
    NEW[kind] = importlib.import_module(kind + '.attention')


def dense(q, k, v):
    # Same backend for all imported operators; emulates attention output dtype
    # plus FP32 LSE, including the production BF16/FP16 output rounding.
    logits = q.float() @ k.float().transpose(-1, -2) / math.sqrt(q.shape[-1])
    return (logits.softmax(-1) @ v.float()).to(v.dtype), logits.logsumexp(-1)


def mixed_plan():
    metadata = {'text_len': 4, 'refs': [
        {'kind': 'image', 'index': 0, 'latent_t': 1, 'latent_h': 2,
         'latent_w': 4, 'frame_rows': 2, 'ref_audio_t': 0},
        {'kind': 'video_audio', 'index': 1, 'latent_t': 7, 'latent_h': 2,
         'latent_w': 6, 'frame_rows': 3, 'ref_audio_t': 2}]}
    packed = types.SimpleNamespace(signature=(4, 7, 2, 6, 3), seq_len=58,
        segments=[(0, 4, 'text'), (4, 6, 'ref_img'), (6, 10, 'ref_audio'),
                  (10, 31, 'ref_img'), (31, 37, 'audio'), (37, 58, 'video')])
    return layout.validate_layout(metadata, packed, 1, 17)


def data(dtype=torch.float32):
    torch.manual_seed(887)
    return [torch.randn(1, 3, 58, 4).to(dtype) for _ in range(3)]


def new_fixed(module, q, k, v, plan, diagnostics=None):
    return module.feature_attention(q, k, v, q.shape[1], plan,
        attention=dense, aligned_attention=old._aligned_attention,
        config=module.FeatureConfig(mode='fixed'), diagnostics=diagnostics)


class OperatorBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_original_layout_maps_video_bins_and_excludes_other_modalities(self):
        p = mixed_plan()
        self.assertEqual(p['latent_interval_half_open'], [1, 6])
        self.assertEqual(p['reference_video_segment'], [10, 31])
        self.assertEqual(p['target_video_segment'], [37, 58])
        self.assertEqual(p['key_interval_half_open'], [13, 28])
        self.assertEqual(p['query_interval_half_open'], [40, 55])
        self.assertEqual(p['reference_image_segments'], [[4, 6]])

    def test_real_old_new_equal_low_precision_and_untouched_tokens(self):
        p = mixed_plan()
        for dtype in (torch.float32, torch.bfloat16, torch.float16):
            q, k, v = data(dtype)
            expected = old.route_attention(q, k, v, 3, p, mode='mass_preserve',
                                            alpha=.25, attention=dense)
            native = dense(q, k, v)[0].transpose(1, 2).reshape(1, 58, 12)
            for name, module in NEW.items():
                with self.subTest(dtype=dtype, method=name):
                    result = new_fixed(module, q, k, v, p)
                    self.assertTrue(torch.equal(result, expected))
                    self.assertTrue(torch.equal(result[:, :40], native[:, :40]))
                    self.assertTrue(torch.equal(result[:, 55:], native[:, 55:]))

    def test_reference_mass_comes_from_full_probability_and_full_reference(self):
        p = mixed_plan(); q, k, v = data(); calls = []
        def traced(a, b, c):
            calls.append((a.clone(), b.clone(), c.clone()))
            return dense(a, b, c)
        logits = q[:, :, 40:55] @ k.transpose(-1, -2) / 2
        direct_mass = logits.softmax(-1)[:, :, :, 10:31].sum(-1).mean()
        for name, module in NEW.items():
            record = {}; calls.clear()
            module.feature_attention(q, k, v, 3, p, attention=traced,
                aligned_attention=old._aligned_attention,
                config=module.FeatureConfig(mode='fixed'), diagnostics=record)
            self.assertEqual(len(calls), 3)
            self.assertTrue(torch.equal(calls[1][1], k[:, :, 10:31]))
            self.assertTrue(torch.equal(calls[1][2], v[:, :, 10:31]))
            self.assertTrue(torch.equal(calls[1][0], q[:, :, 40:55]))
            self.assertEqual(tuple(calls[2][0].shape), (5, 3, 3, 4))
            for j in range(5):
                self.assertTrue(torch.equal(calls[2][0][j], q[0, :, 40+3*j:43+3*j]))
                self.assertTrue(torch.equal(calls[2][1][j], k[0, :, 13+3*j:16+3*j]))
            torch.testing.assert_close(record['reference_mass_mean'], direct_mass)

    def test_actual_old_new_override_rejects_mask_before_attention(self):
        q, k, v = data(); p = mixed_plan()
        def attention_pytorch(*args, **kwargs):
            raise AssertionError('mask must be rejected before evaluation')
        state = types.SimpleNamespace()
        overrides = [old.TemporalAttentionOverride(state, p, 0)]
        for module in NEW.values():
            _, block = module.make_classes(old)
            overrides.append(block.override_class(state, p, 0))
        for override in overrides:
            with self.assertRaisesRegex(ValueError, 'unmasked preshaped'):
                override(attention_pytorch, q, k, v, 3, skip_reshape=True,
                         mask=torch.zeros(58, 58))

    def test_actual_h3_forward_routes_before_unchanged_output_projection(self):
        # Execute the original class AST, not a rewritten forward. Only its
        # external kernel/ops dependencies are replaced by tiny CPU stand-ins.
        tree = ast.parse((ROOT / 'sources' / 'host41_model.py').read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'Attention')
        operators = [lambda q,k,v,p: old.route_attention(q,k,v,3,p,
                     mode='mass_preserve',alpha=.25,attention=dense)]
        operators += [lambda q,k,v,p,m=m: new_fixed(m,q,k,v,p) for m in NEW.values()]
        qkvs = []; projection_inputs = []; outputs = []
        for operator in operators:
            def optimized_attention(q,k,v,heads,**kwargs):
                self.assertIsNone(kwargs['mask']);self.assertTrue(kwargs['skip_reshape'])
                qkvs.append((q.clone(),k.clone(),v.clone()))
                return operator(q,k,v,mixed_plan())
            env = {'nn':nn, 'torch':torch, 'AttentionTensorContainer':lambda x:x,
                   'optimized_attention':optimized_attention}
            exec(compile(ast.Module(body=[cls],type_ignores=[]), 'actual_h3_attention', 'exec'),env)
            torch.manual_seed(190)
            model = env['Attention'](12,3,4,1e-6,operations=types.SimpleNamespace(Linear=nn.Linear,RMSNorm=nn.RMSNorm))
            model.out_proj.register_forward_pre_hook(lambda _,args: projection_inputs.append(args[0].clone()))
            torch.manual_seed(191);x=torch.randn(58,12)
            outputs.append(model(x))
            expected = operator(*qkvs[-1],mixed_plan()).squeeze(0)
            self.assertTrue(torch.equal(projection_inputs[-1],expected))
        for result in outputs[1:]:self.assertTrue(torch.equal(result,outputs[0]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
