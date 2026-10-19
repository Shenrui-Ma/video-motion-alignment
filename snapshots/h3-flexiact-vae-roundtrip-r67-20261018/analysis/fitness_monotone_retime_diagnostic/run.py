"""One frozen monotone post-hoc correspondence, fitting upper arms only."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def better(a, b):
    if b is None:
        return True
    if a[0] < b[0] - 1e-12:
        return True
    if abs(a[0] - b[0]) <= 1e-12:
        return (a[1], a[2]) < (b[1], b[2])
    return False


def monotone(cost, band=8):
    n = len(cost)
    assert cost.shape == (n, n) and np.isfinite(cost).all()
    states = {(0, 1): (float(cost[0, 0]), 0, (0,))}
    for i in range(1, n):
        next_states = {}
        for (previous, repeated), record in states.items():
            for delta in (0, 1, 2):
                j = previous + delta
                if j >= n or abs(j - i) > band or (delta == 0 and repeated >= 2):
                    continue
                if i == n - 1 and j != n - 1:
                    continue
                run = repeated + 1 if delta == 0 else 1
                candidate = (record[0] + float(cost[i, j]), record[1] + abs(j - i), record[2] + (j,))
                if better(candidate, next_states.get((j, run))):
                    next_states[(j, run)] = candidate
        states = next_states
    best = None
    for record in states.values():
        if better(record, best):
            best = record
    assert best is not None
    return np.array(best[2]), best


def add_features(view):
    values = {}
    for name, idx in [('upper_arm_direction_fit', [0, 2]), ('arm_direction', [0, 1, 2, 3]),
                      ('left_arm_direction', [0, 1]), ('right_arm_direction', [2, 3]),
                      ('forearm_direction_not_fit', [1, 3]),
                      ('left_forearm_direction_not_fit', [1]), ('right_forearm_direction_not_fit', [3])]:
        values[name] = (view['arm_direction'][:, idx], view['arm_conf'][:, idx])
    for name, idx in [('wrist_relative_not_fit', [0, 1]), ('left_wrist_relative_not_fit', [0]),
                      ('right_wrist_relative_not_fit', [1])]:
        values[name] = (view['wrist_relative'][:, idx], view['wrist_conf'][:, idx])
    return values


def compare(source, target, mapping, window, name):
    idx = np.arange(window[0], window[1] + 1)
    s, sc = source[name]
    t, tc = target[name]
    a, original, retimed = s[idx], t[idx], t[mapping[idx]]
    valid = np.isfinite(a).all(-1) & np.isfinite(original).all(-1) & np.isfinite(retimed).all(-1)
    weights = np.minimum(np.minimum(sc[idx], tc[idx]), tc[mapping[idx]]).clip(0, 1)
    weights = np.where(valid, weights, 0)
    denominator = float(weights.sum())
    errors = [float((np.nan_to_num(np.linalg.norm(a - value, axis=-1)) * weights).sum() / denominator)
              if denominator else None for value in (original, retimed)]
    coverage = float(valid.mean())
    frames = int((weights.sum(-1) > 0).sum())
    relative = ((errors[1] - errors[0]) / errors[0]) if denominator and errors[0] > 1e-12 else None
    return {'window': window, 'feature': name, 'common_coverage': coverage, 'valid_frame_count': frames,
            'status': 'measured' if coverage >= .8 and frames >= 8 else 'UNKNOWN',
            'native_error': errors[0], 'retimed_error': errors[1], 'relative_change': relative,
            'worsening_over_5pct_engineering_screen': relative is not None and relative > .05,
            'source_original_indices': idx.tolist(), 'selected_native_original_indices': mapping[idx].tolist(),
            'common_valid_segments': valid.tolist()}


def main():
    protocol = json.loads((ROOT / 'PROTOCOL.json').read_text())
    for entry in protocol['inputs'].values():
        assert sha(entry['file']) == entry['sha256']
    sys.path.insert(0, str(Path(protocol['inputs']['original_time_functions']['file']).parent))
    import evaluate
    source_raw = json.loads(Path(protocol['inputs']['source_pose']['file']).read_text())
    native_raw = json.loads(Path(protocol['inputs']['native_pose']['file']).read_text())
    gate = json.loads(Path(protocol['inputs']['actual_pair_gate']['file']).read_text())
    assert gate['passed'] and native_raw['video']['sha256'] == gate['runs']['native']['video']['sha256']
    assert source_raw['provenance'] == native_raw['provenance']
    source = evaluate.original_time_view(source_raw, .3)
    native = evaluate.original_time_view(native_raw, .3)
    s, sc = add_features(source)['upper_arm_direction_fit']
    t, tc = add_features(native)['upper_arm_direction_fit']
    cost, supported = np.full((49, 49), 2.0), np.zeros((49, 49), dtype=bool)
    for i in range(49):
        for j in range(49):
            valid = np.isfinite(s[i]).all(-1) & np.isfinite(t[j]).all(-1)
            if valid.all():
                weight = np.minimum(sc[i], tc[j]).clip(0, 1)
                cost[i, j] = float((np.linalg.norm(s[i] - t[j], axis=-1) * weight).sum() / weight.sum())
                supported[i, j] = True
    mapping, optimum = monotone(cost)
    report = {'scope': protocol['scope'], 'protocol_sha256': sha(ROOT / 'PROTOCOL.json'),
              'implementation_sha256': sha(__file__), 'mapping': [], 'sum_cost': optimum[0],
              'mean_cost_including_missing_penalty': optimum[0] / 49,
              'identity_sum_cost': float(np.trace(cost)), 'sum_absolute_displacement_frames': optimum[1],
              'maximum_repeat_run': 2 if any(np.diff(mapping) == 0) else 1,
              'selected_fit_support': int(supported[np.arange(49), mapping].sum()),
              'fit_cost_matrix': cost.tolist(), 'fit_support_matrix': supported.tolist(),
              'confidence_results': {}}
    for i, j in enumerate(mapping):
        report['mapping'].append({'source_index': i, 'source_time_s': i / 8, 'native_index': int(j),
            'native_time_s': float(j) / 8, 'offset_ms': int(j - i) * 125,
            'fit_supported': bool(supported[i, j]), 'out_of_domain': not 0 <= j <= 48,
            'forced_endpoint': i in (0, 48), 'touches_displacement_limit': abs(j - i) == 8,
            'timing_interpretation_valid': bool(supported[i, j]) and i not in (0, 48)})
    for threshold in (.3, .5):
        sv = add_features(evaluate.original_time_view(source_raw, threshold))
        nv = add_features(evaluate.original_time_view(native_raw, threshold))
        report['confidence_results'][str(threshold)] = [
            compare(sv, nv, mapping, window, feature)
            for window in protocol['evaluate']['windows_inclusive'] for feature in protocol['evaluate']['features']]
    output = ROOT / 'RESULT.json'
    assert not output.exists(), 'preserve earlier result'
    output.write_text(json.dumps(evaluate.metrics.clean(report), ensure_ascii=False, indent=2) + '\n')
    print(output)


if __name__ == '__main__':
    main()
