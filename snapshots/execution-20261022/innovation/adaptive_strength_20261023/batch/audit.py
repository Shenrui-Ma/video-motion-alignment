"""Read-only, standard-library validation of completed H3 experiment audits.

No model loading, queue access, inference, or synthetic evidence generation.
Raise AuditError for malformed/incomplete evidence; return JSON-safe summaries.
"""
import argparse
import json
import math
from pathlib import Path
import sys


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def number(value, label, *, minimum=None, maximum=None):
    require(type(value) in (int, float) and math.isfinite(value), label + ': finite number required')
    require(minimum is None or value >= minimum, label + ': below minimum')
    require(maximum is None or value <= maximum, label + ': above maximum')
    return float(value)


def integer(value, label, *, minimum=0):
    require(type(value) is int and value >= minimum, label + ': integer required')
    return value


def close(actual, expected, label, *, rtol=2e-5, atol=1e-8):
    actual, expected = number(actual, label), number(expected, label)
    require(abs(actual-expected) <= atol + rtol*abs(expected),
            f'{label}: {actual} != {expected}')


def vector(value, label, *, length=None, minimum=None, maximum=None):
    require(isinstance(value, list) and (length is None or len(value) == length), label + ': bad vector')
    return [number(x, f'{label}[{i}]', minimum=minimum, maximum=maximum) for i, x in enumerate(value)]


def interval(value, limit, label):
    require(isinstance(value, list) and len(value) == 2, label + ': half-open interval required')
    a, b = [integer(x, label) for x in value]
    require(0 <= a < b <= limit, label + ': out of range')
    return a, b


def stats(values):
    return {'mean': sum(values)/len(values), 'min': min(values), 'max': max(values),
            'count': len(values)} if values else {'mean': None, 'min': None, 'max': None, 'count': 0}


def boundary_exclusion(value):
    """A flag or an exact excluded-probe count, never a success requirement."""
    require(type(value) is bool or (type(value) is int and value >= 0),
            'boundary_probes_excluded must be boolean or a nonnegative count')
    return value


def _common(audit, expected_steps, blocks):
    integer(expected_steps, 'expected_steps', minimum=1)
    integer(blocks, 'blocks', minimum=1)
    require(isinstance(audit, dict), 'audit must be a JSON object')
    require(audit.get('status') in ('sampling', 'completed', 'complete'), 'audit failed or not sampled')
    require(not audit.get('error'), 'audit contains error')
    total = expected_steps*blocks
    for key, expected in (('completed_forward_calls', expected_steps), ('started_calls', total),
                          ('completed_calls', total), ('native_override_calls', total)):
        require(integer(audit.get(key), key) == expected, key + ': incomplete count')
    require(audit.get('calls_by_forward') == [blocks]*expected_steps, 'calls_by_forward mismatch')
    require(audit.get('calls_by_block') == [expected_steps]*blocks, 'calls_by_block mismatch')
    if 'expected_sampling_steps' in audit:
        require(audit['expected_sampling_steps'] == expected_steps, 'sampling step count mismatch')
    if 'last_completed_block' in audit:
        require(audit['last_completed_block'] == blocks-1, 'last_completed_block mismatch')
    if 'last_completed_forward_index' in audit:
        require(audit['last_completed_forward_index'] == expected_steps-1, 'last forward mismatch')
    steps = interval(audit.get('step_interval_half_open'), expected_steps, 'step interval')
    layers = interval(audit.get('block_interval_half_open'), blocks, 'block interval')
    summaries = audit.get('forward_summaries')
    require(isinstance(summaries, list) and len(summaries) == expected_steps, 'missing forward summaries')
    for i, row in enumerate(summaries):
        require(isinstance(row, dict), f'forward summary {i}: object required')
        require(row.get('forward_index') == i and row.get('completed_blocks') == blocks,
                f'forward summary {i}: incomplete or unordered')
    return steps, layers


def _routed_counts(audit, pairs, expected_steps, blocks):
    by_step = [sum(s == i for s, _ in pairs) for i in range(expected_steps)]
    by_block = [sum(b == i for _, b in pairs) for i in range(blocks)]
    require(audit.get('routed_calls') == len(pairs), 'routed_calls mismatch')
    require(audit.get('routed_by_forward') == by_step, 'routed_by_forward mismatch')
    require(audit.get('routed_by_block') == by_block, 'routed_by_block mismatch')
    for i, summary in enumerate(audit['forward_summaries']):
        require(summary.get('routed_blocks') == by_step[i], f'forward {i}: routed_blocks mismatch')


def _control(row, mode, prior, cap, config):
    """Validate one applied layer and return controller diagnostics."""
    control = row.get('control')
    require(isinstance(control, dict), 'missing control object')
    if mode == 'fixed':
        for a in row['alpha']:
            close(a, prior, 'fixed alpha')
        return False, None
    require(type(control.get('fallback')) is bool, 'control.fallback must be boolean')
    selected = control.get('alpha')
    if mode == 'heads_budget':
        selected = vector(selected, 'head control alpha', length=len(row['alpha']), minimum=0, maximum=cap)
    else:
        selected = [number(selected, 'control alpha', minimum=0, maximum=cap)]*len(row['alpha'])
    for actual, intended in zip(row['alpha'], selected):
        close(actual, intended, 'applied/control alpha')
    if mode in ('dynamic_strength', 'dynamic_strength_dof'):
        valid = integer(control.get('valid_probe_count'), 'valid_probe_count')
        et, en, ed = [number(control.get(k), k, minimum=0) for k in
                      ('temporal_energy', 'complement_energy', 'total_energy')]
        if control['fallback']:
            for a in selected:
                close(a, prior, 'fallback alpha')
        else:
            require(valid > 0 and ed > 0, 'nonfallback controller lacks valid energy')
        j0 = number(control.get('objective_at_prior'), 'objective_at_prior', minimum=0)
        j1 = number(control.get('objective_at_selected'), 'objective_at_selected', minimum=0)
        require(j1 <= j0 + 2e-5*abs(j0)+1e-8, 'controller objective increased')
        if mode == 'dynamic_strength_dof':
            dim = integer(control.get('feature_dimension'), 'feature_dimension', minimum=1)
            require(control.get('basis') == 'centered' and
                    control.get('calibration') == 'equal_variance_per_degree_of_freedom',
                    'DOF basis/calibration mismatch')
            close(control.get('temporal_variance'), et, 'DOF temporal variance')
            close(control.get('complement_variance'), en/max(1, dim-1), 'DOF complement variance')
            close(control.get('overall_variance'), ed/dim, 'DOF overall variance')
            close(et+en, ed, 'centered projection energy', rtol=1e-4)
            if not control['fallback']:
                require(dim > 1, 'DOF nonfallback needs D>1')
                mu = number(config.get('prior_weight'), 'prior_weight', minimum=0)
                c = (1-prior)/prior
                den = et + c*en/(dim-1) + mu*ed/dim
                expected = min(cap, max(0., (et+mu*prior*ed/dim)/den))
                close(selected[0], expected, 'DOF closed-form alpha')
        return control['fallback'], None
    require(control.get('exact_full_correction_budget') is True, 'head budget must use full correction energy')
    requested = number(control.get('requested_energy'), 'requested_energy', minimum=0)
    allocated = number(control.get('allocated_energy'), 'allocated_energy', minimum=0)
    close(requested, prior**2*row['correction_energy'], 'requested head budget')
    close(allocated, row['applied_energy'], 'allocated/applied head energy')
    close(allocated, requested, 'head budget conservation')
    close(control.get('energy_error'), allocated-requested, 'reported energy_error')
    require(number(control.get('utility'), 'utility', minimum=0) + 1e-7 >=
            number(control.get('uniform_utility'), 'uniform_utility', minimum=0)*(1-2e-5),
            'head allocation utility below uniform')
    return control['fallback'], abs(allocated-requested)/max(requested, 1e-30)


def check_feature(audit, expected_steps=20, blocks=50):
    """Verify a completed feature-guidance audit; raise AuditError on failure."""
    require(isinstance(audit, dict), 'audit must be a JSON object')
    require(audit.get('schema') == 'h3-feature-guidance-v1', 'wrong feature schema')
    steps, layers = _common(audit, expected_steps, blocks)
    config = audit.get('feature_config', {})
    require(isinstance(config, dict), 'feature_config must be an object')
    mode = config.get('mode')
    require(mode in ('fixed', 'dynamic_strength', 'dynamic_strength_dof', 'heads_budget'), 'unknown mode')
    prior = number(config.get('alpha_prior'), 'alpha_prior', minimum=0, maximum=1)
    cap = number(config.get('alpha_max'), 'alpha_max', minimum=prior, maximum=1)
    close(audit.get('alpha'), prior, 'audit alpha prior')
    for key in ('full_dit_forward_calls_added', 'intermediate_vae_decode_calls'):
        require(audit.get(key) == 0, key + ': expected zero')
    if mode == 'dynamic_strength_dof' and prior > 0 and 'effective_collateral' in audit:
        close(audit['effective_collateral'], (1-prior)/prior, 'effective_collateral')
    boundary_flag = boundary_exclusion(audit['boundary_probes_excluded']) if 'boundary_probes_excluded' in audit else None
    summaries = audit.get('feature_forward_summaries')
    require(isinstance(summaries, list) and len(summaries) == expected_steps, 'missing feature summaries')
    values, routed, errors, dispatch = [], [], [], []
    per_step, per_block = [[] for _ in range(expected_steps)], [[] for _ in range(blocks)]
    fallback_count, boundary_rows = 0, []
    for n, summary in enumerate(summaries):
        require(isinstance(summary, dict), 'feature summary must be an object')
        require(summary.get('forward') == n, 'feature forwards not ordered')
        rows = summary.get('layers')
        require(isinstance(rows, list) and len(rows) == blocks, f'forward {n}: missing layer records')
        for b, row in enumerate(rows):
            label = f'forward {n} block {b}'
            require(isinstance(row, dict), label + ': object required')
            require(row.get('block') == b and row.get('forward') == n, label + ': wrong identity')
            require(row.get('mode') == mode, label + ': wrong mode')
            active = steps[0] <= n < steps[1] and layers[0] <= b < layers[1] and prior > 0 and cap > 0
            require(type(row.get('applied')) is bool and row['applied'] == active, label + ': applied mismatch')
            if 'finite_output' in row:
                require(row['finite_output'] is True, label + ': nonfinite output')
            expected_calls = (3 if mode == 'fixed' else 5) if active else 1
            require(integer(row.get('attention_calls'), label+' attention_calls', minimum=1) == expected_calls,
                    label + ': attention-call count mismatch')
            if not active:
                continue
            require(row.get('finite_output') is True, label + ': missing finite output evidence')
            alpha = vector(row.get('alpha'), label+' alpha', minimum=0, maximum=cap)
            require(len(alpha) > 0, label + ': empty alpha')
            if mode in ('dynamic_strength', 'dynamic_strength_dof'):
                for a in alpha:
                    close(a, alpha[0], label+' scalar/shared alpha')
            for key, val in (('alpha_mean', sum(alpha)/len(alpha)), ('alpha_min', min(alpha)), ('alpha_max', max(alpha))):
                close(row.get(key), val, label+' '+key)
            energy = vector(row.get('head_energy'), label+' head_energy', length=len(alpha), minimum=0)
            number(row.get('reference_mass_mean'), label+' reference_mass_mean', minimum=0, maximum=1)
            number(row.get('correction_energy'), label+' correction_energy', minimum=0)
            number(row.get('applied_energy'), label+' applied_energy', minimum=0)
            close(row.get('correction_energy'), sum(energy), label+' full correction energy')
            close(row.get('applied_energy'), sum(a*a*e for a, e in zip(alpha, energy)), label+' applied energy')
            fallback, error = _control(row, mode, prior, cap, config)
            fallback_count += int(fallback)
            for source in (row, row['control']):
                if 'boundary_probes_excluded' in source:
                    boundary_rows.append({'step': n, 'layer': b,
                                          'value': boundary_exclusion(source['boundary_probes_excluded'])})
                    break
            if error is not None:
                errors.append(error)
            if mode != 'fixed':
                dispatch.append(number(row.get('controller_host_dispatch_seconds'), 'host dispatch seconds', minimum=0))
            values.extend(alpha); per_step[n].extend(alpha); per_block[b].extend(alpha); routed.append((n,b))
    _routed_counts(audit, routed, expected_steps, blocks)
    return {'status': 'passed', 'schema': audit['schema'], 'mode': mode,
            'expected_steps': expected_steps, 'blocks': blocks, 'routed_calls': len(routed),
            'alpha': stats(values), 'alpha_by_step': [{'step': i, **stats(v)} for i,v in enumerate(per_step)],
            'alpha_by_layer': [{'layer': i, **stats(v)} for i,v in enumerate(per_block)],
            'fallback_count': fallback_count, 'head_budget_relative_error': stats(errors),
            'boundary_probes_excluded': boundary_flag, 'boundary_exclusion_records': boundary_rows,
            'budget_scope': 'attention correction before W_o; excludes head cross terms after projection',
            'controller_host_dispatch_seconds': {'total': sum(dispatch), **stats(dispatch)},
            'timing_scope': 'host dispatch only; CUDA asynchronous; not GPU compute or end-to-end inference cost'}


def check_coverage_blend(audit, expected_steps=20, blocks=50):
    """V2 solver audit plus the .25 identity-anchor contract."""
    require(isinstance(audit, dict), 'audit must be a JSON object')
    require(audit.get('schema') == 'h3-temporal-coverage-blend', 'wrong coverage-blend schema')
    steps, layers = _common(audit, expected_steps, blocks)
    close(audit.get('alpha'), .25, 'coverage alpha')
    config = audit.get('coverage_config', {})
    require(isinstance(config, dict), 'coverage_config must be an object')
    close(config.get('coverage_mix'), .25, 'coverage_mix')
    require(config.get('solver') == 'damped_newton_cpu_float64' and
            config.get('fallback_policy') == 'same_time_weak', 'coverage solver/fallback mismatch')
    require(config.get('iterations') == 64, 'coverage iteration cap mismatch')
    close(config.get('tolerance'), .0002, 'coverage tolerance')
    expected = {(s,b) for s in range(*steps) for b in range(*layers)}
    calls = audit.get('coverage_calls')
    require(isinstance(calls, list) and len(calls) == len(expected), 'coverage calls incomplete')
    pairs, solved, fallback, seconds, iterations, diagonal, minimum = [], [], [], [], [], [], []
    for row in calls:
        require(isinstance(row, dict), 'coverage call must be an object')
        pair = (row.get('forward'), row.get('block'))
        require(pair in expected and pair not in pairs, 'duplicate/out-of-range coverage record')
        require(row.get('applied') is True, 'coverage correction not applied')
        close(row.get('coverage_mix'), .25, 'per-call coverage_mix')
        diagonal.append(number(row.get('mean_diagonal_probability'), 'mean diagonal', minimum=.75-1e-6, maximum=1+1e-6))
        if 'min_diagonal_probability' in row:
            minimum.append(number(row['min_diagonal_probability'], 'minimum diagonal', minimum=.75-1e-6, maximum=1+1e-6))
        n = integer(row.get('solver_iterations'), 'solver_iterations')
        require(n <= 64, 'solver iteration limit exceeded')
        iterations.append(n)
        seconds.append(number(row.get('solver_seconds'), 'solver_seconds', minimum=0))
        if row.get('routing_solved') is True:
            require(row.get('reason') != 'same_time_fallback', 'ambiguous solved/fallback status')
            for key in ('row_error', 'column_error'):
                number(row.get(key), key, minimum=0, maximum=config['tolerance'])
            solved.append(row)
        else:
            require(row.get('routing_solved') is False and row.get('reason') == 'same_time_fallback', 'unknown coverage outcome')
            fallback.append(row)
        pairs.append(pair)
    require(bool(solved), 'no successfully solved coverage calls')
    _routed_counts(audit, pairs, expected_steps, blocks)
    require(audit.get('coverage_solved_calls') == len(solved), 'solved count mismatch')
    require(audit.get('same_time_fallback_calls') == len(fallback), 'fallback count mismatch')
    close(audit.get('solver_wall_seconds'), sum(seconds), 'solver time total')
    seen = set()
    for n, summary in enumerate(audit['forward_summaries']):
        if any(s == n for s,b in expected):
            require(summary.get('sampled_finite') is True, 'nonfinite coverage forward')
        for row in summary.get('layer_stats', []):
            require(isinstance(row, dict), 'coverage layer statistic must be an object')
            pair = (n, row.get('block'))
            require(pair in expected and pair not in seen, 'coverage layer_stats identity mismatch')
            require(row.get('finite') is True, 'nonfinite coverage layer')
            number(row.get('correction_ratio'), 'coverage correction ratio', minimum=0)
            seen.add(pair)
    require(seen == expected, 'missing coverage finite layer evidence')
    return {'status': 'passed', 'schema': audit['schema'], 'routed_calls': len(pairs),
            'solved_calls': len(solved), 'same_time_fallback_calls': len(fallback),
            'solved_fraction': len(solved)/len(pairs), 'coverage_mix': .25,
            'mean_diagonal_probability': stats(diagonal), 'min_diagonal_probability': stats(minimum),
            'diagonal_check_scope': 'every call minimum' if len(minimum) == len(pairs) else 'means; per-row minima incompletely recorded',
            'solver_seconds_total': sum(seconds), 'solver_iterations': stats(iterations),
            'fallback_reasons': {str(k): sum(r.get('fallback_reason') == k for r in fallback)
                                 for k in {r.get('fallback_reason') for r in fallback}}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audit', type=Path)
    parser.add_argument('--kind', choices=('auto', 'feature', 'coverage_blend'), default='auto')
    parser.add_argument('--steps', type=int, default=20)
    parser.add_argument('--blocks', type=int, default=50)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        audit = json.loads(args.audit.read_text())
        require(isinstance(audit, dict), 'audit must be a JSON object')
        kind = args.kind
        if kind == 'auto':
            kind = 'feature' if audit.get('schema') == 'h3-feature-guidance-v1' else 'coverage_blend'
        result = (check_feature if kind == 'feature' else check_coverage_blend)(audit, args.steps, args.blocks)
        result['input_audit'] = str(args.audit.resolve())
        raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
        if args.output:
            args.output.write_text(raw)
        else:
            sys.stdout.write(raw)
        return 0
    except (AuditError, ValueError, TypeError, KeyError, OSError) as error:
        sys.stderr.write(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False)+'\n')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
