"""Stress-test the frozen local pose phase observer using explicit synthetic signals."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

FROZEN_HASH = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
WINDOWS = [(50, 65), (69, 81), (80, 92), (99, 111)]
FEATURES = ('arm_direction', 'right_arm_direction', 'body_xy', 'wrist_relative')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shift(xy, confidence, delay):
    indices = np.clip(np.arange(len(xy)) - delay, 0, len(xy)-1)
    return xy[indices].copy(), confidence[indices].copy()


def amplitude(xy, factor):
    out = xy.copy()
    for joint, shoulder in ((7, 5), (9, 5), (8, 6), (10, 6)):
        relative = xy[:, joint] - xy[:, shoulder]
        mean = np.nanmean(relative, axis=0)
        out[:, joint] = xy[:, shoulder] + mean + factor * (relative-mean)
    return out


def make_cases(xy, confidence):
    cases = []

    def add(name, family, sx, sc, ex, ec, delay, identifiable=True, parameters=None):
        cases.append(dict(name=name, family=family, source_xy=sx, source_conf=sc,
                          edited_xy=ex, edited_conf=ec, true_delay=delay,
                          identifiable=identifiable, parameters=parameters or {}))

    for delay in (0, -2, 2, -7, 7, -13, 13):
        ex, ec = shift(xy, confidence, delay)
        add(f'shift_{delay:+d}', 'known_shift', xy, confidence, ex, ec, delay)
    for delay in (0, 7):
        ex, ec = shift(xy, confidence, delay)
        right_mask = ec.copy()
        right_mask[30:121, [8, 10]] = 0
        add(f'right_occluded_shift_{delay:+d}', 'confidence_mask', xy, confidence,
            ex, right_mask, delay, parameters={'masked_joints': [8, 10], 'frames': [30, 120]})
        add(f'all_low_shift_{delay:+d}', 'confidence_mask', xy, confidence,
            ex, np.full_like(ec, .1), delay, parameters={'all_scores': .1})
        for fraction in (.1, .35):
            masked = ec.copy()
            rng = np.random.default_rng(20261016)
            mask = rng.random(masked.shape) < fraction
            masked[mask] = 0
            add(f'random_mask_{fraction}_shift_{delay:+d}', 'confidence_mask', xy, confidence,
                ex, masked, delay, parameters={'mask_probability': fraction,
                                             'realized_zero_fraction': float(mask.mean()), 'seed': 20261016})
    for family in ('period20', 'flat'):
        indices = 40 + np.arange(len(xy)) % 20 if family == 'period20' else np.full(len(xy), 55)
        sx, sc = xy[indices].copy(), confidence[indices].copy()
        for delay in (0, 7):
            ex, ec = shift(sx, sc, delay)
            add(f'{family}_shift_{delay:+d}', family, sx, sc, ex, ec, delay, False,
                {'source_index_rule': '40 + t % 20' if family == 'period20' else '55'})
    for factor in (.5, 1.5):
        altered = amplitude(xy, factor)
        for delay in (0, -7, 7):
            ex, ec = shift(altered, confidence, delay)
            add(f'excursion_{factor}_shift_{delay:+d}', 'amplitude_confound', xy, confidence,
                ex, ec, delay, parameters={'excursion_scale': factor,
                    'definition': 'shoulder + temporal_mean_relative + alpha*(relative-temporal_mean_relative)'})
    return cases


def assess(case, result):
    lag = result.get('reliable_lag_frames')
    expected = case['true_delay']
    accepted = lag is not None
    identifiable = case['identifiable']
    return {
        'accepted': accepted,
        'abstained': not accepted,
        'signed_error_frames': lag-expected if accepted and identifiable else None,
        'exact_signed_recovery': bool(lag == expected) if accepted and identifiable else None,
        'within_one_frame': bool(abs(lag-expected) <= 1) if accepted and identifiable else None,
        'within_two_frames': bool(abs(lag-expected) <= 2) if accepted and identifiable else None,
        'wrong_sign': bool(lag*expected < 0) if accepted and identifiable and expected else None,
        'false_phase_alarm': bool(accepted and identifiable and expected == 0 and abs(lag) > 2),
        'unwarranted_unique_phase_on_unidentifiable_signal': bool(accepted and not identifiable),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    metrics_path = Path(__file__).with_name('timing_metrics.py')
    actual_hash = digest(metrics_path)
    if actual_hash != FROZEN_HASH:
        raise RuntimeError(f'Frozen observer changed: {actual_hash}')
    spec = importlib.util.spec_from_file_location('frozen_timing_metrics', metrics_path)
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    source = metrics.load_pose(args.source, .3)
    cases = make_cases(source['xy'], source['conf'])
    records, arrays = [], {}
    for case in cases:
        name = case['name']
        for field in ('source_xy', 'source_conf', 'edited_xy', 'edited_conf'):
            arrays[f'{name}/{field}'] = case[field]
        metadata = {k: v for k, v in case.items() if k not in ('source_xy', 'source_conf', 'edited_xy', 'edited_conf')}
        for threshold in (.3, .5):
            try:
                src = metrics.pose_features(case['source_xy'], case['source_conf'], source['times'],
                                            source['frames'], source['raw'], threshold)
                dst = metrics.pose_features(case['edited_xy'], case['edited_conf'], source['times'],
                                            source['frames'], source['raw'], threshold)
                guard_error = None
            except ValueError as exc:
                guard_error = str(exc)
            for window in WINDOWS:
                for feature in FEATURES:
                    if guard_error:
                        result = {'status': 'unknown_input_normalization_guard', 'error': guard_error,
                                  'reliable_lag_frames': None, 'window': window, 'feature': feature}
                    else:
                        result = metrics.local_diagnostic(src, dst, window, 24, feature)
                    records.append({'case': metadata, 'threshold': threshold, 'window': window,
                                    'feature': feature, 'assessment': assess(case, result), 'diagnostic': result})
    np.savez_compressed(output/'synthetic_coordinates.npz', **arrays)
    metadata = {'source': str(Path(args.source).resolve()), 'source_sha256': digest(args.source),
                'frozen_observer_sha256': actual_hash, 'calibration_code_sha256': digest(__file__),
                'case_count': len(cases), 'diagnostic_count': len(records), 'windows': WINDOWS,
                'thresholds': [.3, .5], 'max_lag_frames': 24,
                'scope': 'coordinate-level toy validity only; not decoded-video observer validity',
                'amplitude_classifier_implemented': False, 'positive_lag': 'edited motion occurs later'}
    (output/'all_results.json').write_text(json.dumps(metrics.clean({'metadata': metadata, 'results': records}), indent=2))
    rows = []
    for record in records:
        diag = record['diagnostic']
        best = diag.get('best') or diag.get('unqualified_best') or {}
        rows.append({'case': record['case']['name'], 'family': record['case']['family'],
                     'true_delay': record['case']['true_delay'], 'identifiable': record['case']['identifiable'],
                     'threshold': record['threshold'], 'window': '-'.join(map(str, record['window'])),
                     'feature': record['feature'], 'best_lag': best.get('lag_frames'),
                     'accepted_lag': diag.get('reliable_lag_frames'), 'status': diag['status'],
                     'flags': '|'.join(diag.get('flags', [])), **record['assessment']})
    with (output/'summary.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    primary = [r for r in rows if r['window'] == '50-65' and r['feature'] == 'arm_direction']
    (output/'primary_results.json').write_text(json.dumps(metrics.clean({'metadata': metadata, 'results': primary}), indent=2))
    print(json.dumps(metrics.clean({'metadata': metadata, 'primary': primary}), indent=2), flush=True)


if __name__ == '__main__':
    main()
