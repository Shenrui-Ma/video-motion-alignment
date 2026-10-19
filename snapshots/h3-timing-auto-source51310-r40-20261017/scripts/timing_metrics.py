"""Exploratory local pose timing diagnostics, with no whole-clip DTW.

Positive lag means an edited pose occurs AFTER the corresponding source pose.
Signals are 2D body-relative pose estimates, not a learned motion-quality metric.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ARMS = [(5, 7), (7, 9), (6, 8), (8, 10)]
JOINTS = list(range(5, 17))


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(x) for x in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def load_pose(path, threshold=0.3):
    raw = json.loads(Path(path).read_text())
    records = raw['frames']
    xy = np.full((len(records), 17, 2), np.nan)
    conf = np.zeros((len(records), 17))
    for i, record in enumerate(records):
        selected = record['selected_person']
        if selected is not None:
            person = record['persons'][selected]
            xy[i] = person['coco17_xy']
            conf[i] = person['coco17_score']
    return pose_features(xy, conf, np.array([r['time_s'] for r in records]),
                         np.array([r['frame'] for r in records]), raw, threshold)


def pose_features(xy, conf, times, frames, raw, threshold):
    valid = conf >= threshold
    shoulder = (xy[:, 5] + xy[:, 6])/2
    hip = (xy[:, 11] + xy[:, 12])/2
    anchor_valid = valid[:, [5, 6, 11, 12]].all(axis=1)
    torso_length = np.linalg.norm(shoulder - hip, axis=-1)
    scale = float(np.nanmedian(torso_length[anchor_valid])) if anchor_valid.any() else float('nan')
    if not math.isfinite(scale) or scale <= 1e-8:
        raise ValueError('Insufficient reliable torso anchors for scale normalization')
    center = (shoulder + hip)/2
    centered = (xy-center[:, None])/scale
    norm_valid = valid & anchor_valid[:, None]
    centered[~norm_valid] = np.nan
    directions, direction_conf = [], []
    for a, b in ARMS:
        difference = xy[:, b]-xy[:, a]
        length = np.linalg.norm(difference, axis=-1)
        okay = valid[:, a] & valid[:, b] & (length > 1e-8)
        vector = difference / np.maximum(length[:, None], 1e-8)
        vector[~okay] = np.nan
        directions.append(vector)
        direction_conf.append(np.minimum(conf[:, a], conf[:, b]))
    arm_direction = np.stack(directions, axis=1)
    wrist = np.stack(((xy[:, 9]-xy[:, 5])/scale, (xy[:, 10]-xy[:, 6])/scale), axis=1)
    wrist_conf = np.stack((np.minimum(conf[:, 9], conf[:, 5]), np.minimum(conf[:, 10], conf[:, 6])), axis=1)
    wrist[(wrist_conf < threshold) | ~anchor_valid[:, None]] = np.nan
    return {'raw': raw, 'xy': xy, 'conf': conf, 'times': times, 'frames': frames,
            'scale': scale, 'anchor_valid': anchor_valid, 'threshold': threshold,
            'body_xy': centered[:, JOINTS], 'body_conf': conf[:, JOINTS],
            'arm_direction': arm_direction, 'arm_conf': np.stack(direction_conf, axis=1),
            'left_arm_direction': arm_direction[:, :2], 'left_arm_conf': np.stack(direction_conf, axis=1)[:, :2],
            'right_arm_direction': arm_direction[:, 2:], 'right_arm_conf': np.stack(direction_conf, axis=1)[:, 2:],
            'wrist_relative': wrist, 'wrist_conf': wrist_conf,
            'wrist_height': -wrist[..., 1]}


def paired_indices(source, edited, window, lag_frames):
    indices = np.flatnonzero((source['frames'] >= window[0]) & (source['frames'] <= window[1]))
    target = source['times'][indices] + lag_frames/source['raw']['video']['fps']
    right = np.searchsorted(edited['times'], target).clip(0, len(edited['times'])-1)
    left = (right-1).clip(0)
    nearest = np.where(abs(edited['times'][left]-target) < abs(edited['times'][right]-target), left, right)
    max_distance = 0.501/edited['raw']['video']['fps']
    okay = abs(edited['times'][nearest]-target) <= max_distance
    return indices[okay], nearest[okay], len(indices)


def pair_error(source, edited, window, lag, feature):
    si, ei, expected = paired_indices(source, edited, window, lag)
    confidence_name = {'body_xy': 'body_conf', 'arm_direction': 'arm_conf', 'wrist_relative': 'wrist_conf',
                       'left_arm_direction': 'left_arm_conf', 'right_arm_direction': 'right_arm_conf'}[feature]
    a, b = source[feature][si], edited[feature][ei]
    weights = np.minimum(source[confidence_name][si], edited[confidence_name][ei]).clip(0, 1)
    valid = np.isfinite(a).all(axis=-1) & np.isfinite(b).all(axis=-1)
    weights = np.where(valid, weights, 0)
    distance = np.linalg.norm(a-b, axis=-1)
    weighted = np.nan_to_num(distance)*weights
    score = weighted.sum()/weights.sum() if weights.sum() else np.nan
    per_frame = weighted.sum(axis=-1)/np.maximum(weights.sum(axis=-1), 1e-10)
    per_frame[weights.sum(axis=-1) == 0] = np.nan
    coverage = valid.sum()/max(1, expected*a.shape[1])
    return {'lag_frames': lag, 'lag_seconds': lag/source['raw']['video']['fps'],
            'error': score, 'coverage': coverage, 'valid_frame_count': int((weights.sum(axis=-1) > 0).sum()),
            'source_frames': source['frames'][si].tolist(), 'per_frame_error': per_frame.tolist()}


def local_diagnostic(source, edited, window, max_lag, feature):
    curves = [pair_error(source, edited, window, lag, feature) for lag in range(-max_lag, max_lag+1)]
    candidates = [x for x in curves if np.isfinite(x['error']) and x['coverage'] >= 0.8 and x['valid_frame_count'] >= 8]
    same = next(x for x in curves if x['lag_frames'] == 0)
    finite = [x for x in curves if np.isfinite(x['error']) and x['valid_frame_count'] >= 8]
    unconstrained = min(finite, key=lambda x: x['error']) if finite else None
    # Do not silently replace a low-confidence best basin by an unrelated,
    # higher-confidence distant phase. Such a result is not a reliable lag.
    if not candidates or same['coverage'] < 0.8 or unconstrained['coverage'] < 0.8:
        return {'window': window, 'feature': feature, 'status': 'unreliable_detection_coverage',
                'same_frame': same, 'unqualified_best': unconstrained, 'reliable_lag_frames': None, 'curve': curves}
    best = min(candidates, key=lambda x: x['error'])
    # Adjacent lags are expected to form a smooth basin; compare a distinct basin.
    remote = [x for x in candidates if abs(x['lag_frames']-best['lag_frames']) >= 4]
    second = min(remote, key=lambda x: x['error']) if remote else None
    gap = (second['error']-best['error'])/max(best['error'], 1e-8) if second else None
    relative_improvement = (same['error']-best['error'])/max(same['error'], 1e-8)
    flags = []
    if abs(best['lag_frames']) == max_lag:
        flags.append('best_at_search_boundary')
    if gap is not None and gap < 0.05:
        flags.append('flat_or_multiple_matching_phases')
    if relative_improvement < 0.05:
        flags.append('little_gain_over_same_frame')
    # Exploratory quality gate, not a calibrated action-classification threshold.
    # A large residual direction discrepancy cannot be described as mere timing.
    if 'direction' in feature and best['error'] > 0.5:
        flags.append('large_pose_difference_even_after_shift')
    rejected = any(x in flags for x in ('best_at_search_boundary', 'flat_or_multiple_matching_phases',
                                        'large_pose_difference_even_after_shift'))
    if best['lag_frames'] != 0 and relative_improvement < 0.05:
        rejected = True
    return {'window': window, 'feature': feature, 'status': 'exploratory', 'flags': flags,
            'reliable_lag_frames': None if rejected else best['lag_frames'],
            'same_frame': same, 'best': best, 'distinct_lag_runner_up': second,
            'relative_error_reduction_after_local_shift': relative_improvement,
            'distinct_lag_relative_gap': gap, 'curve': curves}


def crossings(pose, side, start, end, hysteresis=0.05):
    """Sustained wrist-above-own-shoulder transitions; no semantic event guessing."""
    y = pose['wrist_height'][:, side]
    result, state, last_stable = [], None, None
    for i in range(len(y)-1):
        if not (start <= pose['frames'][i] <= end):
            continue
        if not np.isfinite(y[i:i+2]).all():
            state, last_stable = None, None
            continue
        next_state = 1 if min(y[i:i+2]) > hysteresis else (-1 if max(y[i:i+2]) < -hysteresis else None)
        if next_state is None:
            continue
        if state is not None and next_state != state:
            between = list(range(last_stable, i+1))
            zero_idx = min(between, key=lambda j: abs(y[j]))
            result.append({'direction': 'rises_above_shoulder' if next_state == 1 else 'falls_below_shoulder',
                           'frame': int(pose['frames'][zero_idx]), 'time_s': float(pose['times'][zero_idx]),
                           'bracket_frames': [int(pose['frames'][last_stable]), int(pose['frames'][i])],
                           'uncertainty_note': 'threshold crossing bracket; pose-estimator and 2D occlusion errors remain'})
        state, last_stable = next_state, i
    return result


def trace_svg(source, edited, path, title, diagnostics):
    """Dependency-free scientific line plot; gaps remain gaps, no interpolation."""
    import html
    width, height = 1200, 760
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="45" y="25" font-family="sans-serif" font-size="18">{html.escape(title)}</text>']
    max_t = min(source['times'][-1], edited['times'][-1])
    def panel(y0, panel_height, datasets, ymin, ymax, label, xmax):
        left, right = 70, 1160
        bottom, top = y0+panel_height, y0
        parts.append(f'<text x="70" y="{top-12}" font-family="sans-serif" font-size="14">{html.escape(label)}</text>')
        for ytick in np.linspace(ymin, ymax, 5):
            yy = bottom-(ytick-ymin)/(ymax-ymin)*panel_height
            parts.append(f'<line x1="{left}" x2="{right}" y1="{yy}" y2="{yy}" stroke="#ddd"/><text x="10" y="{yy+4}" font-size="12">{ytick:.2f}</text>')
        for xtick in np.linspace(0, xmax, 9):
            xx = left+xtick/xmax*(right-left)
            parts.append(f'<text x="{xx-12}" y="{bottom+17}" font-size="12">{xtick:.1f}</text>')
        for x, y, color, name in datasets:
            segment = []
            for xx, yy in zip(x, y):
                if np.isfinite(xx) and np.isfinite(yy) and 0 <= xx <= xmax:
                    segment.append(f'{left+xx/xmax*(right-left):.2f},{bottom-(yy-ymin)/(ymax-ymin)*panel_height:.2f}')
                else:
                    if segment:
                        parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
                    segment = []
            if segment:
                parts.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
        for i, (_, _, color, name) in enumerate(datasets):
            parts.append(f'<text x="{790+i*160}" y="{top-12}" fill="{color}" font-size="13">{html.escape(name)}</text>')
    for side, label in enumerate(('Left wrist height / torso length', 'Right wrist height / torso length')):
        vals = np.concatenate((source['wrist_height'][:, side], edited['wrist_height'][:, side]))
        good = vals[np.isfinite(vals)]
        ymin, ymax = (float(np.min(good))-.1, float(np.max(good))+.1) if len(good) else (-1, 1)
        panel(70+side*225, 165,
              [(source['times'], source['wrist_height'][:, side], '#0072B2', 'Source'),
               (edited['times'], edited['wrist_height'][:, side], '#D55E00', 'Edited')], ymin, ymax, label, max_t)
    first = diagnostics[0]
    curves = first['curve']
    # Offset lag axis to preserve generic plotting routine; labels explicitly state origin.
    lag_min = min(x['lag_frames'] for x in curves)
    xs = np.array([x['lag_frames']-lag_min for x in curves])
    ys = np.array([x['error'] for x in curves])
    good = ys[np.isfinite(ys)]
    panel(520, 165, [(xs, ys, '#009E73', 'Pose error')], 0, max(1e-5, float(good.max())*1.05) if len(good) else 1,
          f"First local window {first['window']}; arm-direction error vs lag; displayed x = lag + {-lag_min}", float(xs.max()))
    parts.append('<text x="70" y="740" font-family="sans-serif" font-size="13">Wrist traces use physical seconds. Positive lag = edited motion later. Gaps are missing confidence, not zero motion.</text></svg>')
    path.write_text('\n'.join(parts))


def self_test():
    n = 150
    x = np.zeros((n, 17, 2))
    x[:, 5], x[:, 6], x[:, 11], x[:, 12] = [-.4, 0], [.4, 0], [-.3, 1], [.3, 1]
    t = np.arange(n)
    for j in (7, 8, 9, 10):
        x[:, j, 0] = np.sin(t*.075+j*.7)+j*.01
        x[:, j, 1] = np.cos(t*.113+j*.2)
    conf = np.ones((n, 17))
    raw = {'video': {'fps': 24}}
    source = pose_features(x, conf, t/24, t, raw, .3)
    delay = 7
    shifted = np.concatenate([x[:1].repeat(delay, axis=0), x[:-delay]])*2.7 + np.array([100, 77])
    edited = pose_features(shifted, conf, t/24, t, raw, .3)
    for feature in ('body_xy', 'arm_direction', 'wrist_relative'):
        diag = local_diagnostic(source, edited, [50, 65], 24, feature)
        assert diag['best']['lag_frames'] == delay, (feature, diag['best'])
        assert diag['best']['error'] < 1e-10
    advanced = np.concatenate([x[5:], x[-1:].repeat(5, axis=0)])
    early = pose_features(advanced, conf, t/24, t, raw, .3)
    assert local_diagnostic(source, early, [50, 65], 24, 'arm_direction')['best']['lag_frames'] == -5
    target_times = np.arange(187)/30
    resampled = np.stack([np.interp(target_times*24-delay, t, x[:, j, axis])
                         for j in range(17) for axis in range(2)], axis=-1).reshape(-1, 17, 2)
    different_fps = pose_features(resampled, np.ones((187, 17)), target_times,
                                  np.arange(187), {'video': {'fps': 30}}, .3)
    assert local_diagnostic(source, different_fps, [50, 65], 24, 'arm_direction')['best']['lag_frames'] == 7
    bad = conf.copy()
    bad[40:100] = 0
    missing = pose_features(shifted, bad, t/24, t, raw, .3)
    assert local_diagnostic(source, missing, [50, 65], 4, 'arm_direction')['status'] == 'unreliable_detection_coverage'
    return {'passed': True, 'tests': ['positive 7-frame known delay', 'negative 5-frame advance',
            '24fps source / 30fps edited physical-time matching',
            'uniform scale/translation invariance', 'missing-confidence rejection']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source')
    parser.add_argument('--edited', action='append', default=[])
    parser.add_argument('--window', action='append', default=[], help='inclusive source frame start:end')
    parser.add_argument('--output-dir')
    parser.add_argument('--max-lag', type=int, default=24)
    parser.add_argument('--confidence', type=float, default=.3)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        if not args.source:
            return
    if not args.source or not args.edited or not args.window or not args.output_dir:
        parser.error('source, edited, window and output-dir are required for measurement')
    windows = [list(map(int, x.split(':'))) for x in args.window]
    source = load_pose(args.source, args.confidence)
    directory = Path(args.output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    for filename in args.edited:
        edited = load_pose(filename, args.confidence)
        diagnostics = [local_diagnostic(source, edited, window, args.max_lag, feature)
                       for window in windows for feature in ('arm_direction', 'wrist_relative', 'body_xy',
                                                            'left_arm_direction', 'right_arm_direction')]
        event_start = max(0, min(x[0] for x in windows)-args.max_lag)
        event_end = max(x[1] for x in windows)+args.max_lag
        events = {name: {side: crossings(pose, i, event_start, event_end) for i, side in enumerate(('left_wrist', 'right_wrist'))}
                  for name, pose in [('source', source), ('edited', edited)]}
        report = {'schema': 'h3_local_pose_timing_v1', 'source': source['raw']['video'], 'edited': edited['raw']['video'],
                  'measurement_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'source_pose_sha256': hashlib.sha256(Path(args.source).read_bytes()).hexdigest(),
                  'edited_pose_sha256': hashlib.sha256(Path(filename).read_bytes()).hexdigest(),
                  'confidence_threshold': args.confidence, 'lag_sign': 'positive means edited motion occurs later',
                  'normalization': 'per-frame shoulder/hip midpoint translation; per-clip median torso length scale; no rotation or reflection',
                  'source_scale_pixels': source['scale'], 'edited_scale_pixels': edited['scale'],
                  'source_detector_statistics': source['raw']['statistics'], 'edited_detector_statistics': edited['raw']['statistics'],
                  'source_anchor_valid_fraction': source['anchor_valid'].mean(), 'edited_anchor_valid_fraction': edited['anchor_valid'].mean(),
                  'diagnostics': diagnostics, 'wrist_shoulder_crossings': events,
                  'limitations': ['2D pose reliability requires visual calibration; confidence is not accuracy',
                                 'body proportions and occlusion can change pose errors after character replacement',
                                 'local best lag is diagnostic and does not excuse same-frame errors',
                                 'threshold crossings are operational geometric events, not hand-labeled action boundaries',
                                 'nearest physical-time frames are paired; no DTW, mirrored-joint matching or post-hoc event remapping']}
        stem = Path(filename).stem.replace('.pose', '')
        path = directory/(stem+f'.threshold{args.confidence:g}.timing.json')
        path.write_text(json.dumps(clean(report), ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        trace_svg(source, edited, path.with_suffix('.svg'), stem, diagnostics)
        print(json.dumps(clean({'report': str(path), 'local_results': [
              {'window': d['window'], 'feature': d['feature'], 'best_lag': d.get('best', {}).get('lag_frames'),
               'reliable_lag': d['reliable_lag_frames'],
               'same_error': d['same_frame']['error'], 'best_error': d.get('best', {}).get('error'),
               'flags': d.get('flags', [d['status']])} for d in diagnostics]})))


if __name__ == '__main__':
    main()
