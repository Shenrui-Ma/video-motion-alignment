"""Read-only necessary source support over the actual R55 online scan domain."""
from pathlib import Path
import fcntl
import hashlib
import importlib.util
import json
import sys
import numpy as np

ROOT = Path('/Users/researcher/DevProjects/h3-timing-ivebench-auto-r55-20261017')
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r55_source_geometry', ROOT / 'extensions/H3AutomaticWindowRouter/geometry.py')
geometry_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = geometry_module
spec.loader.exec_module(geometry_module)
sys.path.insert(0, str(ROOT / 'scripts'))
import pose_domain
import timing_metrics as metrics


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


with Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    protocol = json.loads((ROOT / 'configs/protocol.json').read_text())
    results = []
    for case in protocol['cases']:
        path = ROOT / case['source_pose_path']
        assert sha(path) == case['source_pose_sha256']
        geometry = geometry_module.Geometry.from_case(case)
        raw = pose_domain.validate_pose(path, geometry)
        windows = list(geometry.windows())
        row = {'pair_id': case['source_id'], 'source_pose_sha256': sha(path), 'valid_frames': geometry.valid_frames,
               'windows': windows, 'number_of_window_feature_rows': len(windows) * 3, 'confidence_results': {}}
        for confidence in [.3, .5]:
            frames = raw['frames'][:geometry.valid_frames]
            xy = np.full((len(frames), 17, 2), np.nan)
            cf = np.zeros((len(frames), 17))
            for index, frame in enumerate(frames):
                if frame['selected_person'] is not None:
                    person = frame['persons'][frame['selected_person']]
                    xy[index], cf[index] = person['coco17_xy'], person['coco17_score']
            anchor = (cf[:, [5, 6, 11, 12]] >= confidence).all(axis=1)
            support = []
            for a, b in metrics.ARMS:
                length = np.linalg.norm(xy[:, b] - xy[:, a], axis=-1)
                support.append((cf[:, a] >= confidence) & (cf[:, b] >= confidence) & np.isfinite(length) & (length > 1e-8))
            support = np.stack(support, axis=1)
            state = {'torso_anchor_frames': int(anchor.sum()), 'raw_arm_support': [], 'actual_feature_rows': []}
            try:
                features = pose_domain.features(raw, geometry, confidence)
                state['runtime_feature_ready'] = True
            except ValueError as exc:
                assert str(exc) == 'Insufficient reliable torso anchors for scale normalization'
                features = None
                state.update(runtime_feature_ready=False, reason=str(exc))
            for window in windows:
                for feature, indexes in [('arm_direction', slice(None)), ('left_arm_direction', slice(0, 2)), ('right_arm_direction', slice(2, 4))]:
                    mask = support[window[0]:window[1] + 1, indexes]
                    coverage, count = float(mask.mean()), int(mask.any(axis=1).sum())
                    state['raw_arm_support'].append({'window': window, 'feature': feature, 'coverage': coverage,
                                                     'valid_frame_count': count, 'necessary_support': coverage >= .8 and count >= 8})
                    if features is not None:
                        actual = metrics.pair_error(features, features, window, 0, feature)
                        state['actual_feature_rows'].append({'window': window, 'feature': feature, 'coverage': actual['coverage'],
                                                            'valid_frame_count': actual['valid_frame_count'],
                                                            'necessary_support': bool(actual['coverage'] >= .8 and actual['valid_frame_count'] >= 8)})
            row['confidence_results'][str(confidence)] = state
        both = all(row['confidence_results'][str(c)]['runtime_feature_ready'] for c in [.3, .5])
        row['actual_observer_source_ready'] = both
        row['raw_arm_windows_passing_both_confidences'] = [a for a, b in zip(row['confidence_results']['0.3']['raw_arm_support'], row['confidence_results']['0.5']['raw_arm_support']) if a['necessary_support'] and b['necessary_support']]
        row['actual_windows_passing_both_confidences'] = [a for a, b in zip(row['confidence_results']['0.3']['actual_feature_rows'], row['confidence_results']['0.5']['actual_feature_rows']) if a['necessary_support'] and b['necessary_support']] if both else []
        results.append(row)
    output = {'scope': 'Source-only necessary conditions; same-pose support is not a paired lag score or a decision to guide.',
              'producer_protocol_sha256': sha(ROOT / 'configs/protocol.json'),
              'files': {name: sha(ROOT / name) for name in ['scripts/scan_current_pose.py', 'scripts/pose_domain.py', 'scripts/timing_metrics.py', 'extensions/H3AutomaticWindowRouter/geometry.py']},
              'cases': results}
    path = HERE / 'ONLINE_SOURCE_SUPPORT.json'
    with path.open('x') as f:
        json.dump(metrics.clean(output), f, indent=2, allow_nan=False)
    for r in results:
        print(json.dumps({'pair_id': r['pair_id'], 'observer_source_ready': r['actual_observer_source_ready'],
                          'actual_usable_rows': len(r['actual_windows_passing_both_confidences']),
                          'raw_arm_usable_rows': len(r['raw_arm_windows_passing_both_confidences']),
                          'all_rows': r['number_of_window_feature_rows'],
                          'torso_anchor_frames': [r['confidence_results'][str(c)]['torso_anchor_frames'] for c in [.3, .5]]}))
