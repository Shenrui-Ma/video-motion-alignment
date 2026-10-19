"""Compare same-frame pose errors using identical valid support across methods.

Separate from best-lag diagnostics: missing difficult joints cannot improve an
arm's score simply by disappearing from its denominator.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--run', action='append', required=True, help='label=pose_json_path')
    p.add_argument('--window', action='append', default=[])
    p.add_argument('--confidence', type=float, default=.3)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    module_path = root/'scripts/timing_metrics.py'
    spec = importlib.util.spec_from_file_location('timing_metrics', module_path)
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    source = metrics.load_pose(args.source, args.confidence)
    runs = {label: metrics.load_pose(path, args.confidence)
            for label, path in (value.split('=', 1) for value in args.run)}
    windows = [list(map(int, value.split(':'))) for value in args.window or ['50:65', '69:81', '80:92', '99:111']]
    results = []
    for window in windows:
        for feature in ('arm_direction', 'wrist_relative', 'body_xy', 'left_arm_direction', 'right_arm_direction'):
            conf_name = {'arm_direction': 'arm_conf', 'wrist_relative': 'wrist_conf', 'body_xy': 'body_conf',
                         'left_arm_direction': 'left_arm_conf', 'right_arm_direction': 'right_arm_conf'}[feature]
            si = np.flatnonzero((source['frames'] >= window[0]) & (source['frames'] <= window[1]))
            paired = {}
            for label, run in runs.items():
                source_indices, target_indices, _ = metrics.paired_indices(source, run, window, 0)
                if not np.array_equal(si, source_indices):
                    raise ValueError('Runs must cover the same complete source-window time support')
                paired[label] = target_indices
            a = source[feature][si]
            valid = np.isfinite(a).all(axis=-1)
            weights = source[conf_name][si].clip(0, 1)
            for label, run in runs.items():
                ti = paired[label]
                valid &= np.isfinite(run[feature][ti]).all(axis=-1)
                weights = np.minimum(weights, run[conf_name][ti].clip(0, 1))
            weights = np.where(valid, weights, 0)
            denominator = weights.sum()
            row = {'window': window, 'feature': feature, 'common_valid_fraction': valid.mean(),
                   'common_valid_joint_frames': int(valid.sum()), 'frame_count': len(si), 'runs': {}}
            for label, run in runs.items():
                distance = np.linalg.norm(a-run[feature][paired[label]], axis=-1)
                error = np.nan_to_num(distance)*weights
                row['runs'][label] = {
                    'same_frame_error_on_common_support': error.sum()/denominator if denominator else None,
                    'per_source_frame_error': np.divide(error.sum(axis=-1), weights.sum(axis=-1),
                        out=np.full(len(si), np.nan), where=weights.sum(axis=-1) > 0).tolist()}
            row['status'] = 'usable_exploratory' if valid.mean() >= .8 else 'insufficient_common_support'
            results.append(row)
    report = {'source': source['raw']['video'], 'runs': {k: v['raw']['video'] for k, v in runs.items()},
              'confidence_threshold': args.confidence, 'same_support_policy': 'intersection of valid source and every compared method; shared min-confidence weights',
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'metrics_script_sha256': hashlib.sha256(module_path.read_bytes()).hexdigest(), 'results': results,
              'limitations': ['exploratory comparison, not a significance test', 'pose preservation alone does not measure edit success or identity leakage']}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(metrics.clean(report), indent=2, allow_nan=False)+'\n')
    print(json.dumps(metrics.clean({'saved': str(destination), 'primary': [row for row in results if row['feature'] == 'arm_direction']})))


if __name__ == '__main__':
    main()
