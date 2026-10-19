"""Supplementary COCO17 leg directions using the frozen timing estimator."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SPEC = json.loads((HERE / 'PROTOCOL.json').read_text())
BASE = Path(SPEC['base_metric_file'])
if hashlib.sha256(BASE.read_bytes()).hexdigest() != SPEC['base_metric_sha256']:
    raise RuntimeError('Frozen metric source changed')
_spec = importlib.util.spec_from_file_location('frozen_r31_timing', BASE)
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)
ALIASES = {'leg_direction': 'arm_direction',
           'left_leg_direction': 'left_arm_direction',
           'right_leg_direction': 'right_arm_direction'}


def leg_view(pose):
    """Reuse the estimator's four-bone interface without modifying its module."""
    result = dict(pose)
    xy, confidence = pose['xy'], pose['conf']
    vectors, weights = [], []
    for start, end in SPEC['coco17_leg_bones']:
        delta = xy[:, end] - xy[:, start]
        length = np.linalg.norm(delta, axis=-1)
        weight = np.minimum(confidence[:, start], confidence[:, end])
        valid = ((weight >= pose['threshold']) & (length > 1e-8)
                 & np.isfinite(delta).all(axis=-1))
        vector = delta / np.maximum(length[:, None], 1e-8)
        vector[~valid] = np.nan
        vectors.append(vector)
        weights.append(weight)
    result['arm_direction'] = np.stack(vectors, axis=1)
    result['arm_conf'] = np.stack(weights, axis=1)
    for side, selection in [('left', slice(0, 2)), ('right', slice(2, 4))]:
        result[f'{side}_arm_direction'] = result['arm_direction'][:, selection]
        result[f'{side}_arm_conf'] = result['arm_conf'][:, selection]
    return result


def diagnostic(source, edited, window, feature, max_lag=24):
    if source is None or edited is None:
        return {'anatomical_feature': feature,
                'estimator_interface_alias': ALIASES[feature],
                'diagnostic': {'window': window, 'status': 'unknown_visibility',
                               'reason': 'frozen parent could not establish reliable torso anchors',
                               'reliable_lag_frames': None}}
    original = metrics.local_diagnostic(source, edited, window, max_lag, ALIASES[feature])
    return {'anatomical_feature': feature,
            'estimator_interface_alias': ALIASES[feature],
            'diagnostic': metrics.clean(original)}


def summarize(row03, row05):
    a = row03['diagnostic']['reliable_lag_frames']
    b = row05['diagnostic']['reliable_lag_frames']
    if a is None or b is None or abs(a - b) > 2:
        return 'UNKNOWN'
    if a > 2 and b > 2:
        return 'delayed_candidate'
    if a < -2 and b < -2:
        return 'advanced_candidate'
    if abs(a) <= 2 and abs(b) <= 2:
        return 'aligned'
    return 'UNKNOWN'


def windows(frame_count):
    result = []
    for length in SPEC['whole_scan_lengths']:
        if frame_count < length:
            continue
        starts = sorted(set(range(0, frame_count - length + 1, SPEC['stride']))
                        | {frame_count - length})
        result.extend([[start, start + length - 1] for start in starts])
    return result


def compare(source_path, targets):
    """No decoder/model call; consumes separately verified immutable pose files."""
    loaded = {}
    def load(path, threshold):
        try:
            return leg_view(metrics.load_pose(path, threshold))
        except ValueError as exc:
            if str(exc) != 'Insufficient reliable torso anchors for scale normalization':
                raise
            return None
    for threshold in SPEC['confidence_thresholds']:
        source = load(source_path, threshold)
        poses = {name: load(path, threshold)
                 for name, path in targets.items()}
        for pose in [source, *poses.values()]:
            if pose is not None and not np.array_equal(pose['frames'], np.arange(141)):
                raise ValueError('Expected exact 141-frame physical grid')
        loaded[threshold] = (source, poses)
    scans, fixed = {}, {}
    for name in targets:
        rows = []
        for window in windows(141):
            for feature in ALIASES:
                pair = [diagnostic(source, poses[name], window, feature)
                        for source, poses in loaded.values()]
                rows.append({'window': window, 'feature': feature,
                             'status': summarize(*pair),
                             'thresholds': dict(zip(('0.3', '0.5'), pair))})
        scans[name] = {'rows': rows, 'counts': {
            status: sum(row['status'] == status for row in rows)
            for status in ('delayed_candidate', 'advanced_candidate', 'aligned', 'UNKNOWN')}}
        fixed[name] = {str(c): [diagnostic(source, poses[name], window, feature)
                     for window in SPEC['fixed_physical_windows'] for feature in ALIASES]
                     for c, (source, poses) in loaded.items()}
    common = {}
    for threshold, (source, poses) in loaded.items():
        if source is None or any(pose is None for pose in poses.values()):
            common[str(threshold)] = {'status': 'unknown_visibility', 'rows': [],
                                     'reason': 'missing reliable torso anchors in at least one input'}
            continue
        rows = []
        for feature, alias in ALIASES.items():
            confidence_key = alias.replace('_direction', '_conf')
            a = source[alias]
            valid = np.isfinite(a).all(axis=-1)
            weights = source[confidence_key].clip(0, 1)
            for pose in poses.values():
                valid &= np.isfinite(pose[alias]).all(axis=-1)
                weights = np.minimum(weights, pose[confidence_key].clip(0, 1))
            weights = np.where(valid, weights, 0)
            denominator = weights.sum()
            errors = {}
            for name, pose in poses.items():
                distance = np.linalg.norm(a - pose[alias], axis=-1)
                errors[name] = (np.nan_to_num(distance) * weights).sum() / denominator if denominator else None
            rows.append({'feature': feature, 'region': 'whole_clip',
                         'status': 'usable_exploratory' if valid.mean() >= .8 else 'insufficient_common_support',
                         'common_valid_fraction': valid.mean(),
                         'common_valid_mask': valid.tolist(),
                         'common_weights': weights.tolist(),
                         'same_frame_errors': errors})
        common[str(threshold)] = metrics.clean(rows)
    return {'fixed': fixed, 'whole_scan': scans, 'common_support': common,
            'scope': SPEC['primary_scope'],
            'overlapping_windows_are_not_independent_samples': True}
