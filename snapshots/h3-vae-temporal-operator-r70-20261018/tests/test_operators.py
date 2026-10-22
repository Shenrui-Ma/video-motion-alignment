import ast
import sys
import unittest
from pathlib import Path
import numpy as np
import torch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import operators as op


class OperatorTest(unittest.TestCase):
    def test_identity_exact_rgb_and_latent(self):
        value = torch.randn(158, 2, 3, dtype=torch.float32)
        self.assertTrue(torch.equal(value, op.interpolate(value, np.arange(158), 0)))
        z = torch.randn(1, 24, 47, 2, 2)
        coords = op.coordinates(np.arange(158))
        self.assertTrue(torch.equal(z, op.interpolate(z, coords['latent_positions'], 2)))

    def test_shift_direction_and_boundary(self):
        phi = op.make_maps(np.arange(49))['shift3']
        value = torch.arange(158, dtype=torch.float32)[:, None]
        warped = op.interpolate(value, phi, 0)
        self.assertEqual(warped[0].item(), 3)
        self.assertEqual(warped[-1].item(), 157)
        coords = op.coordinates(phi)
        self.assertEqual(sum(coords['rgb_full_domain_valid']), 155)
        self.assertEqual(sum(coords['observed147_valid']), 144)
        self.assertFalse(coords['latent_center_domain_valid'][-1])

    def test_dtw_time_units_and_identity_tail(self):
        mapping = np.arange(49, dtype=float)
        mapping[1:10] += 1
        phi = op.make_maps(mapping)['offline_mapping']
        self.assertEqual(phi[3], 6)
        self.assertEqual(phi[1], 2)
        np.testing.assert_array_equal(phi[144:], np.arange(144, 158))
        self.assertTrue(np.all(np.diff(phi) >= 0))

    def test_nominal_bins_from_actual_source(self):
        start, end, center = op.bins()
        np.testing.assert_array_equal(center[:6], [0, 2.5, 6.5, 10.5, 14.5, 17])
        self.assertEqual(end[-1], 157)
        self.assertEqual(center[-1], 155.5)
        model = ast.parse((ROOT / 'audit/source_code/h3_model.py').read_text())
        assignments = {target.id: ast.literal_eval(node.value) for node in model.body
                       if isinstance(node, ast.Assign) for target in node.targets
                       if isinstance(target, ast.Name) and target.id == 'FRAME_PER_TOKEN'}
        self.assertEqual(assignments['FRAME_PER_TOKEN'], (1, 4, 4, 4, 4))
        funcs = [node for node in model.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('_video_t_spans', '_video_t_grid')]
        env = {'torch': torch, 'FRAME_PER_TOKEN': assignments['FRAME_PER_TOKEN'], 'FRAME_RESCALE': 5 / 3}
        exec(compile(ast.Module(body=funcs, type_ignores=[]), '<actual_h3_model_coordinates>', 'exec'), env)
        grid = env['_video_t_grid'](47, 0).numpy() / (5 / 3)
        np.testing.assert_allclose(grid, start, atol=1e-12, rtol=0)
        vae = ast.parse((ROOT / 'audit/source_code/h3_vae.py').read_text())
        cls = next(x for x in vae.body if isinstance(x, ast.ClassDef) and x.name == 'MiniMaxH3VideoVAE')
        init = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '__init__')
        defaults = dict(zip([x.arg for x in init.args.args][-len(init.args.defaults):], init.args.defaults))
        self.assertEqual(ast.literal_eval(defaults['clip_length']), 17)
        self.assertEqual(ast.literal_eval(defaults['token_drop']), 3)
        self.assertEqual(np.prod(ast.literal_eval(defaults['time_down'])), 4)

    def test_nonuniform_coordinate_linear_ramp(self):
        _, _, centers = op.bins()
        z = torch.tensor(centers, dtype=torch.float32)[None, None, :, None, None]
        coords = op.coordinates(np.arange(158) + 3)
        result = op.interpolate(z, coords['latent_positions'], 2).flatten().numpy()
        valid = np.array(coords['latent_center_domain_valid'])
        np.testing.assert_allclose(result[valid], centers[valid] + 3, atol=2e-5, rtol=0)

    def test_dtype_and_channel_normalization_ownership(self):
        with self.assertRaises(AssertionError):
            op.interpolate(torch.zeros(158, dtype=torch.float16), np.arange(158), 0)
        z = torch.randn(1, 24, 47, 2, 2)
        before = z.clone()
        phi = op.coordinates(np.arange(158) + 3)['latent_positions']
        warped = op.interpolate(z, phi, 2)
        self.assertTrue(torch.equal(z, before))
        mean = torch.arange(24).view(1, 24, 1, 1, 1).float()
        std = mean / 10 + 1
        inverse_after = warped * std + mean
        inverse_before = op.interpolate(z * std + mean, phi, 2)
        torch.testing.assert_close(inverse_after, inverse_before, atol=1e-5, rtol=1e-5)


if __name__ == '__main__':
    unittest.main()
