"""CPU-only audit of copied actual Comfy functions, without importing Comfy."""
import argparse
import ast
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
from types import SimpleNamespace as NS

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch

HERE = Path(__file__).resolve().parent
SRC = HERE / 'sources'


def load_definitions(filename, names, scope):
    tree = ast.parse((SRC / filename).read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SRC / filename), 'exec'), scope)


def source_literal(filename, class_name, attribute):
    cls = next(n for n in ast.parse((SRC / filename).read_text()).body
               if isinstance(n, ast.ClassDef) and n.name == class_name)
    stmt = next(n for n in cls.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == attribute for t in n.targets))
    return ast.literal_eval(stmt.value)


def sigsha(t):
    return hashlib.sha256(t.contiguous().numpy().tobytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tag', required=True)
    args = p.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    assert not torch.cuda.is_initialized()
    bindings = json.loads((HERE / 'SOURCE_BINDINGS.json').read_text())
    for row in bindings['sources']:
        assert hashlib.sha256((SRC / row['file']).read_bytes()).hexdigest() == row['sha256']

    ns = {'torch': torch, 'math': math, 're': re,
          'io': NS(ComfyNode=object, NodeOutput=lambda *a: a)}
    load_definitions('model_sampling.py', ['reshape_sigma', 'time_snr_shift',
                     'CONST', 'ModelSamplingDiscreteFlow', 'ModelSamplingAV'], ns)
    load_definitions('samplers.py', ['simple_scheduler'], ns)
    load_definitions('nodes_custom_sampler.py', ['ManualSigmas', 'BasicScheduler'], ns)
    load_definitions('minimax_model.py', ['time_shift_sigma'], ns)
    settings = source_literal('supported_models.py', 'MiniMaxH3', 'sampling_settings')
    assert settings == {'shift': 12.0, 'audio_shift': 3.0}
    ModelSampling = type('ExtractedModelSampling', (ns['ModelSamplingAV'], ns['CONST']), {})
    default = ModelSampling(NS(sampling_settings=settings))
    patched = ModelSampling(NS(sampling_settings=settings))
    patched.set_parameters(shift=12.0, audio_shift=3.0)
    assert torch.equal(default.sigmas, patched.sigmas)
    assert default.audio_scale == patched.audio_scale == 4.0
    assert default.noise_scale == patched.noise_scale == 1.0

    # BasicScheduler delegates the selected "simple" path to this exact function.
    def calculate_sigmas(sampling, name, steps):
        assert name == 'simple'
        return ns['simple_scheduler'](sampling, steps)
    ns['comfy'] = NS(samplers=NS(calculate_sigmas=calculate_sigmas))
    official = json.loads((SRC / 'official_template.json').read_text())
    nodes = {n['id']: n for n in official['nodes']}
    assert nodes[123]['widgets_values'] == ['res_multistep']
    assert nodes[124]['widgets_values'] == ['simple', 20, 1]
    assert nodes[126]['type'] == 'BasicGuider'
    assert nodes[146]['widgets_values'] == [False]
    simple = ns['BasicScheduler'].execute(NS(get_model_object=lambda _: default), 'simple', 20, 1.0)[0]
    graph = json.loads((SRC / 'r87_graph.json').read_text())
    other = json.loads((SRC / 'r85_graph.json').read_text())
    assert graph['8']['inputs']['sampler_name'] == other['8']['inputs']['sampler_name'] == 'euler'
    assert graph['9'] == other['9']
    manual = ns['ManualSigmas'].execute(graph['9']['inputs']['sigmas'])[0]
    assert len(manual) == len(simple) == 21
    assert manual.dtype == simple.dtype == torch.float32
    differences = torch.abs(manual - simple)
    ulps = torch.abs(manual.view(torch.int32).to(torch.int64) - simple.view(torch.int32).to(torch.int64))
    # Use the actual model's float32 multiplier/division followed by its shift function.
    model_sigma_manual = (default.timestep(manual[:20]) / 1000.0).float().clamp(min=1e-6)
    model_sigma_simple = (default.timestep(simple[:20]) / 1000.0).float().clamp(min=1e-6)
    audio_manual = ns['time_shift_sigma'](model_sigma_manual, 12.0, 3.0)
    audio_simple = ns['time_shift_sigma'](model_sigma_simple, 12.0, 3.0)
    rows = []
    for i in range(21):
        rows.append({'step_zero_based': i, 'is_model_call': i < 20,
                     'manual_sigma_video': float(manual[i]), 'simple_sigma_video': float(simple[i]),
                     'abs_difference': float(differences[i]), 'float32_ulp_difference': int(ulps[i]),
                     'manual_model_sigma_video': float(model_sigma_manual[i]) if i < 20 else None,
                     'simple_model_sigma_video': float(model_sigma_simple[i]) if i < 20 else None,
                     'manual_model_sigma_audio': float(audio_manual[i]) if i < 20 else None,
                     'simple_model_sigma_audio': float(audio_simple[i]) if i < 20 else None})

    # Execute the actual sampler functions on a tiny deterministic toy denoiser.
    # This checks update/callback/forward behavior only, not any H3 quality claim.
    ns['trange'] = lambda n, disable=None: range(n)
    ns['utils'] = NS(append_dims=lambda x, n: x[(...,) + (None,) * (n - x.ndim)])
    load_definitions('sampling.py', ['to_d', 'get_ancestral_step', 'default_noise_sampler',
                     'sample_euler', 'res_multistep', 'sample_res_multistep'], ns)
    def run(name):
        calls, callbacks, noise_calls = [], [], []
        class Toy:
            inner_model = NS(model_patcher=NS(get_model_object=lambda _: default))
            def __call__(self, x, sigma, **kwargs):
                denoised = 0.2 * x + 0.1 * torch.tanh(x) + 0.15 * torch.sin(sigma[:, None] * 2.0)
                calls.append({'sigma': sigma.clone(), 'x': x.clone(), 'denoised': denoised.clone()})
                return denoised
        def callback(info):
            callbacks.append({k: v.clone() if isinstance(v, torch.Tensor) else v for k, v in info.items()})
        def noise_sampler(sigma, next_sigma):
            noise_calls.append((float(sigma), float(next_sigma)))
            raise AssertionError('eta=0 must not request additional noise')
        kw = {'noise_sampler': noise_sampler} if name == 'sample_res_multistep' else {}
        rng_before = torch.random.get_rng_state().clone()
        output = ns[name](Toy(), torch.tensor([[0.7, -0.25]], dtype=torch.float32),
                          manual.clone(), extra_args={'seed': 2026101701}, callback=callback, disable=True, **kw)
        assert torch.equal(rng_before, torch.random.get_rng_state())
        assert len(calls) == len(callbacks) == 20
        assert [c['i'] for c in callbacks] == list(range(20))
        assert all(torch.equal(c['sigma'], manual[i:i+1]) for i, c in enumerate(calls))
        assert all(torch.equal(c['sigma'], manual[i]) and torch.equal(c['sigma_hat'], manual[i])
                   for i, c in enumerate(callbacks))
        assert not noise_calls and torch.isfinite(output).all()
        return calls, callbacks, output
    euler, _, euler_output = run('sample_euler')
    res, _, res_output = run('sample_res_multistep')
    exact_x = [torch.equal(a['x'], b['x']) for a, b in zip(euler, res)]
    exact_d = [torch.equal(a['denoised'], b['denoised']) for a, b in zip(euler, res)]
    assert exact_x[:2] == exact_d[:2] == [True, True]
    assert exact_x[2] is False and exact_d[2] is False
    # Coefficients describe eta=0's 18 multistep updates in real arithmetic.
    coefficients = []
    for i in range(1, 19):
        sv, sn, sp = [float(manual[j]) for j in (i, i+1, i-1)]
        h = math.log(sv/sn)
        c2 = math.log(sv/sp)/h
        phi1 = math.expm1(-h)/(-h)
        phi2 = (phi1-1)/(-h)
        coefficients.append({'step_zero_based': i, 'x_weight': math.exp(-h),
                             'euler_current_x0_weight': 1-sn/sv,
                             'res_current_x0_weight': h*(phi1-phi2/c2),
                             'res_previous_x0_weight': h*phi2/c2})
    result = {
        'schema': 'native-sampler-protocol-cpu-v1', 'tag': args.tag,
        'torch_version': torch.__version__, 'cuda_initialized': torch.cuda.is_initialized(),
        'official_template': {'sampler': 'res_multistep', 'scheduler': 'simple', 'steps': 20,
                              'denoise': 1, 'turbo_switch': False, 'guider': 'BasicGuider'},
        'model_sampling': {'default_settings': settings, 'explicit_12_3_schedule_exact_equal': True,
                           'audio_scale': default.audio_scale, 'noise_scale': default.noise_scale,
                           'video_sigma_multiplier': default.multiplier},
        'grid': {'manual_sha256': sigsha(manual), 'simple_sha256': sigsha(simple),
                 'exact_equal': torch.equal(manual, simple), 'max_abs_difference': float(differences.max()),
                 'max_float32_ulp_difference': int(ulps.max()),
                 'different_indices': torch.nonzero(manual != simple).flatten().tolist(),
                 'manual_model_roundtrip_different_indices': torch.nonzero(manual[:20] != model_sigma_manual).flatten().tolist(),
                 'max_audio_sigma_difference': float(torch.abs(audio_manual-audio_simple).max()),
                 'rows': rows},
        'synthetic_execution': {'scope': 'actual functions, deterministic toy denoiser; no H3 weights or generated video',
            'manual_grid_identical_for_both_solvers': True, 'forward_calls_each': 20,
            'callbacks_each': 20, 'extra_noise_calls_each': 0, 'global_rng_unchanged': True,
            'same_actual_sigma_at_each_model_call': True,
            'input_state_exact_equal_by_step': exact_x, 'denoised_exact_equal_by_step': exact_d,
            'euler_output': euler_output.tolist(), 'res_multistep_output': res_output.tolist(),
            'final_max_abs_difference': float(torch.abs(euler_output-res_output).max()),
            'multistep_coefficients_real_arithmetic': coefficients},
        'passed': True,
    }
    assert not result['cuda_initialized']
    (HERE / f'CPU_{args.tag}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    with (HERE / f'SIGMAS_{args.tag}.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'tag':args.tag, 'passed':True, 'torch':torch.__version__, 'cuda_initialized':False,
                      'max_sigma_difference':float(differences.max()), 'max_ulp':int(ulps.max()),
                      'different_indices':result['grid']['different_indices'],
                      'solver_first_divergent_model_call_zero_based':2,
                      'index6_coefficients':coefficients[5]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
