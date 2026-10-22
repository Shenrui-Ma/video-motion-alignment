"""Compare source-only necessary support on the fixed five actual source poses."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import arm_features as candidate

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / 'source_snapshot'
sys.path.insert(0, str(SNAPSHOT / 'scripts'))
import pose_domain
import timing_metrics as metrics

spec = importlib.util.spec_from_file_location('r56_frozen_geometry', SNAPSHOT / 'extensions/H3AutomaticWindowRouter/geometry.py')
geometry_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = geometry_module
spec.loader.exec_module(geometry_module)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def support(features, windows):
    if features is None:
        return []
    rows = []
    for window in windows:
        for feature in ('arm_direction', 'left_arm_direction', 'right_arm_direction'):
            row = metrics.pair_error(features, features, window, 0, feature)
            rows.append({'window': window, 'feature': feature, 'coverage': float(row['coverage']),
                         'valid_frame_count': row['valid_frame_count'],
                         'necessary_support': bool(row['coverage'] >= .8 and row['valid_frame_count'] >= 8)})
    return rows


def qualifying_both(rows):
    return [a for a, b in zip(rows['0.3'], rows['0.5'])
            if a['necessary_support'] and b['necessary_support']]


def main():
    snapshot = json.loads((HERE / 'SOURCE_SNAPSHOT.json').read_text())
    for file in snapshot['files']:
        assert sha(HERE / file['copy']) == file['sha256']
    protocol = json.loads((SNAPSHOT / 'configs/protocol.json').read_text())
    results = []
    for case in protocol['cases']:
        geometry = geometry_module.Geometry.from_case(case)
        pose = SNAPSHOT / case['source_pose_path']
        assert sha(pose) == case['source_pose_sha256']
        raw = pose_domain.validate_pose(pose, geometry)
        windows = list(geometry.windows())
        row = {'pair_id': case['source_id'], 'source_pose_sha256': sha(pose),
               'valid_frames': geometry.valid_frames, 'number_of_windows': len(windows),
               'number_of_window_arm_rows': len(windows)*3, 'original': {}, 'candidate': {},
               'old_feature_status': {}, 'original_six_arm_fields_exact': {}}
        for confidence in (.3, .5):
            new = candidate.features(raw, geometry, confidence)
            try:
                old = pose_domain.features(raw, geometry, confidence)
                for field in candidate.ARM_FIELDS:
                    np.testing.assert_array_equal(old[field], new[field], err_msg=field)
                row['old_feature_status'][str(confidence)] = 'available'
                row['original_six_arm_fields_exact'][str(confidence)] = True
            except ValueError as exc:
                if str(exc) != 'Insufficient reliable torso anchors for scale normalization':
                    raise
                old = None
                row['old_feature_status'][str(confidence)] = str(exc)
                row['original_six_arm_fields_exact'][str(confidence)] = None
            row['original'][str(confidence)] = support(old, windows)
            row['candidate'][str(confidence)] = support(new, windows)
        row['original_usable_rows'] = qualifying_both(row['original'])
        row['candidate_usable_rows'] = qualifying_both(row['candidate'])
        results.append(row)
    report = {'schema': 'h3-arm-only-source-support-candidate-v1',
              'scope': 'Feature-entry applicability check; source-only necessary support, no paired lag decision or generation gain.',
              'connected_to_running_producers': False,
              'fixed_case_denominator': 5,
              'thresholds': {'confidence': [.3, .5], 'minimum_coverage': .8, 'minimum_valid_frames': 8},
              'window_rule': {'lengths': [16, 32], 'stride': 4, 'include_last_start': True},
              'candidate_sha256': sha(HERE / 'arm_features.py'),
              'snapshot_manifest_sha256': sha(HERE / 'SOURCE_SNAPSHOT.json'),
              'cases': results}
    output = HERE / 'FIVE_SOURCE_SUPPORT.json'
    with output.open('x') as file:
        json.dump(report, file, indent=2, allow_nan=False)
        file.write('\n')
    for row in results:
        print(json.dumps({'pair_id': row['pair_id'], 'original': len(row['original_usable_rows']),
                          'candidate': len(row['candidate_usable_rows']), 'all_rows': row['number_of_window_arm_rows']}))
    print('report_sha256=' + sha(output))


if __name__ == '__main__':
    lock = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        main()
