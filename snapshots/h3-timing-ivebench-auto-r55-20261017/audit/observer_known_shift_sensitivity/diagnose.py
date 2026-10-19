"""Fixed source-pose shift diagnostic; no GPU, inference, or tracker calls."""
import argparse
from collections import Counter
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R56 = ROOT.parent / 'h3-observer-local-bones-r56-20261017'
SHIFTS = (-8, -4, 0, 4, 8)
SCRIPTS = ('scan_current_pose.py', 'pose_domain.py', 'timing_metrics.py',
           'pairwise_gain.py', 'physical_tolerance.py', 'automatic_window_policy.py',
           'delayed_window_policy.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def freeze():
    protocol = json.loads((ROOT / 'configs/protocol.json').read_text())
    files = ['configs/protocol.json', 'configs/source_pose_protocol.json']
    files += ['scripts/' + name for name in SCRIPTS]
    files += ['extensions/H3AutomaticWindowRouter/geometry.py']
    files += [c['source_pose_path'] for c in protocol['cases']]
    files += ['configs/parents/' + c['source_id'] + '/source_pose_complete.json' for c in protocol['cases']]
    destination = HERE / 'source_snapshot'
    destination.mkdir(exist_ok=False)
    bindings = []
    for rel in files:
        src, dest = ROOT / rel, destination / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        bindings.append({'original': str(src), 'copy': str(dest.relative_to(HERE)), 'sha256': sha(src)})
    helper = HERE / 'r56_arm_features.py'
    shutil.copyfile(R56 / 'arm_features.py', helper)
    bindings.append({'original': str(R56 / 'arm_features.py'), 'copy': helper.name, 'sha256': sha(helper)})
    for c in protocol['cases']:
        assert sha(ROOT / c['source_pose_path']) == c['source_pose_sha256']
    frozen = {
        'schema': 'r55-known-physical-shift-pose-diagnostic-v1',
        'synthetic_CPU_diagnostic': True, 'GPU_calls': 0, 'new_pose_calls': 0,
        'case_denominator': 5, 'cases': [c['source_id'] for c in protocol['cases']],
        'shifts_frames': list(SHIFTS), 'fps': 24,
        'transformation': 'target physical t contains source content t-d; positive d means target later',
        'valid_mapping': '0 <= t < original valid_frame_count AND 0 <= t-d < original valid_frame_count',
        'out_of_bounds': 'all coordinate and confidence entries zero, selected_person null; ledger records null content index',
        'padding': 'original valid prefix retained; all terminal padding excluded by original Geometry/pose_domain',
        'confidence': 'copy exact raw scores at t-d; no recalibration',
        'selector': protocol['observer'],
        'persistence': 'same observation submitted to fresh signed Policy at index 0 then 1; diagnostic only',
        'versions': {'r55_original': 'exact archived original scan+features+policy',
                     'r56_arm_only': 'optional secondary diagnostic: replace only scanner.features with existing frozen R56 helper'},
        'denominators': '25 case-shift diagnostic cells; overlapping window/feature rows are internal counts, not independent samples',
        'script_sha256': sha(__file__), 'files': bindings,
        'existing_check': (HERE / 'PLAN.md').read_text(),
    }
    save(HERE / 'PROTOCOL.json', frozen)
    print(json.dumps({'frozen': True, 'protocol_sha256': sha(HERE / 'PROTOCOL.json')}))


def verify_sources():
    p = json.loads((HERE / 'PROTOCOL.json').read_text())
    assert sha(__file__) == p['script_sha256']
    for b in p['files']:
        assert sha(HERE / b['copy']) == b['sha256'], b
        assert sha(b['original']) == b['sha256'], b
    return p


def shifted(raw, valid_frames, d):
    """Shift content while keeping original target physical timestamps intact."""
    out = copy.deepcopy(raw)
    out['video'] = {k: v for k, v in raw['video'].items() if k not in ('path', 'sha256')}
    out['video']['path'] = 'SYNTHETIC_POSE_ONLY_NO_VIDEO'
    out['statistics'] = {'synthetic': True, 'copied_detector_statistics_not_applicable': True}
    out['provenance'] = {'synthetic_CPU_diagnostic': True, 'new_pose_estimation': False,
                         'original_pose_provenance': raw.get('provenance')}
    ledger = []
    for t in range(len(raw['frames'])):
        j = t - d
        valid = 0 <= t < valid_frames and 0 <= j < valid_frames
        row = copy.deepcopy(raw['frames'][j if valid else t])
        row['frame'] = raw['frames'][t]['frame']
        row['time_s'] = raw['frames'][t]['time_s']
        if 'decoder_pos_msec' in row:
            row['decoder_pos_msec'] = 1000 * row['time_s']
        if not valid:
            for person in row['persons']:
                person['coco17_xy'] = [[0., 0.] for _ in range(17)]
                person['coco17_score'] = [0.] * 17
                if 'detector_score' in person:
                    person['detector_score'] = 0.
            row['selected_person'] = None
            if 'selection_scores' in row:
                row['selection_scores'] = [0.] * len(row['persons'])
        out['frames'][t] = row
        ledger.append({'target_physical_frame': t, 'target_physical_time_s': row['time_s'],
                       'requested_source_content_index': j, 'source_content_index': j if valid else None,
                       'source_content_time_s': raw['frames'][j]['time_s'] if valid else None,
                       'valid_mask': valid, 'in_original_valid_prefix': t < valid_frames})
    out['synthetic_diagnostic'] = {'shift_frames': d, 'shift_seconds': d / raw['video']['fps'],
                                  'valid_frames': valid_frames, 'ledger': ledger}
    return out


def load_modules():
    snapshot = HERE / 'source_snapshot'
    sys.path.insert(0, str(snapshot / 'scripts'))
    # Pure module import; bypass the unrelated Comfy node registration __init__.
    package = types.ModuleType('H3AutomaticWindowRouter')
    package.__path__ = [str(snapshot / 'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter'] = package
    import scan_current_pose as scanner
    import automatic_window_policy as policy
    return scanner, policy


def summary(observation, policy, d):
    rows = observation['windows']
    eligible = policy.eligible_rows(rows, threshold=.5)
    p = policy.Policy(threshold=.5)
    first, second = p.update(0, rows), p.update(1, rows)
    reliable = []
    unknown_reasons = Counter()
    for row in rows:
        ds = row['measurements']
        values = [ds[c]['reliable_lag_frames'] for c in ('0.3', '0.5')]
        if all(x is not None for x in values) and abs(values[0] - values[1]) <= 2:
            reliable.append({'window': row['window'], 'feature': row['feature'], 'lags': values})
        else:
            for c, measurement in ds.items():
                if measurement['reliable_lag_frames'] is None:
                    unknown_reasons[c + ':' + measurement['status']] += 1
                    for flag in measurement.get('flags', []):
                        unknown_reasons[c + ':' + flag] += 1
    exact = [r for r in reliable if r['lags'] == [d, d]]
    pair_counts = Counter(tuple(r['lags']) for r in reliable)
    s = {'observer_status': observation['status'], 'observer_reasons': observation['reasons'],
         'window_count': len({tuple(r['window']) for r in rows}), 'window_feature_rows': len(rows),
         'baseline_counts': dict(Counter(r['baseline'] for r in rows)),
         'status_counts': dict(Counter(r['status'] for r in rows)),
         'reliable_lag_pairs': [{'lags': list(k), 'row_count': v} for k, v in sorted(pair_counts.items())],
         'reliable_rows': len(reliable), 'exact_groundtruth_rows': len(exact),
         'unknown_rows': sum(r['baseline'] == 'unknown' for r in rows),
         'unknown_measurement_reasons': dict(unknown_reasons),
         'qualified_signed_candidate_rows': len(eligible),
         'first_possible_ON': first['active'], 'second_identical_observation_possible_ON': second['active'],
         'first_reason': first['reason'], 'second_reason': second['reason'],
         'selected_after_repetition': second['selected'],
         'case_result': ('UNKNOWN_GLOBAL_VISIBILITY' if observation['status'] != 'measured' else
                         'RELIABLE_LAG_AVAILABLE' if reliable else 'UNKNOWN_ALL_WINDOW_ROWS')}
    return s, {'observation_indices_for_simulation_only': [0, 1], 'updates': [first, second],
               'reliable_lag_rows': reliable, 'qualified_rows': eligible}


def run(version):
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'explicit CPU-only required'
    frozen = verify_sources()
    scanner, policy = load_modules()
    if version == 'r56_arm_only':
        spec = importlib.util.spec_from_file_location('r56_helper_frozen', HERE / 'r56_arm_features.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        scanner.features = mod.features
    protocol = json.loads((HERE / 'source_snapshot/configs/protocol.json').read_text())
    output = HERE / version
    output.mkdir(exist_ok=False)
    results, start = [], time.monotonic()
    for case in protocol['cases']:
        source = HERE / 'source_snapshot' / case['source_pose_path']
        geometry = scanner.Geometry.from_case(case)
        raw = scanner.valid_pose(source, geometry)
        for d in SHIFTS:
            name = case['source_id'] + '__shift_' + str(d)
            target = output / (name + '.pose.json')
            transformed = shifted(raw, geometry.valid_frames, d)
            save(target, transformed)
            observation = scanner.observe(source, target, 0, geometry)
            details, decisions = summary(observation, policy, d)
            observation['diagnostic_observation_api_index_only'] = observation.pop('physical_index')
            full_path = output / (name + '.scan.json.gz')
            with gzip.open(full_path, 'wt') as f:
                json.dump({'observation': observation, 'policy': decisions}, f, allow_nan=False)
            record = {'source_id': case['source_id'], 'known_lag_frames': d, 'known_lag_seconds': d/24,
                      'version': version, 'valid_frames': geometry.valid_frames,
                      'source_pose_sha256': sha(source), 'target_file': str(target.relative_to(HERE)),
                      'target_sha256': sha(target), 'scan_file': str(full_path.relative_to(HERE)),
                      'scan_sha256': sha(full_path), **details}
            results.append(record)
            print(json.dumps({k: record[k] for k in ['source_id', 'known_lag_frames', 'observer_status',
                'reliable_lag_pairs', 'qualified_signed_candidate_rows', 'second_identical_observation_possible_ON'] }), flush=True)
    verify_sources()
    report = {'schema': 'r55-known-shift-diagnostic-results-v1', 'version': version,
              'synthetic_CPU_diagnostic': True, 'status': 'complete', 'protocol_sha256': sha(HERE / 'PROTOCOL.json'),
              'independent_source_cases': 5, 'case_shift_cells': 25,
              'warning': 'Window/feature rows overlap. Repeated identical observations only test persistence capability. No generated-video or online-performance claim.',
              'GPU_calls': 0, 'new_pose_calls': 0, 'cpu_wall_seconds': time.monotonic() - start,
              'records': results}
    save(output / 'SUMMARY.json', report)
    print(json.dumps({'version': version, 'complete': True, 'seconds': report['cpu_wall_seconds'],
                      'summary_sha256': sha(output / 'SUMMARY.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--run', choices=['r55_original', 'r56_arm_only'])
    args = parser.parse_args()
    if args.freeze:
        freeze()
    elif args.run:
        run(args.run)
    else:
        parser.error('choose --freeze or --run')
