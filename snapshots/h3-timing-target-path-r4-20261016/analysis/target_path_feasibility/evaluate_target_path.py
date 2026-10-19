#!/usr/bin/env python3
"""Frozen CPU-only C/Y feasibility check. No model, GPU, fitting of M or lag sensor."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
HEADS = [0, 14, 28, 42]
CALLS = [6, 10, 14]
W = np.arange(10, 26)
EVENT = np.arange(14, 20)
EVENT_LOCAL = np.arange(4, 10)
OTHER_LOCAL = np.array([i for i in range(16) if i not in EVENT_LOCAL])
FIT_HEADS = [0, 2]
HOLD_HEADS = [1, 3]
EPS = 64 * np.finfo(np.float64).eps


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json_exclusive(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def load_frozen_inputs():
    p = read_json(HERE / 'protocol.json')
    if p.get('schema') != 'h3-target-path-feasibility-protocol-v1':
        raise ValueError('wrong protocol')
    exact = {'calls': CALLS, 'primary_call': 6, 'block': 25, 'heads': HEADS,
             'fit_head_indices': FIT_HEADS, 'hold_head_indices': HOLD_HEADS,
             'window_bins': W.tolist(), 'event_bins': EVENT.tolist(),
             'radius_bins': 4, 'max_bin_jump': 2, 'minimum_pooled_gain': .25,
             'minimum_median_advance_frames': 4.0, 'common_support_required': 1.0}
    if any(p.get(k) != v for k, v in exact.items()):
        raise ValueError('protocol constants changed; requires a new protocol')
    for name, key in [('source_groups.json', 'source_groups_sha256'),
                      ('encoded_reference_locator.json', 'locator_sha256'),
                      ('FROZEN_DESIGN.txt', 'design_sha256'),
                      ('source_runtime_evidence.json', 'source_runtime_evidence_sha256'),
                      ('source_runtime_report.txt', 'source_runtime_report_sha256')]:
        if file_sha(HERE / name) != p[key]:
            raise ValueError('frozen source input hash mismatch: ' + name)
    groups = read_json(HERE / 'source_groups.json')
    locator = read_json(HERE / 'encoded_reference_locator.json')
    if groups.get('source_only') is not True or groups.get('target_features_read') is not False:
        raise ValueError('source groups were not frozen independently')
    if groups.get('status') != 'available' or groups.get('fps') != 24:
        raise ValueError('source grouping unavailable or wrong fps')
    tiles = sorted(tuple(x) for x in groups['high'])
    expected_tiles = {(y, x) for y in range(1, 20, 3) for x in range(1, 38, 3)}
    if len(tiles) != 23 or len(set(tiles)) != 23 or not set(tiles) <= expected_tiles:
        raise ValueError('invalid frozen high-activity tiles')
    positions = []
    fit_positions, hold_positions = [], []
    for index, (y, x) in enumerate(tiles):
        for dy in [-1, 0, 1]:
            for dx in [-1, 0, 1]:
                position = (y + dy, x + dx)
                destination = fit_positions if index % 2 == 0 else hold_positions
                destination.append(len(positions))
                positions.append(position)
    if len(set(positions)) != 207 or set(fit_positions) & set(hold_positions):
        raise ValueError('spatial partitions overlap')
    mapping = locator['position_mapping']
    if len(mapping) != 42 or [x['latent_bin'] for x in mapping] != list(range(42)):
        raise ValueError('position-bin layout mismatch')
    frame_centres = np.array([sum(x['position_bin_frames_inclusive']) / 2 for x in mapping])
    if not np.all(np.diff(frame_centres) > 0):
        raise ValueError('time coordinates not strictly ordered')
    return p, groups, locator, positions, fit_positions, hold_positions, frame_centres


def valid_path(path):
    path = np.asarray(path)
    return (path.shape == (16,) and np.issubdtype(path.dtype, np.integer)
            and path[0] == 10 and path[-1] == 25
            and bool(np.all((path >= 10) & (path <= 25)))
            and bool(np.all(np.abs(path - W) <= 4))
            and bool(np.all((np.diff(path) >= 0) & (np.diff(path) <= 2))))


def _prefer(a, b):
    if b is None:
        return True
    tolerance = EPS * max(1.0, abs(a[0]), abs(b[0]))
    if a[0] < b[0] - tolerance:
        return True
    if abs(a[0] - b[0]) <= tolerance:
        return (a[1], a[2]) < (b[1], b[2])
    return False


def solve_path(cost):
    """Exact constrained DP with fixed deterministic tie handling; absolute bins."""
    cost = np.asarray(cost, dtype=np.float64)
    if cost.shape != (16, 16) or not np.isfinite(cost).all():
        raise ValueError('finite16x16 cost required')
    states = {10: (float(cost[0, 0]), 0, (10,))}
    for row, t in enumerate(W[1:], 1):
        current = {}
        candidates = [25] if t == 25 else range(max(10, t - 4), min(25, t + 4) + 1)
        for u in candidates:
            best = None
            for previous in range(u - 2, u + 1):
                if previous not in states:
                    continue
                prior = states[previous]
                candidate = (prior[0] + float(cost[row, u - 10]),
                             prior[1] + abs(int(u - t)), prior[2] + (int(u),))
                if _prefer(candidate, best):
                    best = candidate
            if best is not None:
                current[u] = best
        states = current
    result = states.get(25)
    if result is None or not valid_path(result[2]):
        raise ValueError('no feasible path')
    return list(result[2]), result[0]


def variances(y, fit_positions):
    z = np.take(np.take(y, W, axis=1), fit_positions, axis=2)
    centred = z - z.mean(axis=1, keepdims=True)
    v = np.mean(centred ** 2, axis=(1, 2, 3))
    native_scale = np.mean(z ** 2, axis=(1, 2, 3))
    if np.any(v <= EPS * native_scale) or np.any(v <= 0) or not np.isfinite(v).all():
        return None
    return v


def costs_for_head(y, c, h, positions, variance):
    """Each entry sums all spatial/channel residuals; no per-token ratios."""
    yw = np.take(np.take(y[h], W, axis=0), positions, axis=1)
    p = yw.copy()
    p[EVENT_LOCAL] = np.take(c[h], positions, axis=1)
    out = np.empty((16, 16), dtype=np.float64)
    for row in range(16):
        difference = yw - p[row]
        out[row] = np.sum(difference ** 2, axis=(1, 2)) / variance
    return out


def evaluate_branch(y, c, fit_positions, hold_positions, centres):
    """Small arrays [4,42,S,D]/[4,6,S,D], unmodified, FP64; source selection fixed."""
    if (y.ndim != 4 or c.shape != (4, 6, y.shape[2], y.shape[3])
            or y.shape[0:2] != (4, 42)):
        raise ValueError('invalid selected feature arrays')
    if not np.isfinite(y).all() or not np.isfinite(c).all():
        finite_rows = np.isfinite(y).all(axis=-1)
        finite_rows[:, EVENT] &= np.isfinite(c).all(axis=-1)
        support = float(np.mean(np.all(finite_rows, axis=0)))
        return {'status': 'unknown', 'reason': 'nonfinite_no_dropping', 'common_support': support,
                'common_support_scope': '42xselected_spatial rows finite in every head; C required at event bins'}
    nu = variances(y, fit_positions)
    if nu is None:
        return {'status': 'unknown', 'reason': 'near_constant_target_path', 'common_support': 1.0}
    fit_cost = sum(costs_for_head(y, c, h, fit_positions, nu[h]) for h in FIT_HEADS)
    path, fit_objective = solve_path(fit_cost)
    path = np.asarray(path, dtype=np.int64)
    displacement = centres[path[EVENT_LOCAL]] - centres[EVENT]
    median_advance = float(np.median(displacement))
    metrics = []
    for h in HOLD_HEADS:
        cost = costs_for_head(y, c, h, hold_positions, nu[h])
        e0 = float(np.sum(cost[EVENT_LOCAL, EVENT_LOCAL]))
        native_event = np.take(np.take(y[h], EVENT, axis=0), hold_positions, axis=1)
        native_energy = float(np.sum(native_event ** 2) / nu[h])
        epath = float(np.sum(cost[EVENT_LOCAL, path[EVENT_LOCAL] - 10]))
        boundary = float(np.sum(cost[OTHER_LOCAL, path[OTHER_LOCAL] - 10]))
        efree = sum(float(np.min(cost[row, max(0, row - 4):min(16, row + 5)])) for row in EVENT_LOCAL)
        fixed_plus4 = float(sum(cost[row, row + 4] for row in EVENT_LOCAL))
        nearzero = e0 <= EPS * native_energy or e0 <= 0
        metrics.append({'head': HEADS[h], 'E0': e0, 'Epath': epath, 'boundary_cost': boundary,
                        'free_NN_lower_bound': efree, 'fixed_plus4_event_cost': fixed_plus4,
                        'native_event_energy': native_energy, 'near_zero_proposal': nearzero,
                        'gain': None if nearzero else 1 - (epath + boundary) / e0,
                        'event_only_gain': None if nearzero else 1 - epath / e0})
    report = {'path': path.tolist(), 'fit_objective': fit_objective,
              'event_displacement_frames': displacement.tolist(),
              'event_median_advance_frames': median_advance,
              'repeated_edges': int(np.sum(np.diff(path) == 0)),
              'skipped_edges': int(np.sum(np.diff(path) == 2)),
              'common_support': 1.0, 'variance_by_head': nu.tolist(), 'held_out_heads': metrics}
    if any(m['near_zero_proposal'] for m in metrics):
        report.update(status='unknown', reason='near_zero_proposal_denominator')
        return report
    total_e0 = sum(m['E0'] for m in metrics)
    gain = 1 - sum(m['Epath'] + m['boundary_cost'] for m in metrics) / total_e0
    free_ratio = sum(m['free_NN_lower_bound'] for m in metrics) / total_e0
    passed = (gain >= .25 and all(m['gain'] > 0 for m in metrics)
              and median_advance >= 4 and median_advance > 0)
    report.update(status='pass' if passed else 'reject', reason='all_main_gates_pass' if passed else 'main_gate_not_met',
                  pooled_gain=gain, pooled_free_NN_ratio=free_ratio,
                  path_capacity_impossible=free_ratio > .75,
                  independent_heads_improve=all(m['gain'] > 0 for m in metrics),
                  threshold_gain=.25, threshold_advance_frames=4.0)
    return report


def evaluate_arrays(y, c, fit_positions, hold_positions, centres):
    y = np.asarray(y, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    if not (set(fit_positions).isdisjoint(hold_positions) and fit_positions and hold_positions):
        raise ValueError('nonoverlapping nonempty spatial partitions required')
    main = evaluate_branch(y, c, fit_positions, hold_positions, centres)
    if not np.isfinite(y).all() or not np.isfinite(c).all():
        return {'status': 'unknown', 'reason': 'invalid_features', 'main': main, 'negative_controls': {}}
    static_delta = (c - y[:, EVENT]).mean(axis=1, keepdims=True)
    static_candidate = y[:, EVENT] + static_delta
    negative = {
        'event_time_constant_correction': evaluate_branch(y, static_candidate, fit_positions, hold_positions, centres),
        'reverse_candidate_event_order': evaluate_branch(y, c[:, ::-1].copy(), fit_positions, hold_positions, centres),
    }
    # Only an exactly zero-correction negative control is a safe identity no-op.
    if np.array_equal(static_candidate, y[:, EVENT]):
        negative['event_time_constant_correction'].update(status='noop', reason='exact_zero_correction_control')
    if main['status'] != 'pass':
        status, reason = main['status'], 'main_' + main['reason']
    elif any(x['status'] == 'pass' for x in negative.values()):
        status, reason = 'reject', 'negative_control_also_passed'
    elif any(x['status'] not in ('reject', 'noop') for x in negative.values()):
        status, reason = 'unknown', 'negative_control_indeterminate'
    else:
        status, reason = 'advance_to_generation_test', 'representability_and_negative_controls_only'
    return {'status': status, 'reason': reason, 'main': main, 'negative_controls': negative,
            'claim_limit': 'Feature-proposal feasibility only; not correct action, video quality, automatic timing detection or novelty.'}


def _tensor_signature(tensor):
    import torch
    if tensor.device.type != 'cpu' or not tensor.is_contiguous():
        raise ValueError('CPU contiguous tensor required')
    return {'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
            'bytes': tensor.numel() * tensor.element_size(),
            'sha256': hashlib.sha256(tensor.view(torch.uint8).numpy()).hexdigest()}


def validate_payload(payload, record, expected_layout, run_id):
    import torch
    if set(payload) != {'target', 'candidate', 'reference_mass', 'metadata'}:
        raise ValueError('wrong payload fields')
    meta = payload['metadata']
    if meta != record['metadata']:
        raise ValueError('capture/router metadata mismatch')
    expected = {'schema': 'h3-target-path-candidate-v1', 'run_id': run_id,
                'block_index': 25, 'head_indices': HEADS, 'grid': [42, 23, 41],
                'candidate_latent_interval_half_open': [14, 20],
                'tensor_axis_order': ['batch', 'head', 'time', 'y', 'x', 'channel']}
    if any(meta.get(k) != v for k, v in expected.items()) or meta.get('forward_index') not in CALLS:
        raise ValueError('wrong checkpoint/head/geometry/schema')
    if meta.get('layout') != expected_layout:
        raise ValueError('actual router/capture layout mismatch')
    plan = meta['layout']
    qa, qb = plan['target_video_segment']
    if (qb - qa != 42 * 943 or plan['frame_rows'] != 943
            or plan['latent_interval_half_open'] != [14, 20]
            or plan['query_interval_half_open'] != [qa + 14*943, qa + 20*943]
            or plan['signature'][1:4] != [42, 46, 82]):
        raise ValueError('packed target rows cannot be reshaped as stated')
    shapes = {'target': [1, 4, 42, 23, 41, 128], 'candidate': [1, 4, 6, 23, 41, 128],
              'reference_mass': [1, 4, 6, 23, 41]}
    for name, shape in shapes.items():
        t = payload[name]
        if not isinstance(t, torch.Tensor) or list(t.shape) != shape:
            raise ValueError('actual tensor shape mismatch: ' + name)
        if t.dtype != (torch.float32 if name == 'reference_mass' else torch.bfloat16):
            raise ValueError('actual tensor dtype mismatch: ' + name)
        if not bool(torch.isfinite(t).all()) or _tensor_signature(t) != meta['tensors'][name]:
            raise ValueError('actual tensor hash/finite mismatch: ' + name)
    mass = payload['reference_mass']
    if bool(((mass < 0) | (mass > 1)).any()):
        raise ValueError('reference group mass outside[0,1]')
    return meta


def _signature_matches(actual, expected):
    return all(actual.get(k) == expected[k] for k in ('shape', 'dtype', 'sha256'))


def validate_source_runtime(evidence, condition, groups, locator):
    """Reuse frozen source-only tiles, with explicit and pinned decoder differences."""
    if evidence.get('schema') != 'h3-input-runtime-difference-v1':
        raise ValueError('wrong source runtime evidence schema')
    decode = evidence['decode_conversion']
    conversions = [decode[k] for k in ('r2_actual', 'r3_actual', 'r2_same_host_base16_control')]
    for field in ('source_sha256', 'full_native_yuv_sha256'):
        if len({x[field] for x in conversions}) != 1:
            raise ValueError('source MP4/YUV identity evidence differs')
    if decode.get('full_native_yuv_equal') is not True or any(x['frame_count'] != 141 for x in conversions):
        raise ValueError('complete source YUV/geometry evidence missing')
    r2 = evidence['source_conditions']['r2']['actual_fields']
    r3 = evidence['source_conditions']['r3']['actual_fields']
    for name, expected in [('r2_actual', r2), ('r3_actual', r3)]:
        if decode[name]['full_gbrpf32le_sha256'] != expected['input_video']['sha256']:
            raise ValueError('source decoder and original condition evidence disagree')
    r2_video, r3_video = (r['native_vae_calls'][1] for r in (r2, r3))
    if not _signature_matches(groups['prepared_tensor_expected'], r3_video['prepared_frames']):
        raise ValueError('frozen source groups do not match their R3 source')
    if not _signature_matches(locator['tensor_metadata'], r3_video['latent']):
        raise ValueError('frozen locator does not match its R3 reference')
    if (r2_video['latent']['shape'] != r3_video['latent']['shape']
            or r2_video['prepared_frames']['shape'] != r3_video['prepared_frames']['shape']):
        raise ValueError('source runtime geometries differ')
    video = next(x for x in condition['pair_snapshot']['actual']['references']
                 if x['reference_index'] == 1 and x['kind'] == 'video')
    actual_video = condition['native_vae_calls'][1]
    for label, actual, expected in [
            ('decoded RGB', condition['input_video'], r2['input_video']),
            ('prepared RGB', actual_video['prepared_frames'], r2_video['prepared_frames']),
            ('encoded reference latent', actual_video['latent'], r2_video['latent']),
            ('packed clean reference latent', video['clean_latent'], r2_video['latent'])]:
        if not _signature_matches(actual, expected):
            raise ValueError('R4 actual source does not match frozen R2 ' + label)
    return {'policy': 'fixed_R3_source_only_tiles_R4_actual_source_must_match_R2',
            'groups_recomputed_from_current_RGB': False,
            'source_mp4_sha256_in_prior_audit': conversions[0]['source_sha256'],
            'all141_native_YUV_sha256_in_prior_audit': conversions[0]['full_native_yuv_sha256'],
            'source_identity_basis': 'pinned prior R2/R3 full decode audit; current tensors match R2',
            'selection_runtime': 'R3 .9 PyAV16', 'current_expected_runtime': 'R2/R4 .41 PyAV17',
            'selection_prepared_RGB': r3_video['prepared_frames'],
            'current_prepared_RGB': r2_video['prepared_frames'],
            'selection_reference_latent': r3_video['latent'],
            'current_reference_latent': r2_video['latent'],
            'prepared_RGB_matches_selection': _signature_matches(r2_video['prepared_frames'], r3_video['prepared_frames']),
            'reference_latent_matches_selection': _signature_matches(r2_video['latent'], r3_video['latent'])}


def validate_run_metadata(router, condition, noise, groups, locator):
    run_id = router.get('run_id')
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', run_id) is None:
        raise ValueError('invalid run id')
    if condition.get('run_id') != run_id or noise.get('run_id') != run_id:
        raise ValueError('condition/noise/capture run ids differ')
    if (router.get('mode') != 'native' or router.get('routed_calls') != 0
            or router.get('completed_calls') != 1000 or router.get('completed_forward_calls') != 20
            or router.get('native_override_calls') != 1000):
        raise ValueError('require completed20x50 native run; status label alone is insufficient')
    actual = condition['pair_snapshot']['actual']
    if condition['pair_snapshot'].get('verified') is not True:
        raise ValueError('condition snapshot not verified')
    protocol = read_json(HERE / 'protocol.json')
    if protocol.get('source_group_policy') != 'fixed_R3_source_only_tiles_R4_actual_source_must_match_R2':
        raise ValueError('source runtime policy changed')
    evidence_path = HERE / 'source_runtime_evidence.json'
    if file_sha(evidence_path) != protocol['source_runtime_evidence_sha256']:
        raise ValueError('source runtime evidence hash changed')
    source_audit = validate_source_runtime(read_json(evidence_path), condition, groups, locator)
    packed = actual['packed_layout']
    layout = router['validated_layout']
    if packed['seq_len'] != layout['seq_len'] or packed['segments'] != layout['segments']:
        raise ValueError('condition/router packed layout differs')
    if not noise.get('actual_noise_streams'):
        raise ValueError('actual noise evidence missing')
    records = router.get('target_path_feature_captures', [])
    if len(records) != 3 or sorted(x['metadata']['forward_index'] for x in records) != CALLS:
        raise ValueError('need exactly three distinct target-path captures')
    sigmas = router['sample_sigmas']
    for record in records:
        meta = record['metadata']
        step = meta['forward_index']
        if meta.get('sampler_sigma_video') != sigmas[step]:
            raise ValueError('capture sampler sigma mismatch')
        if Path(record['path']).name != f'block25_step{step:03d}.pt':
            raise ValueError('capture filename/call mismatch')
    return run_id, layout, records, source_audit


def run(args):
    # Source-only freeze is validated and archived before any .pt target is opened.
    protocol, groups, locator, positions, fit, hold, centres = load_frozen_inputs()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    router, condition, noise = (read_json(p) for p in (args.router, args.condition, args.noise))
    run_id, layout, records, source_audit = validate_run_metadata(router, condition, noise, groups, locator)
    capture_dir = Path(args.capture_dir).resolve(strict=True)
    inputs = {'schema': 'h3-target-path-frozen-inputs-v1', 'run_id': run_id,
              'source_groups_validated_before_target_load': True, 'real_target_read_yet': False,
              'protocol': protocol, 'source_runtime_audit': source_audit,
              'fit_tiles_sorted_indices': list(range(0,23,2)),
              'hold_tiles_sorted_indices': list(range(1,23,2)), 'positions': positions,
              'fit_positions': fit, 'hold_positions': hold,
              'file_sha256': {str(p): file_sha(p) for p in [args.router, args.condition, args.noise,
                                HERE/'protocol.json', HERE/'source_groups.json', HERE/'encoded_reference_locator.json',
                                HERE/'source_runtime_evidence.json', HERE/'source_runtime_report.txt', Path(__file__)]},
              'native_capture_passivity_gate': 'not_certified_by_this_CPU_tool'}
    write_json_exclusive(out / 'frozen_input_audit.json', inputs)
    import torch
    torch.set_num_threads(1)
    results = {}
    for record in sorted(records, key=lambda x: x['metadata']['forward_index']):
        step = record['metadata']['forward_index']
        path = capture_dir / f'block25_step{step:03d}.pt'
        if path.is_symlink() or path.stat().st_size != record['bytes'] or file_sha(path) != record['sha256']:
            raise ValueError('capture file size/hash/symlink mismatch')
        payload = torch.load(path, map_location='cpu', weights_only=True, mmap=True)
        meta = validate_payload(payload, record, layout, run_id)
        yy = [x[0] for x in positions]
        xx = [x[1] for x in positions]
        target = payload['target'][0, :, :, yy, xx, :].to(torch.float64).numpy()
        candidate = payload['candidate'][0, :, :, yy, xx, :].to(torch.float64).numpy()
        # Explicit axis check detects advanced-indexing layout mistakes.
        if target.shape != (4,42,207,128) or candidate.shape != (4,6,207,128):
            raise ValueError('selected feature axis layout mismatch')
        result = evaluate_arrays(target, candidate, fit, hold, centres)
        result.update(step=step, primary=step == 6, block=25, capture_sha256=record['sha256'],
                      tensor_sha256={k: v['sha256'] for k,v in meta['tensors'].items()},
                      source='same-forward native trajectory; C is not action ground truth')
        write_json_exclusive(out / f'step{step:03d}.json', result)
        results[str(step)] = result
        del payload, target, candidate
    summary = {'schema': 'h3-target-path-feasibility-results-v1', 'run_id': run_id,
               'status': results['6']['status'], 'primary_call': 6, 'results': results,
               'uses_late_calls_to_override_primary': False,
               'native_capture_passivity_gate': 'root_must_verify_independently',
               'new_architecture_or_action_correctness_proven': False,
               'software': {'python':sys.version,'numpy':np.__version__,'torch':torch.__version__,
                            'torch_threads':torch.get_num_threads(),'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES']}}
    write_json_exclusive(out / 'RESULTS.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('router', 'condition', 'noise', 'capture-dir', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    output_was_present = args.output.exists()
    try:
        summary = run(args)
    except Exception as exc:
        if not output_was_present and args.output.exists():
            error = args.output / 'EXECUTION_ERROR.json'
            if not error.exists():
                write_json_exclusive(error, {'status':'invalid_input_or_execution_error', 'type':type(exc).__name__, 'error':str(exc)})
        raise
    print(json.dumps({'status':summary['status'], 'primary_call':6, 'output':str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
