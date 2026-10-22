"""Run the actual pinned solver functions on a small deterministic packed AV model."""
import ast
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

import torch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r106_readout', ROOT / 'extensions/H3X0Readout/core.py')
readout = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = readout
spec.loader.exec_module(readout)


def solvers():
    path = ROOT / 'source_snapshot/actual_sampling.py'
    binding = json.loads((ROOT / 'source_snapshot/SAMPLER_SOURCE.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == binding['sha256']
    names = {'to_d', 'get_ancestral_step', 'default_noise_sampler',
             'sample_euler', 'res_multistep', 'sample_res_multistep'}
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == names
    scope = {'torch': torch, 'math': math, 'trange': lambda n, disable=None: range(n),
             'utils': NS(append_dims=lambda x, n: x[(...,) + (None,) * (n - x.ndim)])}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class Nested:
    def __init__(self, leaves):
        self.leaves = leaves

    def unbind(self):
        return self.leaves


def unpack(value, shapes):
    position = 0
    result = []
    for shape in shapes:
        count = math.prod(shape[1:])
        result.append(value[:, :, position:position + count].reshape(shape))
        position += count
    return result


def run(solver, captured, directory, *, extra_options=None, callback_mode=None, grid_override=None):
    scope = solvers()
    config = readout.CaptureConfig('test_' + solver, str(directory), 32, 32, 5, solver)
    shapes = config.shapes
    calls, callbacks, extra_noise = [], [], []
    graph = json.loads((ROOT / 'design/ORIGINAL_NATIVE_GRAPH.json').read_text())
    sigmas = torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')], dtype=torch.float32)
    if grid_override is not None:
        sigmas = grid_override(sigmas)
    initial = torch.linspace(-0.3, 0.7, sum(math.prod(s[1:]) for s in shapes), dtype=torch.float32).reshape(1, 1, -1)
    original = initial.clone()
    inner = NS(latent_shapes=shapes, audio_scale=lambda: 4., latent_format=NS(scale_factor=1.),
               model_patcher=NS(get_model_object=lambda _: NS(noise_scale=1.)),
               process_latent_out=lambda value: Nested([value.unbind()[0], value.unbind()[1] * .25]))

    class Model:
        inner_model = inner

        def __call__(self, x, sigma, **kwargs):
            prediction = .2 * x + .1 * torch.tanh(x) + .15 * torch.sin(sigma[:, None, None] * 2.)
            calls.append({'x': x.clone(), 'prediction': prediction.clone(), 'sigma': sigma.clone()})
            return prediction

    model = Model()
    sampler = NS(sampler_function=scope[solver], extra_options=extra_options or {}, inpaint_options={})

    def execute(wrap, grid, args, callback, noise, latent=None, mask=None, disable=False):
        def converted(info):
            step = info['i']
            if callback_mode == 'duplicate' and step == 1:
                step = 0
            if callback_mode == 'skip' and step == 1:
                return
            callback(step, info['denoised'], info['x'], len(grid) - 1)

        def noise_sampler(a, b):
            extra_noise.append((float(a), float(b)))
            raise AssertionError('deterministic solver requested extra noise')

        kwargs = {'noise_sampler': noise_sampler} if solver == 'sample_res_multistep' else {}
        return scope[solver](wrap, noise, grid, extra_args=args, callback=converted, disable=True, **kwargs)

    execute.class_obj = sampler

    def callback(step, prediction, state, total):
        callbacks.append((step, prediction.clone(), state.clone(), total))

    rng = torch.random.get_rng_state().clone()
    if captured:
        output = readout.PassiveRecorder(config, unpack=unpack, nested_factory=Nested)(
            execute, model, sigmas, {'seed': 2026101701}, callback, initial)
    else:
        output = execute(model, sigmas, {'seed': 2026101701}, callback, initial)
    assert torch.equal(rng, torch.random.get_rng_state())
    assert torch.equal(initial, original)
    assert not extra_noise
    return config, calls, callbacks, output


class PassiveSamplerTests(unittest.TestCase):
    def test_both_actual_solvers_recorder_preserves_all_values(self):
        for solver in readout.SOLVERS:
            with self.subTest(solver=solver), tempfile.TemporaryDirectory() as folder:
                plain = run(solver, False, Path(folder))
                recorded = run(solver, True, Path(folder))
                self.assertEqual(len(plain[1]), 20)
                self.assertEqual(len(recorded[2]), 20)
                self.assertTrue(torch.equal(plain[3], recorded[3]))
                for a, b in zip(plain[1], recorded[1]):
                    self.assertTrue(all(torch.equal(a[k], b[k]) for k in a))
                for a, b in zip(plain[2], recorded[2]):
                    self.assertEqual((a[0], a[3]), (b[0], b[3]))
                    self.assertTrue(torch.equal(a[1], b[1]) and torch.equal(a[2], b[2]))
                manifest = json.loads((Path(folder) / recorded[0].run_id / 'manifest.json').read_text())
                self.assertEqual(manifest['sampler'], solver)
                self.assertEqual(manifest['status'], 'complete')
                self.assertEqual([x['step_zero_based'] for x in manifest['raw_prefix']], [0, 1])
                for row in manifest['raw_prefix']:
                    payload = torch.load(Path(folder) / recorded[0].run_id / row['file'], weights_only=True)
                    step = row['step_zero_based']
                    for prefix, source in [('state', 'x'), ('prediction', 'prediction')]:
                        original = unpack(recorded[1][step][source], recorded[0].shapes)
                        for index, kind in enumerate(('video', 'audio')):
                            key = prefix + '_' + kind
                            self.assertTrue(torch.equal(payload[key], original[index]))
                            self.assertEqual(readout.tensor_signature(payload[key]), row['tensor_signatures'][key])

    def test_actual_solvers_share_first_two_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            euler = run('sample_euler', True, Path(folder))
            res = run('sample_res_multistep', True, Path(folder))
            for step in (0, 1):
                for key in ('x', 'prediction', 'sigma'):
                    self.assertTrue(torch.equal(euler[1][step][key], res[1][step][key]))
            self.assertFalse(torch.equal(euler[1][2]['x'], res[1][2]['x']))
            self.assertTrue(torch.isfinite(euler[3]).all() and torch.isfinite(res[3]).all())

    def test_options_rejected(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            run('sample_euler', True, Path(folder), extra_options={'s_churn': 1.})

    def test_unknown_expected_solver_rejected(self):
        with self.assertRaises(ValueError):
            readout.CaptureConfig('bad', '/tmp/r106', 32, 32, 5, 'sample_res_multistep_ancestral')

    def test_duplicate_and_missing_callback_rejected(self):
        for mode in ('duplicate', 'skip'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                run('sample_res_multistep', True, Path(folder), callback_mode=mode)

    def test_bad_sigma_count_rejected(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            run('sample_euler', True, Path(folder), grid_override=lambda grid: grid[:-1])


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
