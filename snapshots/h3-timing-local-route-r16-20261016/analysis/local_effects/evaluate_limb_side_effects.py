"""Apply frozen pose timing diagnostics to legs and torso; CPU-only side effects.

The original arm diagnostic is reused unchanged through temporary feature views.
Leg directions use hip-knee and knee-ankle edges; torso uses hip-to-shoulder
midpoints. These are exploratory 2D measurements with the original rejection
rules, not independent motion or perceptual ground truth.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import numpy as np

METRICS = Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016/scripts/timing_metrics.py')
METRICS_SHA = 'eebb6893896aca76276ae2e749b8cd44d6efa24ace1cc0fcbbcc9e17cd1b3d8e'
LEGS = ((11, 13), (13, 15), (12, 14), (14, 16))
WINDOWS = ((50, 65), (69, 81), (80, 92), (99, 111))


def load_metrics():
    assert hashlib.sha256(METRICS.read_bytes()).hexdigest() == METRICS_SHA
    spec = importlib.util.spec_from_file_location('frozen_timing_metrics', METRICS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def feature_view(pose, feature):
    xy, conf = pose['xy'], pose['conf']
    if feature == 'leg_direction':
        vectors = np.stack([xy[:, b] - xy[:, a] for a, b in LEGS], axis=1)
        scores = np.stack([np.minimum(conf[:, a], conf[:, b]) for a, b in LEGS], axis=1)
    elif feature == 'torso_direction':
        vectors = ((xy[:, 5] + xy[:, 6] - xy[:, 11] - xy[:, 12]) / 2)[:, None]
        scores = conf[:, [5, 6, 11, 12]].min(axis=1)[:, None]
    else:
        raise ValueError(feature)
    length = np.linalg.norm(vectors, axis=-1)
    valid = (scores >= pose['threshold']) & (length > 1e-8) & np.isfinite(vectors).all(axis=-1)
    unit = vectors / np.maximum(length[..., None], 1e-8)
    unit[~valid] = np.nan
    # Shallow view only: original pose arrays are never modified.
    return dict(pose, arm_direction=unit, arm_conf=scores)


def evaluate(source_path, edited_path, metric=None):
    metric = metric or load_metrics()
    started = time.perf_counter()
    rows = []
    for threshold in (0.3, 0.5):
        source = metric.load_pose(source_path, threshold)
        edited = metric.load_pose(edited_path, threshold)
        for feature in ('leg_direction', 'torso_direction'):
            a, b = feature_view(source, feature), feature_view(edited, feature)
            for window in WINDOWS:
                result = metric.local_diagnostic(a, b, list(window), 24, 'arm_direction')
                result['feature'] = feature
                rows.append(dict(threshold=threshold, **result))
    return metric.clean({'source_pose': str(source_path), 'edited_pose': str(edited_path),
                         'source_sha256': hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),
                         'edited_sha256': hashlib.sha256(Path(edited_path).read_bytes()).hexdigest(),
                         'metrics_sha256': METRICS_SHA,
                         'elapsed_seconds': time.perf_counter() - started, 'measurements': rows,
                         'scope': 'Frozen direction/coverage/ambiguity rules, descriptive local side effects.'})


def self_test():
    metric = load_metrics()
    n, lag = 150, 7
    t = np.arange(n)
    xy = np.zeros((n, 17, 2))
    xy[:, 5], xy[:, 6], xy[:, 11], xy[:, 12] = [-.4, 0], [.4, 0], [-.3, 1], [.3, 1]
    for a, b in LEGS:
        angle = .013 * t ** 1.3 + b * .11 + .2 * np.sin(t * .157)
        xy[:, b] = xy[:, a] + np.stack((np.sin(angle), np.cos(angle)), -1)
    conf = np.ones((n, 17))
    raw = {'video': {'fps': 24}}
    a = metric.pose_features(xy.copy(), conf.copy(), t/24, t, raw, .3)
    shifted = np.concatenate((xy[:1].repeat(lag, 0), xy[:-lag])) * 2.7 + [100, 77]
    b = metric.pose_features(shifted, conf.copy(), t/24, t, raw, .3)
    original_xy = a['xy'].copy()
    av, bv = feature_view(a, 'leg_direction'), feature_view(b, 'leg_direction')
    result = metric.local_diagnostic(av, bv, [50, 65], 24, 'arm_direction')
    assert result['reliable_lag_frames'] == lag, result
    assert np.array_equal(a['xy'], original_xy)
    hidden = dict(b, conf=b['conf'].copy())
    hidden['conf'][:, [13, 14, 15, 16]] = .1
    rejected = metric.local_diagnostic(av, feature_view(hidden, 'leg_direction'), [50, 65], 24, 'arm_direction')
    assert rejected['reliable_lag_frames'] is None
    torso = feature_view(a, 'torso_direction')
    constant = metric.local_diagnostic(torso, torso, [50, 65], 24, 'arm_direction')
    assert constant['reliable_lag_frames'] is None
    assert av['arm_direction'].shape == (n, 4, 2)
    assert torso['arm_direction'].shape == (n, 1, 2)
    print(json.dumps({'passed': True, 'known_shift': lag, 'scale_translation_invariance': True,
                      'low_confidence_unknown': True, 'constant_torso_unknown': True,
                      'input_immutable': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--edited', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        if not all((args.source, args.edited, args.output)):
            parser.error('--source, --edited and --output are required')
        result = evaluate(args.source, args.edited)
        with args.output.open('x') as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
