"""Explicit one-phase, one-thread, locked offline pilot. No model calls."""
import os
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import argparse
import csv
import fcntl
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
import numpy as np
from partial import double_drop, pair_cost, summarize

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / 'PROTOCOL.json').read_text())
ARMS = ((5, 7), (7, 9), (6, 8), (8, 10))
FEATURES = {'arm_direction': ('arm_conf', slice(None)),
            'left_arm_direction': ('left_arm_conf', slice(0, 2)),
            'right_arm_direction': ('right_arm_conf', slice(2, 4))}
spec = importlib.util.spec_from_file_location('frozen_timing_metrics', PROTOCOL['baseline_file'])
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def save(path, value):
    with Path(path).open('x') as handle:
        json.dump(clean(value), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def sequence(vectors, conf=None):
    vectors = np.asarray(vectors)
    if conf is None:
        conf = np.ones(vectors.shape[:2])
    result = {'frames': np.arange(len(vectors)), 'times': np.arange(len(vectors)) / 24,
              'raw': {'video': {'fps': 24}}}
    for name, (score, subset) in FEATURES.items():
        result[name] = vectors[:, subset]
        result[score] = conf[:, subset]
    return result


def load_pose(path, threshold, last):
    raw = json.loads(Path(path).read_text())
    records = [x for x in raw['frames'] if 0 <= x['frame'] <= last]
    frames = np.array([x['frame'] for x in records])
    if not np.array_equal(frames, np.arange(last + 1)):
        raise ValueError('Expected complete consecutive physical-frame view')
    if raw['video']['fps'] != 24:
        raise ValueError('Only the declared24fps inputs are supported')
    xy = np.full((len(records), 17, 2), np.nan)
    confidence = np.zeros((len(records), 17))
    for i, record in enumerate(records):
        selected = record['selected_person']
        if selected is not None:
            person = record['persons'][selected]
            xy[i] = person['coco17_xy']
            confidence[i] = person['coco17_score']
    directions, scores = [], []
    for a, b in ARMS:
        difference = xy[:, b] - xy[:, a]
        length = np.linalg.norm(difference, axis=-1)
        valid = (confidence[:, a] >= threshold) & (confidence[:, b] >= threshold) & (length > 1e-8)
        unit = difference / np.maximum(length[:, None], 1e-8)
        unit[~valid] = np.nan
        directions.append(unit)
        scores.append(np.minimum(confidence[:, a], confidence[:, b]))
    result = sequence(np.stack(directions, axis=1), np.stack(scores, axis=1))
    result['raw'] = raw
    result['times'] = np.array([r['time_s'] for r in records])
    result['person_selection_ambiguous_frames'] = sum(bool(x.get('selection_ambiguous')) for x in records)
    return result


def windows(length):
    starts = list(range(0, max(1, length - 31), 16))
    if length >= 32 and starts[-1] != length - 32:
        starts.append(length - 32)
    return [[0, length - 1]] + [[i, min(i + 31, length - 1)] for i in starts]


def compact_baseline(result):
    copy = {k: v for k, v in result.items() if k != 'curve'}
    for name in ('same_frame', 'best', 'distinct_lag_runner_up', 'unqualified_best'):
        if copy.get(name):
            copy[name] = {k: v for k, v in copy[name].items() if k not in ('source_frames', 'per_frame_error')}
    return copy


def analyze(source, target, feature, drop=.25, compare=True):
    begin = time.perf_counter()
    score = FEATURES[feature][0]
    a, b = source[feature], target[feature]
    cost, fraction = pair_cost(a, b, source[score], target[score])
    alignment = double_drop(cost, drop, drop)
    result = summarize(alignment, cost, a, b)
    result['drop_cost_each_side'] = drop
    result['partial_seconds'] = time.perf_counter() - begin
    result['window_summaries'] = []
    for window in windows(len(a)):
        lo, hi = window
        lag = np.asarray(result['source_lag_frames'][lo:hi + 1])
        residual = np.asarray(result['source_geometry_residual'][lo:hi + 1])
        okay = np.isfinite(lag)
        item = {'window': window, 'matched_source_fraction': float(okay.mean()),
                'lag_median': float(np.median(lag[okay])) if okay.any() else None,
                'lag_range': [float(lag[okay].min()), float(lag[okay].max())] if okay.any() else None,
                'geometry_residual': float(residual[okay].mean()) if okay.any() else None}
        if compare:
            item['constant_lag24'] = compact_baseline(baseline.local_diagnostic(source, target, window, 24, feature))
            item['constant_lag48'] = compact_baseline(baseline.local_diagnostic(source, target, window, 48, feature))
        result['window_summaries'].append(item)
    result['total_seconds_with_baselines'] = time.perf_counter() - begin
    return result, alignment, cost


def angles_to_vectors(angles):
    return np.stack((np.cos(angles), np.sin(angles)), axis=-1)


def synthetic_cases():
    n = PROTOCOL['synthetic']['frames']
    t = np.arange(n, dtype=float)
    angles = np.stack([.015 * (b + 1) * t + .8 * np.sin(t / (11 + 3 * b) + b)
                       + .65 * np.sin(.0009 * (b + 1) * t * t + b / 2) for b in range(4)], axis=1)
    x = angles_to_vectors(angles)
    rng = np.random.default_rng(PROTOCOL['synthetic']['seed'])
    noise = angles_to_vectors(rng.uniform(-np.pi, np.pi, (n, 4)))
    cases = []

    def add(name, y, mapping=None, source=x, note='known synthetic correspondence'):
        if mapping is None:
            mapping = np.arange(n, dtype=float)
        cases.append({'name': name, 'source': source.copy(), 'target': y.copy(),
                      'truth_target_index_by_source': np.asarray(mapping, dtype=float), 'note': note})

    add('identity', x)
    for d in (-36, -24, -6, 6, 24, 36):
        mapping = np.arange(n, dtype=float) + d
        mapping[(mapping < 0) | (mapping >= n)] = np.nan
        y = noise.copy()
        for i in np.flatnonzero(np.isfinite(mapping)):
            y[int(mapping[i])] = x[i]
        add('shift_' + str(d), y, mapping)
    for d in (-36, 36):
        mapping = np.arange(n, dtype=float) + d
        mapping[(mapping < 0) | (mapping >= n)] = np.nan
        y = np.full_like(x, np.nan)
        for i in np.flatnonzero(np.isfinite(mapping)):
            y[int(mapping[i])] = x[i]
        add('missing_pad_shift_' + str(d), y, mapping)
    mapping = np.arange(n, dtype=float)
    mapping[56:80] = np.nan
    mapping[80:] -= 24
    add('delete_middle24', np.concatenate((x[:56], x[80:])), mapping)
    mapping = np.arange(n, dtype=float)
    mapping[56:] += 24
    add('insert_middle24', np.concatenate((x[:56], noise[:24], x[56:])), mapping)
    # Stretch one interval: source samples56:80 each appear twice.
    y = np.concatenate((x[:56], np.repeat(x[56:80], 2, axis=0), x[80:]))
    mapping = np.arange(n, dtype=float)
    mapping[56:80] = 56 + 2 * np.arange(24) + .5
    mapping[80:] += 24
    add('local_slowdown', y, mapping)
    offsets = np.array([.7, -.55, .6, -.65])
    add('shape_constant_offset', angles_to_vectors(angles + offsets), note='zero time warp, changed angles; must not infer timing-only failure')
    shape = angles.copy()
    shape[56:80] += np.pi
    add('shape_local24', angles_to_vectors(shape), note='zero time warp, interval has incompatible pose geometry')
    add('shape_opposite', -x, note='zero time warp, every bone reversed')
    repeated = angles_to_vectors(np.stack([np.sin(2 * np.pi * t / 24 + b) for b in range(4)], axis=1))
    add('repeated_shift24_unidentifiable', np.roll(repeated, 24, axis=0), source=repeated,
        note='period24: timing origin is unidentifiable from these features; zero residual is not evidence of phase correctness')
    constant = np.tile(x[0], (n, 1, 1))
    add('constant_shift36_unidentifiable', constant, source=constant,
        note='constant motion: no unique timing ground truth; hidden shift36 cannot be identified')
    y = x.copy(); y[56:80] = np.nan
    add('missing_all_bones24', y, note='time remains aligned; visibility absent, not action deletion')
    y = x.copy(); y[56:80, 3] = np.nan
    add('missing_one_bone24', y, note='time remains aligned; one missing bone fails fixed80percent pair support')
    y = x.copy(); y[:, 2:] = np.nan
    add('missing_one_arm_all', y, note='time remains aligned; full-arm descriptor insufficient, left remains observable')
    add('all_missing', np.full_like(x, np.nan), note='no observable target')
    lengths = np.array([.55, 1.7, 1.4, .65])
    scaled = x * lengths[None, :, None]
    scaled /= np.linalg.norm(scaled, axis=-1, keepdims=True)
    add('identity_geometry_only', scaled, note='changed bone lengths erased by unit normalization; no identity or limb-length diagnostic can follow')
    if [c['name'] for c in cases] != PROTOCOL['synthetic']['cases']:
        raise AssertionError('Synthetic case list differs from predeclared protocol')
    return cases


def truth_diagnostics(case, alignment):
    truth = case['truth_target_index_by_source']
    pairs = alignment.pairs
    matched = np.unique(pairs[:, 0])
    expected = np.isfinite(truth)
    observable = np.isfinite(case['source']).all(-1).mean(-1) >= .8
    # Ground-truth targets may be half-indices for repeated samples; nearest frame is allowed.
    target_visible = np.isfinite(case['target']).all(-1).mean(-1) >= .8
    for i in np.flatnonzero(expected):
        j = int(np.floor(truth[i]))
        observable[i] &= 0 <= j < len(target_visible) and target_visible[j]
    observable &= expected
    valid_pairs = expected[pairs[:, 0]] if len(pairs) else np.array([], dtype=bool)
    errors = np.abs(pairs[valid_pairs, 1] - truth[pairs[valid_pairs, 0]])
    unmatched_true = np.flatnonzero(~expected)
    return {
        'pair_abs_time_error_median': float(np.median(errors)) if len(errors) else None,
        'pair_abs_time_error_p95': float(np.quantile(errors, .95)) if len(errors) else None,
        'fraction_pairs_within2frames': float((errors <= 2).mean()) if len(errors) else None,
        'observable_true_source_match_recall': float(np.isin(np.flatnonzero(observable), matched).mean()) if observable.any() else None,
        'true_unmatched_source_recall': float(np.isin(unmatched_true, alignment.source_unmatched).mean()) if len(unmatched_true) else None,
        'matched_pairs_on_true_unmatched_source': int((~valid_pairs).sum()),
        'unique_timing_ground_truth': 'unidentifiable' not in case['name'],
        'note': case['note'],
    }


def prepare():
    project = HERE.parents[1]
    dev = project.parent
    records = project / 'analysis/flexiact_generated_pose158_20261017/records'
    sources = dev / 'h3-timing-flexiact-native-r49-20261017/analysis/source_pose158_sidecar'
    inputs = []
    for name in PROTOCOL['real_cases_order'][:5]:
        generated = list((records / ('native_' + name)).glob('*.pose.json'))
        if len(generated) != 1:
            raise ValueError('Need exactly one archived Native pose for ' + name)
        inputs.append({'id': name, 'source': str(sources / name / ('source_' + name + '_video.pose.json')),
                       'target': str(generated[0]), 'last_frame': 146, 'scope': 'public5 exploratory; no case reranking'})
    r47 = dev / 'h3-timing-new-dance-native-r47-20261017/analysis/postrun/captured/batch'
    for source_id in ('10264579', '6980766'):
        run = 'r47_source_' + source_id + '_seed2026101701_native'
        source = r47 / 'source_pose' / ('source_' + source_id + '_video') / ('source_' + source_id + '_video.pose.json')
        target = r47 / 'final' / run / 'pose' / (run + '_00001_.pose.json')
        if source.exists() and target.exists():
            inputs.append({'id': 'r47_' + source_id, 'source': str(source), 'target': str(target), 'last_frame': 140,
                           'scope': 'exploratory archived Native; original labels retained'})
    for item in inputs:
        for kind in ('source', 'target'):
            path = Path(item[kind])
            raw = json.loads(path.read_text())
            item[kind + '_sha256'] = sha(path)
            item[kind + '_video'] = raw['video']
            item[kind + '_raw_frames'] = len(raw['frames'])
    save(HERE / 'INPUTS.json', {'cases': inputs, 'baseline_sha256': sha(PROTOCOL['baseline_file'])})
    names = ['PROTOCOL.json', 'PRIOR_ART.txt', 'prior_exact_dp.py', 'partial.py', 'test_partial.py', 'pilot.py', 'INPUTS.json']
    save(HERE / 'FREEZE.json', {'files': {name: sha(HERE / name) for name in names}, 'frozen_at_unix': time.time()})
    print(json.dumps({'prepared_cases': [x['id'] for x in inputs]}))


def verify():
    frozen = json.loads((HERE / 'FREEZE.json').read_text())
    for name, digest in frozen['files'].items():
        if sha(HERE / name) != digest:
            raise ValueError('Frozen pilot changed: ' + name)
    inputs = json.loads((HERE / 'INPUTS.json').read_text())
    if sha(PROTOCOL['baseline_file']) != inputs['baseline_sha256']:
        raise ValueError('Baseline implementation changed')
    for item in inputs['cases']:
        for kind in ('source', 'target'):
            if sha(item[kind]) != item[kind + '_sha256']:
                raise ValueError('Input changed: ' + item['id'])
    return inputs


def execute(phase, case_id, attempt):
    verify()
    dest = HERE / 'results' / attempt
    if dest.exists():
        raise FileExistsError('Never overwrite an existing attempt')
    with Path(PROTOCOL['cpu_lock']).open('r') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('CPU_LOCK_BUSY'); return 75
        dest.mkdir(parents=True)
        start = time.perf_counter()
        if phase == 'tests':
            import unittest
            from test_partial import PartialTests
            with (dest / 'tests.log').open('w') as handle:
                result = unittest.TextTestRunner(stream=handle, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PartialTests))
            save(dest / 'COMPLETE.json', {'success': result.wasSuccessful(), 'tests': result.testsRun, 'seconds': time.perf_counter() - start})
            return 0 if result.wasSuccessful() else 1
        rows = []
        if phase == 'synthetic':
            for case in synthetic_cases():
                for drop in (.25, *PROTOCOL['sensitivity_drop_costs']):
                    source, target = sequence(case['source']), sequence(case['target'])
                    metrics, alignment, cost = analyze(source, target, 'arm_direction', drop, compare=drop == .25)
                    metrics['truth'] = truth_diagnostics(case, alignment)
                    metrics['case'] = case['name']
                    save(dest / (case['name'] + '_drop' + str(drop) + '.json'), metrics)
                    np.savez_compressed(dest / (case['name'] + '_drop' + str(drop) + '.npz'),
                                        pairs=alignment.pairs, cost=cost, truth=case['truth_target_index_by_source'])
                    rows.append(metrics)
        else:
            item = next(x for x in json.loads((HERE / 'INPUTS.json').read_text())['cases'] if x['id'] == case_id)
            for threshold in PROTOCOL['pose_confidence_thresholds']:
                source = load_pose(item['source'], threshold, item['last_frame'])
                target = load_pose(item['target'], threshold, item['last_frame'])
                for feature in FEATURES:
                    metrics, alignment, cost = analyze(source, target, feature)
                    metrics.update(case=case_id, confidence_threshold=threshold, feature=feature, input_binding=item)
                    metrics['original_person_selection_ambiguous_frames'] = {'source': source['person_selection_ambiguous_frames'], 'target': target['person_selection_ambiguous_frames']}
                    name = feature + '_c' + str(threshold)
                    save(dest / (name + '.json'), metrics)
                    np.savez_compressed(dest / (name + '.npz'), pairs=alignment.pairs, cost=cost)
                    rows.append(metrics)
        fields = ['case', 'feature', 'confidence_threshold', 'drop_cost_each_side', 'matched_geometry_residual_source_mean',
                  'same_frame_geometry_residual', 'source_unmatched_fraction', 'target_unmatched_fraction',
                  'source_unobservable_fraction', 'target_unobservable_fraction', 'lag_median_frames',
                  'max_targets_per_source', 'max_sources_per_target', 'partial_seconds', 'total_seconds_with_baselines']
        with (dest / 'SUMMARY.csv').open('x') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
            writer.writeheader(); writer.writerows(rows)
        save(dest / 'COMPLETE.json', {'phase': phase, 'case': case_id, 'rows': len(rows), 'seconds': time.perf_counter() - start,
                                    'threads': 1, 'code_freeze_sha256': sha(HERE / 'FREEZE.json')})
        print(json.dumps({'phase': phase, 'case': case_id, 'rows': len(rows), 'seconds': time.perf_counter() - start}))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'tests', 'synthetic', 'real'])
    parser.add_argument('--case')
    parser.add_argument('--attempt', default='attempt001')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare()
    else:
        sys.exit(execute(args.phase, args.case, args.attempt))
