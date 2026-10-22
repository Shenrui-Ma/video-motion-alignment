"""Independent CPU counterexamples; imports an isolated package, never GPUs."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    import torch
    torch.set_num_threads(1)
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    uniform = import_file('review_uniform', args.package/'uniform.py')
    audit = import_file('review_uniform_audit', args.package/'audit.py')
    results = {}
    for name, energies, candidate in (
        ('fp64_denominator_overflow', [1., 1e308, 1e308, 1.], [.25, .1, .4, .25]),
        ('fp64_many_bins_overflow', [1e308]*40, [.25]*40),
    ):
        mask = torch.ones(len(energies), dtype=torch.bool)
        mask[0] = mask[-1] = False
        try:
            uniform.uniform_energy_alpha(torch.tensor(candidate, dtype=torch.float64),
                                         torch.tensor(energies, dtype=torch.float64), mask)
        except (ValueError, FloatingPointError) as exc:
            results[name] = {'rejected': True, 'reason': str(exc)}
        else:
            raise AssertionError('overflow accepted: ' + name)
    for name, energies, mask in (
        ('fp32_large_sum_safe_fp64', [1e38]*8, [False]+[True]*6+[False]),
        ('no_modifiable_bins', [1.]*8, [False]*8),
        ('zero_energy', [0.]*8, [False]+[True]*6+[False]),
        ('fp32_subnormal_fallback', [1e-40]*8, [False]+[True]*6+[False]),
    ):
        a = torch.tensor([.25,.1,.2,.3,.4,.1,.2,.25])
        m = torch.tensor(mask)
        a[~m] = .25
        out, proof = uniform.uniform_energy_alpha(a, torch.tensor(energies), m)
        assert torch.isfinite(out).all()
        assert torch.equal(out[~m], a[~m])
        if name == 'fp32_large_sum_safe_fp64':
            assert math.isfinite(float(proof['modifiable_energy']))
            assert abs(float(proof['energy_relative_error'])) < 3e-7
        else:
            assert torch.equal(out, torch.full_like(out,.25))
        results[name] = {'passed': True, 'applied': out.tolist()}
    raw = args.fixture.read_bytes()
    doc = json.loads(raw)
    proof = audit.check_uniform(doc)
    row = next(r for f in doc['feature_forward_summaries'] for r in f['layers']
               if max(r['candidate_alpha'])-min(r['candidate_alpha'])>.01)
    bad = copy.deepcopy(row)
    candidate = [.25]*len(bad['alpha'])
    # Forge candidate/control/output consistently and recompute every energy
    # field, while preserving independently recorded QP evidence/anchors.
    bad['alpha'] = candidate[:]
    bad['candidate_alpha'] = candidate[:]
    bad['control']['alpha'] = candidate[:]
    u = bad['uniform_energy']
    u['candidate_alpha'] = candidate[:]
    u['applied_alpha'] = candidate[:]
    u['uniform_alpha'] = .25
    e = bad['bin_energy']
    m = u['modifiable_mask']
    total = sum(x*.25**2 for x in e)
    selected = sum(x*.25**2 for x, selected in zip(e,m) if selected)
    u['candidate_modifiable_energy'] = selected
    u['applied_modifiable_energy'] = selected
    u['candidate_total_energy'] = total
    u['applied_total_energy'] = total
    u['energy_error'] = u['energy_relative_error'] = 0.
    bad['applied_energy'] = total
    try:
        audit.check_uniform_layer(bad)
    except ValueError as exc:
        results['coherent_forged_candidate_output_energies'] = {'rejected': True, 'reason': str(exc)}
    else:
        raise AssertionError('coherent false candidate accepted')
    bad = copy.deepcopy(row)
    bad['uniform_energy']['applied_modifiable_energy'] *= 1.1
    try:
        audit.check_uniform_layer(bad)
    except ValueError as exc:
        results['incorrect_applied_modifiable_energy'] = {'rejected': True, 'reason': str(exc)}
    else:
        raise AssertionError('unused false energy diagnostic accepted')
    assert not torch.cuda.is_initialized()
    print(json.dumps({'results': results, 'full_wrapper_audit': proof,
        'fixture_sha256': hashlib.sha256(raw).hexdigest(), 'cuda_initialized': False,
        'source_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in args.package.glob('*.py')}}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
