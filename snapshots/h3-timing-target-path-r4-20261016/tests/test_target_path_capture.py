import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions'))
from H3TemporalRouter.core import route_attention, _aligned_attention
from H3TemporalRouter import core
from H3TemporalRouter.target_path_features import candidate_readout, save_target_path_features


def attention(q, k, v):
    scores = q.float() @ k.float().transpose(-1, -2) / q.shape[-1] ** .5
    return (scores.softmax(-1) @ v.float()).to(q.dtype), scores.logsumexp(-1)


def fixture():
    torch.manual_seed(119)
    tensors = [torch.randn(1, 4, 62, 8, dtype=torch.bfloat16) for _ in range(3)]
    plan = {'seq_len': 62, 'signature': [2, 5, 4, 6, 0], 'frame_rows': 6,
            'latent_interval_half_open': [1, 3], 'reference_video_segment': [2, 32],
            'target_video_segment': [32, 62], 'query_interval_half_open': [38, 50]}
    return tensors, plan


class CaptureTests(unittest.TestCase):
    def test_hook_native_only_three_registered_points(self):
        (q, k, v), p = fixture()
        sentinel = torch.zeros(1, 62, 32, dtype=torch.bfloat16)
        def attention_pytorch(*args, **kwargs):
            raise AssertionError('unexpected native entry')
        for mode in ['native', 'mass_preserve', 'dynamic_residual']:
            with tempfile.TemporaryDirectory() as d:
                state = core.RouterState({}, mode, 1., 0, 0, 50, 65, 0, 50, 6, 15, 'test', str(Path(d) / 'router'))
                state.audit['sample_sigmas'] = torch.linspace(1, 0, 21).tolist()
                def routed(*args, **kwargs):
                    if kwargs.get('passive_capture') is not None:
                        kwargs['passive_capture'](q, torch.zeros(1, 4, 62), q, k, v)
                    return sentinel
                with mock.patch.object(core, 'save_target_path_features', return_value={'fake': True}) as saved, \
                     mock.patch.object(core, 'component_probe', return_value={}), \
                     mock.patch.object(core, 'temporal_readout', return_value={}), \
                     mock.patch.object(core, 'route_attention', side_effect=routed):
                    for step in range(20):
                        state.forward_index = step
                        state.audit['routed_by_forward'].append(0)
                        for block in range(50):
                            result = core.TemporalAttentionOverride(state, p, block)(attention_pytorch, q, k, v, 4, skip_reshape=True, mask=None)
                            self.assertIs(result, sentinel)
                    self.assertEqual(saved.call_count, 3 if mode == 'native' else 0)
                    if mode == 'native':
                        self.assertEqual([c.kwargs['step'] for c in saved.call_args_list], [6, 10, 14])
                        self.assertEqual([c.kwargs['block'] for c in saved.call_args_list], [25, 25, 25])
                        self.assertEqual(len(state.audit['target_path_feature_captures']), 3)

    def test_candidate_is_actual_formal_full_branch(self):
        (q, k, v), p = fixture()
        full, lse = attention(q, k, v)
        target, c, mass = candidate_readout(full, lse, q, k, v, p, selected_heads=(0, 3),
                                           attention=attention, aligned_attention=_aligned_attention)
        actual = route_attention(q, k, v, 4, p, mode='mass_preserve', attention=attention)
        actual = actual.reshape(1, 62, 4, 8).permute(0, 2, 1, 3)
        self.assertTrue(torch.equal(c, actual[:, (0, 3), 38:50]))
        self.assertTrue(torch.equal(target, full[:, (0, 3), 32:62]))
        self.assertTrue(bool(((mass >= 0) & (mass <= 1)).all()))

    def test_passive_route_inputs_rng_and_output_unchanged(self):
        tensors, p = fixture()
        saved = [t.clone() for t in tensors]
        before_rng = torch.get_rng_state().clone()
        native = route_attention(*tensors, 4, p, attention=attention)
        seen = []
        def capture(full, lse, q, k, v):
            seen.append(candidate_readout(full, lse, q, k, v, p, selected_heads=(0, 3),
                                          attention=attention, aligned_attention=_aligned_attention))
        captured = route_attention(*tensors, 4, p, attention=attention, passive_capture=capture)
        self.assertEqual(len(seen), 1)
        self.assertTrue(torch.equal(native, captured))
        self.assertTrue(torch.equal(before_rng, torch.get_rng_state()))
        for a, b in zip(tensors, saved):
            self.assertTrue(torch.equal(a, b))

    def test_save_layout_hash_and_overwrite_guard(self):
        (q, k, v), p = fixture()
        full, lse = attention(q, k, v)
        with tempfile.TemporaryDirectory() as d:
            kwargs = dict(output_dir=d, run_id='test', step=6, block=25, sigma_video=.9,
                          attention=attention, aligned_attention=_aligned_attention,
                          selected_heads=(0, 3), expected_grid=(5, 2, 3))
            record = save_target_path_features(full, lse, q, k, v, p, **kwargs)
            saved = torch.load(record['path'], map_location='cpu', weights_only=True)
            self.assertEqual(tuple(saved['target'].shape), (1, 2, 5, 2, 3, 8))
            self.assertEqual(tuple(saved['candidate'].shape), (1, 2, 2, 2, 3, 8))
            self.assertTrue(torch.equal(saved['target'].reshape(1, 2, 30, 8), full[:, (0, 3), 32:62]))
            self.assertIn('not correct-action ground truth', saved['metadata']['candidate_scope'])
            self.assertEqual(len(record['sha256']), 64)
            with self.assertRaises(FileExistsError):
                save_target_path_features(full, lse, q, k, v, p, **kwargs)

    def test_invalid_geometry_and_heads_rejected(self):
        (q, k, v), p = fixture()
        full, lse = attention(q, k, v)
        for heads in [(0, 0), (4,), ()]:
            with self.assertRaises(ValueError):
                candidate_readout(full, lse, q, k, v, p, selected_heads=heads,
                                  attention=attention, aligned_attention=_aligned_attention)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
