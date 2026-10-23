"""Independent CPU-only contract tests using captured production KSAMPLER AST."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


def actual_classes():
    source = json.loads(Path(__file__).with_name('HOST41_GUIDER_SOURCE.json').read_text())
    nodes = {n['name']: n['source'] for f in source['files'] for n in f['nodes']}
    class Sampler:
        def max_denoise(self, model, sigmas):
            return sigmas[0] == 1
    ns = {'Sampler': Sampler, 'detail': lambda *args: None}
    for name in ('KSamplerX0Inpaint', 'KSAMPLER'):
        exec(compile(ast.parse(nodes[name]), '<actual '+name+'>', 'exec'), ns)
    return ns['KSAMPLER'], ns['KSamplerX0Inpaint']


class Contract(unittest.TestCase):
    def setUp(self):
        self.KSAMPLER, _ = actual_classes()
        self.flow = SimpleNamespace(noise_scaling=lambda s,n,x,m:n,
                                    inverse_noise_scaling=lambda s,x:x)
        self.model = SimpleNamespace(inner_model=SimpleNamespace(model_sampling=self.flow))

    def test_absent_outer_callback_is_still_wrapped(self):
        seen = {}
        def finite(model_k, x, sigmas, **kwargs):
            seen.update(kwargs)
            return x
        out = self.KSAMPLER(finite).sample(self.model, [1, .5, 0], {}, None, 'noise', 'latent')
        self.assertEqual(out, 'noise')
        self.assertTrue(callable(seen['callback']))
        self.assertIsNone(seen['extra_args']['denoise_mask'])

    def test_original_rejection_blocks_actual_wrapper(self):
        def reject(model_k, x, sigmas, callback=None, **kwargs):
            if callback is not None:
                raise ValueError('no preview callback')
        with self.assertRaisesRegex(ValueError, 'no preview callback'):
            self.KSAMPLER(reject).sample(self.model, [1, .5, 0], {}, None, 'noise', 'latent')

    def test_finite_sampler_does_not_need_to_invoke_callback(self):
        calls = []
        def callback(*args):
            calls.append(args)
        self.KSAMPLER(lambda model_k,x,sigmas,**kwargs:x).sample(
            self.model, [1,.5,0], {}, callback, 'noise', 'latent')
        self.assertEqual(calls, [])

    def test_same_full_grid_and_terminal_inverse_are_preserved(self):
        seen = {}
        grid = [1,.5,0]
        def finite(model_k,x,sigmas,**kwargs):
            self.assertIs(sigmas, grid)
            self.assertIs(model_k.sigmas, grid)
            self.assertIs(model_k.inner_model, self.model)
            return 'raw_x0'
        self.flow.inverse_noise_scaling=lambda s,x:seen.update(sigma=s, value=x) or x
        self.KSAMPLER(finite).sample(self.model, grid, {}, None, 'noise', 'latent')
        self.assertEqual(seen, {'sigma':0,'value':'raw_x0'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
