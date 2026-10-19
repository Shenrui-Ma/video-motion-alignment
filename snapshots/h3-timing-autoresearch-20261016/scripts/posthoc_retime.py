"""Fixed-band offline pose DTW baseline; NOT a primary evaluation metric.

Creates a new full-length nearest-frame resampling; never modifies source clips.
The pose objective is an optimization diagnostic, not independent validation.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import numpy as np

PARAMETERS = {'band_frames': 20, 'dtw_steps': [[1, 1], [1, 0], [0, 1]],
              'nondiagonal_step_penalty': 0.05, 'smoothing_window': 5,
              'confidence_threshold': 0.3, 'minimum_pair_coverage': 0.8,
              'body_coordinate_weight': 0.25, 'missing_feature_cost': 2.0,
              'fixed_endpoints': True, 'resampling': 'nearest original frame; no interpolation'}


def dtw(cost, band=20, penalty=.05):
    n, m = cost.shape
    if n != m:
        raise ValueError('This fixed baseline requires equal frame counts')
    cumulative = np.full_like(cost, np.inf)
    previous = np.full((n, m, 2), -1, dtype=int)
    cumulative[0, 0] = cost[0, 0]
    for i in range(n):
        for j in range(max(0, i-band), min(m, i+band+1)):
            if i == j == 0:
                continue
            choices = []
            if i and j:
                choices.append((cumulative[i-1, j-1], i-1, j-1))
            if i:
                choices.append((cumulative[i-1, j]+penalty, i-1, j))
            if j:
                choices.append((cumulative[i, j-1]+penalty, i, j-1))
            value, pi, pj = min(choices, key=lambda x: x[0])
            cumulative[i, j] = value + cost[i, j]
            previous[i, j] = pi, pj
    if not np.isfinite(cumulative[-1, -1]):
        raise ValueError('No finite endpoint-constrained DTW path')
    path, i, j = [], n-1, m-1
    while i >= 0 and j >= 0:
        path.append((i, j))
        if i == j == 0:
            break
        i, j = previous[i, j]
    path.reverse()
    mean_map = np.array([np.mean([j for ii, j in path if ii == i]) for i in range(n)])
    mean_map[0], mean_map[-1] = 0, m-1
    half = PARAMETERS['smoothing_window']//2
    smooth = np.convolve(np.pad(mean_map, (half, half), mode='edge'),
                         np.ones(PARAMETERS['smoothing_window'])/PARAMETERS['smoothing_window'], mode='valid')
    smooth[0], smooth[-1] = 0, m-1
    integer = np.rint(smooth).astype(int)
    assert (np.diff(integer) >= 0).all()
    assert integer[0] == 0 and integer[-1] == m-1
    assert (np.abs(integer-np.arange(n)) <= band).all()
    return path, mean_map, smooth, integer, float(cumulative[-1, -1])


def self_test():
    n = 40
    identical = np.abs(np.arange(n)[:, None]-np.arange(n)[None, :]).astype(float)
    _, _, _, mapping, _ = dtw(identical)
    assert np.array_equal(mapping, np.arange(n))
    delayed = np.abs(np.arange(n)[:, None]+5-np.arange(n)[None, :]).astype(float)
    _, _, _, mapping, _ = dtw(delayed)
    assert mapping[15] == 20
    assert mapping[0] == 0 and mapping[-1] == n-1
    return {'passed': True, 'tests': ['identity mapping', 'known +5 lag recovers internal map', 'monotonicity, band and endpoints']}


def render_nearest(source_video, mapping, output, fps):
    import cv2
    cv2.setNumThreads(1)
    cap = cv2.VideoCapture(str(source_video))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    if len(frames) != len(mapping):
        raise ValueError('MP4 decoded frame count differs from pose records')
    height, width = frames[0].shape[:2]
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pixel_format', 'bgr24', '-video_size', f'{width}x{height}',
               '-framerate', str(fps), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast',
               '-crf', '16', '-pix_fmt', 'yuv420p', '-threads', '4', '-movflags', '+faststart', str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for index in mapping:
        process.stdin.write(frames[index].tobytes())
    process.stdin.close()
    error = process.stderr.read().decode()
    if process.wait() != 0:
        raise RuntimeError(error)
    check = cv2.VideoCapture(str(output))
    result = {'path': str(output), 'frames': int(check.get(cv2.CAP_PROP_FRAME_COUNT)),
              'fps': check.get(cv2.CAP_PROP_FPS), 'width': int(check.get(cv2.CAP_PROP_FRAME_WIDTH)),
              'height': int(check.get(cv2.CAP_PROP_FRAME_HEIGHT)), 'audio': 'omitted; visual timing baseline',
              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'ffmpeg_command': command}
    check.release()
    assert result['frames'] == len(mapping) and abs(result['fps']-fps) < 1e-6
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-pose')
    p.add_argument('--edited-pose')
    p.add_argument('--output-dir')
    p.add_argument('--render', action='store_true')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        if not args.source_pose:
            return
    if not args.source_pose or not args.edited_pose or not args.output_dir:
        p.error('source-pose, edited-pose, output-dir required')
    spec = importlib.util.spec_from_file_location('timing_metrics', Path(__file__).with_name('timing_metrics.py'))
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    source = metrics.load_pose(args.source_pose, PARAMETERS['confidence_threshold'])
    edited = metrics.load_pose(args.edited_pose, PARAMETERS['confidence_threshold'])
    n = len(source['frames'])
    assert n == len(edited['frames']) == 141
    assert np.array_equal(source['frames'], np.arange(n)) and np.array_equal(edited['frames'], np.arange(n))
    assert source['raw']['video']['fps'] == edited['raw']['video']['fps'] == 24
    cost = np.zeros((n, n))
    coverage = np.zeros((n, n, 2))
    for feature_index, (feature, conf_name, feature_weight) in enumerate([
            ('arm_direction', 'arm_conf', 1), ('body_xy', 'body_conf', PARAMETERS['body_coordinate_weight'])]):
        a, b = source[feature][:, None], edited[feature][None, :]
        valid = np.isfinite(a).all(axis=-1) & np.isfinite(b).all(axis=-1)
        weights = np.minimum(source[conf_name][:, None], edited[conf_name][None, :]).clip(0, 1)
        weights = np.where(valid, weights, 0)
        distances = np.linalg.norm(a-b, axis=-1)
        numerator = (np.nan_to_num(distances)*weights).sum(axis=-1)
        denominator = weights.sum(axis=-1)
        feature_cost = np.divide(numerator, denominator, out=np.full((n, n), PARAMETERS['missing_feature_cost']), where=denominator > 0)
        feature_coverage = valid.mean(axis=-1)
        feature_cost[feature_coverage < PARAMETERS['minimum_pair_coverage']] = PARAMETERS['missing_feature_cost']
        cost += feature_weight * feature_cost
        coverage[..., feature_index] = feature_coverage
    path, raw, smooth, mapping, total = dtw(cost, PARAMETERS['band_frames'], PARAMETERS['nondiagonal_step_penalty'])
    steps = np.diff(mapping)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir/'pair_cost.npy', cost)
    np.save(output_dir/'pair_coverage.npy', coverage)
    with (output_dir/'mapping.csv').open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['source_frame', 'dtw_mean_target', 'smoothed_target', 'selected_original_target_frame', 'offset_frames'])
        for i in range(n):
            writer.writerow([i, raw[i], smooth[i], int(mapping[i]), int(mapping[i]-i)])
    stats = {'source_frames': n, 'output_frames': n, 'fixed_endpoints': [int(mapping[0]), int(mapping[-1])],
             'monotone': bool((steps >= 0).all()), 'maximum_absolute_band_offset': int(abs(mapping-np.arange(n)).max()),
             'repeated_adjacent_target_frames': int((steps == 0).sum()),
             'unique_target_frames_used': len(set(mapping.tolist())), 'unused_target_frame_count': n-len(set(mapping.tolist())),
             'unused_target_frames': sorted(set(range(n))-set(mapping.tolist())),
             'more_than_one_frame_steps': int((steps > 1).sum()), 'maximum_target_step': int(steps.max()),
             'dtw_path_length': len(path), 'dtw_total_optimization_cost': total,
             'mean_diagonal_pose_objective': float(np.diag(cost).mean()),
             'mean_retimed_pose_objective': float(cost[np.arange(n), mapping].mean()),
             'retimed_joint_coverage_mean_arms_body': coverage[np.arange(n), mapping].mean(axis=0).tolist(),
             'retimed_frames_below_80pct_arms_body_coverage': (coverage[np.arange(n), mapping] < .8).sum(axis=0).tolist()}
    result = {'parameters_preregistered': PARAMETERS, 'source': source['raw']['video'], 'edited': edited['raw']['video'],
              'source_pose_sha256': hashlib.sha256(Path(args.source_pose).read_bytes()).hexdigest(),
              'edited_pose_sha256': hashlib.sha256(Path(args.edited_pose).read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'statistics': stats, 'path': path, 'raw_mean_mapping': raw.tolist(),
              'smooth_mapping': smooth.tolist(), 'integer_mapping': mapping.tolist(),
              'critical_limitation': 'Same pose information defines optimization and objective; lower pose cost is circular and NOT independent validation. Full-video continuity and event correctness require human/independent evaluation.'}
    if args.render:
        result['rendered_video'] = render_nearest(Path(edited['raw']['video']['path']), mapping,
                                                 output_dir/'old_sam05_posthoc_dtw_nn_full.mp4', 24)
    (output_dir/'retiming_result.json').write_text(json.dumps(metrics.clean(result), indent=2, allow_nan=False)+'\n')
    print(json.dumps({'output_dir': str(output_dir), 'statistics': stats, 'rendered': result.get('rendered_video')}))


if __name__ == '__main__':
    main()
