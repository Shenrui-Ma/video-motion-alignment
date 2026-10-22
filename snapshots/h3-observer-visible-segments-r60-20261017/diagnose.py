"""Frozen CPU-only segment sensitivity and existing-trajectory replay."""
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

from segment_features import make, NAMES

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R58 = BASE / 'h3-observer-visible-parts-r58-20261017'
OLD = BASE / 'h3-timing-ivebench-auto-r55-20261017/audit/observer_known_shift_sensitivity'
EXPORTS = {'r55': 'r55_short0210_full20', 'r50': 'r50_chest_prefix17'}
SHIFTS = [-8, -4, 0, 4, 8]
MASKS = {'both_wrists': [9, 10], 'left_wrist': [9]}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def save_gz(path, data):
    with gzip.open(path, 'xt') as f:
        json.dump(data, f, allow_nan=False)
    return {'path': str(Path(path).relative_to(HERE)), 'sha256': sha(path)}


def freeze():
    bindings = []
    def bind(path, dest=None):
        path = Path(path)
        if dest:
            dest = HERE / dest
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
        bindings.append({'original': str(path), 'path': str(dest or path), 'sha256': sha(path)})
    for version in ('r55', 'r50'):
        for path in sorted((R58 / 'frozen' / version).rglob('*.py')):
            bind(path, Path('frozen') / version / path.relative_to(R58 / 'frozen' / version))
    bind(R58 / 'visible_arm_features.py', 'frozen/visible_arm_features.py')
    for version, producer in [('r55', 'h3-timing-ivebench-auto-r55-20261017'),
                              ('r50', 'h3-timing-flexiact-auto-r50-retry-20261017')]:
        bind(BASE / producer / 'extensions/H3TemporalRouter/layout.py', f'frozen/{version}/layout.py')
        binding = read(R58 / 'results' / EXPORTS[version] / 'INPUT_BINDING.json')
        bind(binding['export'])
        exported = read(binding['export'])
        root = Path(binding['export']).parent
        for rel, item in exported['files'].items():
            assert sha(root / rel) == item['sha256']
            bind(root / rel)
    bind(OLD / 'PROTOCOL.json')
    bind(OLD / 'r55_original/SUMMARY.json')
    bind(OLD / 'source_snapshot/configs/protocol.json', 'frozen/cases.json')
    for case in read(HERE / 'frozen/cases.json')['cases']:
        bind(OLD / 'source_snapshot' / case['source_pose_path'])
        for d in SHIFTS:
            bind(OLD / 'r55_original' / f"{case['source_id']}__shift_{d}.pose.json")
    for name in ('PLAN.md', 'diagnose.py', 'segment_features.py', 'test_diagnose.py'):
        bind(HERE / name)
    protocol = {'schema': 'r60-visible-segment-cpu-diagnostic-v1',
                'case_count': 5, 'shifts': SHIFTS, 'families': NAMES,
                'occlusion': {'target_joints_confidence_zero': MASKS, 'shifts': [0, 4],
                              'coordinates_times_identity_unchanged': True},
                'thresholds': read(OLD / 'PROTOCOL.json')['selector'],
                'policy': {'known_shift': 'r55 signed', 'r55_replay': 'r55 signed',
                           'r50_replay': 'r50 delayed-only'},
                'per_family_independent_policy': True,
                'persistence_diagnostic': 'repeat identical observation at0 and1; synthetic only',
                'existing_trajectories': {v: read(R58 / 'results' / p / 'INPUT_BINDING.json')['export']
                                          for v, p in EXPORTS.items()},
                'bindings': bindings, 'GPU_calls': 0, 'new_pose_calls': 0,
                'plan': (HERE / 'PLAN.md').read_text()}
    write(HERE / 'PROTOCOL.json', protocol)
    print(json.dumps({'frozen': True, 'sha256': sha(HERE / 'PROTOCOL.json')}))


def verified():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('Explicit CPU environment required')
    p = read(HERE / 'PROTOCOL.json')
    for b in p['bindings']:
        if sha(b['path']) != b['sha256']:
            raise ValueError('Frozen binding changed: ' + b['path'])
    return p


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


_loaded = False
def load(version):
    global _loaded
    if _loaded:
        raise ValueError('Use a fresh CPU process per diagnostic command')
    _loaded = True
    names = ('scan_current_pose', 'pose_domain', 'timing_metrics', 'pairwise_gain',
             'physical_tolerance', 'automatic_window_policy', 'delayed_window_policy')
    if any(n in sys.modules for n in names):
        raise ValueError('Frozen module namespace is already loaded')
    root = HERE / 'frozen' / version
    sys.path.insert(0, str(root / 'scripts'))
    package = types.ModuleType('H3AutomaticWindowRouter')
    package.__path__ = [str(root / 'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter'] = package
    import scan_current_pose as scanner
    import automatic_window_policy as policy
    helper = module('r60_frozen_arm_features', HERE / 'frozen/visible_arm_features.py')
    layout = module('r60_frozen_layout', root / 'layout.py')
    return scanner, policy, helper, layout


def hide(raw, joints):
    target = copy.deepcopy(raw)
    target['synthetic_visibility_diagnostic'] = {'target_joint_confidence_zero': joints,
                                                 'positions_and_physical_time_unchanged': True}
    for row in target['frames']:
        for person in row['persons']:
            for joint in joints:
                person['coco17_score'][joint] = 0.
    return target


def describe(observation, policy, family, truth=None):
    rows = observation['windows']
    counts = {}
    for feature, parts in NAMES[family].items():
        selected = [r for r in rows if r['feature'] == feature]
        reliable, reasons = [], Counter()
        for row in selected:
            lags = [row['measurements'][c]['reliable_lag_frames'] for c in ('0.3', '0.5')]
            if all(v is not None for v in lags) and abs(lags[0]-lags[1]) <= 2:
                reliable.append(lags)
            for c, d in row['measurements'].items():
                if d['reliable_lag_frames'] is None:
                    reasons[c + ':' + d['status']] += 1
                    for flag in d.get('flags', []):
                        reasons[c + ':' + flag] += 1
            for c, d in row.get('comparison', {}).items():
                if d['status'] == 'unknown':
                    for null in d['null_comparisons']:
                        if null['status'] != 'valid':
                            reasons[c + ':gain:' + null['status']] += 1
        pairs = Counter(tuple(x) for x in reliable)
        qualified = [r for r in selected if policy.candidate(r, .5) is not None]
        counts[feature] = {'segments': parts, 'rows': len(selected),
                          'reliable_lag_pairs': [{'lags': list(k), 'count': v} for k,v in sorted(pairs.items())],
                          'reliable_rows': len(reliable),
                          'wrong_reliable_rows': sum(x != [truth, truth] for x in reliable) if truth is not None else None,
                          'baseline': dict(Counter(r['baseline'] for r in selected)),
                          'qualified_rows': len(qualified), 'rejection_reasons': dict(reasons)}
    return {'status': observation['status'], 'features': counts,
            'qualified_rows': sum(c['qualified_rows'] for c in counts.values()),
            'reliable_rows': sum(c['reliable_rows'] for c in counts.values()),
            'all_UNKNOWN': all(r['baseline'] == 'unknown' for r in rows),
            'window_feature_rows_are_not_independent_samples': True}


def summary_record(observation, policy, family, truth):
    p = policy.Policy(.5)
    decisions = [p.update(i, observation['windows']) for i in (0, 1)]
    return dict(describe(observation, policy, family, truth),
                possible_ON_after_identical_repeat=decisions[1]['active'],
                repetition_decisions=decisions)


def sensitivity(family, occlusion=False):
    verified()
    scanner, policy, helper, _ = load('r55')
    original = scanner.features
    scanner.features = make(helper, family)
    output = HERE / 'results' / (('occlusion_' if occlusion else 'known_shift_') + family)
    output.mkdir(parents=True, exist_ok=False)
    records, start = [], time.monotonic()
    try:
        for case in read(HERE / 'frozen/cases.json')['cases']:
            source = OLD / 'source_snapshot' / case['source_pose_path']
            geometry = scanner.Geometry.from_case(case)
            for d in ([0, 4] if occlusion else SHIFTS):
                target = OLD / 'r55_original' / f"{case['source_id']}__shift_{d}.pose.json"
                for mask in (MASKS if occlusion else ['none']):
                    name = f"{case['source_id']}__shift_{d}__{mask}"
                    base_target = target
                    if occlusion:
                        target = output / (name + '.pose.json')
                        write(target, hide(read(base_target), MASKS[mask]))
                    observation = scanner.observe(source, target, 0, geometry)
                    details = summary_record(observation, policy, family, d)
                    artifact = save_gz(output / (name + '.scan.json.gz'), {'observation': observation,
                                             'decisions': details.pop('repetition_decisions')})
                    record = {'source_id': case['source_id'], 'truth_lag': d, 'mask': mask,
                              'source_pose': str(source), 'source_sha256': sha(source),
                              'target_pose': str(target), 'target_sha256': sha(target),
                              'original_target_sha256': sha(base_target), 'artifact': artifact, **details}
                    records.append(record)
                    target = base_target
        result = {'schema': 'r60-segment-sensitivity-v1', 'family': family,
                  'diagnostic': 'synthetic_visibility_gap' if occlusion else 'known_physical_shift',
                  'independent_source_cases': 5, 'case_cells': len(records), 'records': records,
                  'GPU_calls': 0, 'new_pose_calls': 0, 'cpu_seconds': time.monotonic()-start,
                  'protocol_sha256': sha(HERE / 'PROTOCOL.json')}
        verified()
        write(output / 'SUMMARY.json', result)
        print(json.dumps({'output': str(output), 'seconds': result['cpu_seconds'],
                          'ON_cells': sum(r['possible_ON_after_identical_repeat'] for r in records),
                          'zero_ON_cells': sum(r['possible_ON_after_identical_repeat'] for r in records if r['truth_lag']==0)}))
    finally:
        scanner.features = original


def checked(root, record):
    path = root / record['relative_file']
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or sha(path) != record['sha256']:
        raise ValueError('Bad exported file binding')
    return path


def check_row(root, exported, row, geometry):
    target, reqp, respp = (checked(root, row[k]) for k in ('target_pose', 'request', 'response'))
    req, resp = read(reqp), read(respp)
    assert row['run_id'] == req['run_id'] == exported['run_id']
    assert req['physical_index'] == resp['physical_index'] == row['denoising_index']
    assert resp['request_sha256'] == sha(reqp) and resp['status'] == 'complete'
    for field in ('request_id', 'condition_sha256', 'reference_sha256', 'seed', 'nfe_index', 'sigma'):
        assert req[field] == resp[field], field
    assert req['seed'] == exported['case']['seed']
    assert req['endpoint_file_sha256'] == resp['endpoint_file_sha256'] == row['endpoint_file_sha256']
    assert req['geometry'] == geometry.video_geometry and req['observation_domain'] == geometry.domain_record
    assert resp['pose']['file'] == row['target_pose']['remote_file']
    assert resp['pose']['sha256'] == sha(target)
    assert resp['observer'] == row['observer']
    if row['original_decision_committed']:
        assert row['original_decision']['request_sha256'] == sha(reqp)
        assert row['original_decision']['response_sha256'] == sha(respp)
    return target


def proposal_signature(decision):
    return {'active': decision['active'], 'selected': decision['selected']}


def execution_signature(decision, geometry, layout):
    bins = set()
    for a,b in decision['physical_intervals']:
        if not 0 <= a <= b < geometry.valid_frames:
            raise ValueError('Outside valid physical domain')
        low, high = layout.event_latent_range(a, b, geometry.latent_bins)
        bins.update(range(low, high))
    return {'chosen_full': bool(bins), 'latent_bins': sorted(bins)}


def replay(version, family):
    protocol = verified()
    scanner, policy, helper, layout = load(version)
    index_path = Path(protocol['existing_trajectories'][version])
    exported, root = read(index_path), index_path.parent
    rows = exported['rows']
    assert [r['denoising_index'] for r in rows] == list(range(len(rows)))
    geometry = scanner.Geometry.from_case(exported['case'])
    source = checked(root, exported['source_pose'])
    assert sha(source) == exported['case']['source_pose_sha256']
    original_features = scanner.features
    original_policy, candidate_policy = policy.Policy(.5), policy.Policy(.5)
    first_proposal, first_execution = None, None
    output = HERE / 'results' / f'replay_{version}_{family}'
    output.mkdir(parents=True, exist_ok=False)
    records, start = [], time.monotonic()
    try:
        for row in rows:
            i = row['denoising_index']
            target = check_row(root, exported, row, geometry)
            scanner.features = original_features
            original = scanner.observe(source, target, i, geometry)
            od = original_policy.update(i, original['windows'])
            if original['status'] == 'unknown_visibility':
                od['reason'] = 'unknown_visibility'
            oe = execution_signature(od, geometry, layout)
            if row['original_decision_committed']:
                saved = row['original_decision']
                assert all(saved[k] == v for k,v in od.items()), 'Original complete policy fields differ'
                assert all(saved[k] == v for k,v in oe.items()), 'Original actuation differs'
                assert saved['measurement_status'] == original['status']
                assert saved['measurement_reasons'] == original['reasons']
            scanner.features = make(helper, family)
            candidate = scanner.observe(source, target, i, geometry)
            cd = candidate_policy.update(i, candidate['windows'])
            ce = execution_signature(cd, geometry, layout)
            if first_proposal is None and proposal_signature(od) != proposal_signature(cd):
                first_proposal = i
            if first_execution is None and oe != ce:
                first_execution = i
            artifact = save_gz(output / f'step{i:03}.json.gz', {'original': original, 'candidate': candidate,
                                          'original_decision': od, 'candidate_decision': cd,
                                          'original_execution': oe, 'candidate_execution': ce})
            records.append({'index': i, 'original_committed_verified': row['original_decision_committed'],
                            'original_decision': od, 'candidate_decision': cd, 'original_execution': oe,
                            'candidate_execution': ce, 'candidate_summary': describe(candidate, policy, family),
                            'causal_input_before_step': first_execution is None or i <= first_execution,
                            'artifact': artifact})
        result = {'schema': 'r60-existing-trajectory-replay-v1', 'version': version, 'family': family,
                  'export': str(index_path), 'export_sha256': sha(index_path),
                  'prefix_length': len(rows), 'first_proposal_divergence': first_proposal,
                  'first_execution_divergence': first_execution,
                  'candidate_ON_on_old_trajectory': [r['index'] for r in records if r['candidate_decision']['active']],
                  'records': records, 'new_generated_video': False, 'GPU_calls': 0, 'new_pose_calls': 0,
                  'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'cpu_seconds': time.monotonic()-start,
                  'interpretation': 'After first execution divergence observations remain from original trajectory; no final quality claim.'}
        verified()
        write(output / 'SUMMARY.json', result)
        print(json.dumps({k:v for k,v in result.items() if k != 'records'}))
    finally:
        scanner.features = original_features


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--freeze', action='store_true')
    p.add_argument('--family', choices=['upper','forearm'])
    p.add_argument('--sensitivity', action='store_true')
    p.add_argument('--occlusion', action='store_true')
    p.add_argument('--replay', choices=['r55','r50'])
    a=p.parse_args()
    if a.freeze: freeze()
    elif a.sensitivity: sensitivity(a.family, a.occlusion)
    elif a.replay: replay(a.replay, a.family)
    else: p.error('select one command')
