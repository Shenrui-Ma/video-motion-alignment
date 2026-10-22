"""Frozen CPU-only correspondence diagnosis; writes only its own directory."""
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

import gates

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R60 = BASE / 'h3-observer-visible-segments-r60-20261017'
OLD = BASE / 'h3-timing-ivebench-auto-r55-20261017/audit/observer_known_shift_sensitivity'
VARIANTS = ('original', 'A', 'B', 'AB')
FAMILIES = ('whole_arm', 'upper')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    if not path.resolve().is_relative_to(HERE):
        raise ValueError('write outside owned directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def freeze():
    if (HERE / 'PROTOCOL.json').exists():
        raise FileExistsError('protocol already frozen')
    bindings = []
    def bind(source, relative):
        source = Path(source)
        dest = HERE / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise FileExistsError(dest)
        shutil.copyfile(source, dest)
        bindings.append({'original': str(source), 'path': str(dest.relative_to(HERE)), 'sha256': sha(dest)})
        return str(dest.relative_to(HERE))
    for p in sorted((R60 / 'frozen/r55').rglob('*.py')):
        bind(p, 'frozen/r55/' + str(p.relative_to(R60 / 'frozen/r55')))
    bind(R60 / 'frozen/visible_arm_features.py', 'frozen/visible_arm_features.py')
    bind(R60 / 'segment_features.py', 'frozen/segment_features.py')
    cases = read(R60 / 'frozen/cases.json')['cases']
    tasks = []
    originals = {}
    for c in cases:
        sid = c['source_id']
        source = OLD / 'source_snapshot' / c['source_pose_path']
        assert sha(source) == c['source_pose_sha256']
        originals[sid] = bind(source, f'inputs/{sid}/source.pose.json')
        for shift in (-8, -4, 0, 4, 8):
            target = bind(OLD / 'r55_original' / f'{sid}__shift_{shift}.pose.json', f'inputs/{sid}/shift_{shift}.pose.json')
            prior = {}
            prior['whole_arm'] = bind(OLD / 'r56_arm_only' / f'{sid}__shift_{shift}.scan.json.gz', f'prior/whole_arm/{sid}__shift_{shift}.json.gz')
            prior['upper'] = bind(R60 / 'results/known_shift_upper' / f'{sid}__shift_{shift}__none.scan.json.gz', f'prior/upper/{sid}__shift_{shift}.json.gz')
            tasks.append({'id': f'{sid}__shift_{shift}', 'group': 'known_shift', 'source_id': sid,
                          'target_id': sid, 'source': originals[sid], 'target': target,
                          'valid_frames': c['valid_frame_count'], 'truth_lag': shift, 'prior': prior})
    cycle = read(R60 / 'NEGATIVE_PROTOCOL.json')['pairs']
    cycle_keys = {(x['source_id'], x['target_id']) for x in cycle}
    for group in ('fixed_cycle', 'additional_ordered_pairs'):
        for source in cases:
            for target in cases:
                a, b = source['source_id'], target['source_id']
                if a == b or ((a, b) in cycle_keys) != (group == 'fixed_cycle'):
                    continue
                prior = {}
                if group == 'fixed_cycle':
                    for family, subdir in [('whole_arm', 'cross_case_r56_whole_arm'), ('upper', 'cross_case_upper')]:
                        prior[family] = bind(R60 / 'results' / subdir / f'{a}__{b}.json.gz', f'prior/{family}/{a}__{b}.json.gz')
                tasks.append({'id': a + '__' + b, 'group': group, 'source_id': a, 'target_id': b,
                              'source': originals[a], 'target': originals[b],
                              'valid_frames': min(source['valid_frame_count'], target['valid_frame_count']),
                              'truth_lag': None, 'prior': prior})
    assert Counter(t['group'] for t in tasks) == {'known_shift': 25, 'fixed_cycle': 5, 'additional_ordered_pairs': 15}
    for name in ('PROTOCOL.json', 'NEGATIVE_PROTOCOL.json', 'NEGATIVE_BASELINE_PROTOCOL.json', 'REPORT.md', 'VERIFIED_ALL.json'):
        bind(R60 / name, 'prior/evidence/' + name)
    for name in ('PLAN.txt', 'gates.py', 'study.py', 'test_gates.py'):
        bindings.append({'original': str(HERE / name), 'path': name, 'sha256': sha(HERE / name)})
    protocol = {
        'schema': 'r61-fixed-correspondence-cpu-v1', 'status': 'FROZEN_BEFORE_DATA_EVALUATION',
        'families': list(FAMILIES), 'variants': list(VARIANTS), 'tasks': tasks, 'bindings': bindings,
        'code_and_inputs_bound': True, 'geometry': 'original1312x736x90@24; valid prefix per task; no reindex/interpolation',
        'features': 'Exact frozen R56 arm directions; upper selects R60 indices0,2. No single-forearm experiment.',
        'A': {'search': 'For each original qualified row and each confidence, query target W+lag against source using inherited local_diagnostic over all integer lags[-24,24]; independently re-estimate reverse lag and inherited common-support gain.',
              'domain': 'Whole W+lag must lie inside common valid prefix; otherwise UNKNOWN boundary.',
              'accept': 'Both reverse lags reliable, opposite sign outside ±2, reverse gain>.5; each abs(forward+reverse)<=2; reverse confidence lag disagreement<=2.',
              'not_identity': 'Never obtain reverse lag by transposing or negating the selected forward edge.'},
        'B': {'difference': 'Delta u_b(t)=u_b(t)-u_b(t-1) on adjacent original physical frames. Both endpoints visible; confidence minimum across endpoints; no interpolation. Source pairs use t=a+1..b inside original W.',
              'support': 'For each confidence and each null e=-2..2, same finite bone/time support and min confidence for source/proposal/null; coverage denominator=(window_length-1)*bone_count; ≥.8 coverage and ≥8 nonzero-weight timepoints.',
              'gain': 'min_e[(E_delta(e)-E_delta(original_lag))/max(E_delta(e),1e-8)]>.5 at both confidences; weighted Euclidean difference distance; no derivative lag search.',
              'zero': 'Constant/zero denominator gives zero gain; epsilon1e-8 is numeric convention. No motion-amplitude gate.',
              'units': 'Difference per original frame; original direction residual<=.5 remains upstream, no invented difference residual threshold.'},
        'threshold_origin': 'Original confidence.3/.5, coverage.8,8frames,±24search,±2tolerance,gain>.5 and persistence copied from R55/R56/R60. A reciprocal2 and B gain.5 are declared adaptations, uncalibrated; no Fisher uncertainty guarantee.',
        'policy': 'Filter failed original qualified rows before unchanged signed grouping/persistence. Independent policy per variant/family/task; repeat identical observation at indices0,1 only to test possibleON.',
        'stress_test': 'All remaining15 ordered cross-source pairs fixed before evaluating any result; same5 source videos, secondary stress set not independent data.',
        'denominators': '5 unique sources;25knownshift+5cycle+15additional input pairs;360family×variant×input cells; windows/arms/repeats not independent.',
        'progression_rule': 'No new zero-shiftON or reliable lag error; at least one fewer fixed-cycleON while preserving every originally ON known nonzero cell. Otherwise report tradeoff and no robust-success claim.',
        'limitations': 'Cross-source pairs lack correspondence groundtruth and can share generic gestures. No semantic-certainty claim. No generated trajectory/video improvements measured.',
        'GPU_calls': 0, 'new_pose_calls': 0, 'new_dependencies': 0,
        'created_unix': time.time()}
    write(HERE / 'PROTOCOL.json', protocol)
    write(HERE / 'PROTOCOL_SEAL.json', {'sha256': sha(HERE / 'PROTOCOL.json'), 'sealed_unix': time.time(), 'evaluations_started': False})
    print(json.dumps({'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'tasks': len(tasks), 'bindings': len(bindings)}))


def verify():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('explicit CPU environment required')
    protocol = read(HERE / 'PROTOCOL.json')
    assert sha(HERE / 'PROTOCOL.json') == read(HERE / 'PROTOCOL_SEAL.json')['sha256']
    for binding in protocol['bindings']:
        assert sha(HERE / binding['path']) == binding['sha256'], binding['path']
    return protocol


def load():
    names = ('scan_current_pose', 'pose_domain', 'timing_metrics', 'pairwise_gain', 'physical_tolerance', 'automatic_window_policy')
    if any(n in sys.modules for n in names):
        raise ValueError('fresh CPU process required')
    root = HERE / 'frozen/r55'
    sys.path.insert(0, str(root / 'scripts'))
    package = types.ModuleType('H3AutomaticWindowRouter')
    package.__path__ = [str(root / 'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter'] = package
    import scan_current_pose as scanner
    import automatic_window_policy as policy
    import physical_tolerance as support
    def module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    helper = module('r61_frozen_visible', HERE / 'frozen/visible_arm_features.py')
    segments = module('r61_frozen_segments', HERE / 'frozen/segment_features.py')
    return scanner, policy, support, helper, segments


def prior_equal(task, family, observation, decisions):
    if family not in task['prior']:
        return None
    with gzip.open(HERE / task['prior'][family], 'rt') as f:
        previous = json.load(f)
    for key in ('source_pose_sha256', 'edited_pose_sha256', 'status', 'reasons', 'windows', 'observation_domain'):
        assert observation[key] == previous['observation'][key], (task['id'], family, key)
    old_decisions = previous.get('decisions')
    if old_decisions is None:
        old_decisions = previous['policy']['updates']
    assert decisions == old_decisions, (task['id'], family, 'policy')
    return True


def run(family, group):
    protocol = verify()
    scanner, policy, support, helper, segments = load()
    scanner.features = helper.features if family == 'whole_arm' else segments.make(helper, 'upper')
    output = HERE / 'results' / family / group
    output.mkdir(parents=True, exist_ok=False)
    records = []
    begin = time.monotonic()
    for task in [t for t in protocol['tasks'] if t['group'] == group]:
        started = time.monotonic()
        source, target = HERE / task['source'], HERE / task['target']
        geometry = scanner.Geometry(frames=90, valid_frames=task['valid_frames'])
        observation = scanner.observe(source, target, 0, geometry)
        loaded = {(name, str(c)): scanner.features(scanner.valid_pose(path, geometry), geometry, c)
                  for name, path in [('source', source), ('target', target)] for c in (.3, .5)}
        deltas = {k: gates.differences(v) for k, v in loaded.items()}
        checks = {}
        for i, row in enumerate(observation['windows']):
            if policy.candidate(row, .5) is not None:
                checks[str(i)] = {'A': gates.reverse_gate(loaded, row, geometry.valid_frames, scanner.m, scanner.compare),
                                  'B': gates.difference_gate(deltas, row, support.align)}
        variants, decision_rows = {}, {}
        for variant in VARIANTS:
            rows = gates.filtered(observation['windows'], checks, variant)
            controller = policy.Policy(.5)
            decisions = [controller.update(index, rows) for index in (0, 1)]
            assert not decisions[0]['active']
            qualified = [row for row in rows if policy.candidate(row, .5) is not None]
            reasons = Counter(reason for i, check in checks.items() for gate in ('A', 'B')
                              if gate in variant for reason in check[gate]['reasons'])
            truth = task['truth_lag']
            wrong = sum(any(v != truth for v in policy.candidate(row, .5)['lags'].values()) for row in qualified) if truth is not None else None
            variants[variant] = {'ON': decisions[1]['active'], 'qualified_rows': len(qualified),
                                 'selected': decisions[1]['selected'], 'physical_intervals': decisions[1]['physical_intervals'],
                                 'rejected_original_rows': len(checks) - len(qualified), 'gate_reasons': dict(reasons),
                                 'wrong_qualified_rows': wrong}
            decision_rows[variant] = decisions
        old_verified = prior_equal(task, family, observation, decision_rows['original'])
        artifact = output / (task['id'] + '.json.gz')
        data = {'task': task, 'family': family, 'protocol_sha256': sha(HERE / 'PROTOCOL.json'),
                'observation': observation, 'candidate_gates': checks, 'decisions': decision_rows,
                'variants': variants, 'original_prior_verified': old_verified}
        with gzip.open(artifact, 'xt') as f:
            json.dump(scanner.m.clean(data), f, allow_nan=False)
        record = {'task_id': task['id'], 'source_id': task['source_id'], 'target_id': task['target_id'],
                  'truth_lag': task['truth_lag'], 'valid_frames': task['valid_frames'],
                  'original_reliable_rows': sum(row['baseline'] != 'unknown' for row in observation['windows']),
                  'original_unknown_rows': sum(row['baseline'] == 'unknown' for row in observation['windows']),
                  'original_prior_verified': old_verified, 'variants': variants,
                  'artifact': str(artifact.relative_to(HERE)), 'sha256': sha(artifact),
                  'cpu_seconds': time.monotonic() - started}
        records.append(record)
        print(json.dumps({'family': family, 'group': group, 'task': task['id'], 'ON': {v: variants[v]['ON'] for v in VARIANTS}, 'seconds': round(record['cpu_seconds'], 3)}), flush=True)
    verify()
    result = {'schema': 'r61-correspondence-diagnostic-results-v1', 'protocol_sha256': sha(HERE / 'PROTOCOL.json'),
              'family': family, 'group': group, 'input_pairs': len(records), 'independent_source_videos': 5,
              'records': records, 'ON_counts': {v: sum(r['variants'][v]['ON'] for r in records) for v in VARIANTS},
              'cpu_seconds': time.monotonic() - begin, 'GPU_calls': 0, 'new_pose_calls': 0,
              'synthetic_or_cross_source_diagnostic_only': True, 'generated_video_result': False}
    write(output / 'SUMMARY.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--family', choices=FAMILIES)
    parser.add_argument('--group', choices=['known_shift', 'fixed_cycle', 'additional_ordered_pairs'])
    args = parser.parse_args()
    if args.freeze:
        freeze()
    elif args.family and args.group:
        run(args.family, args.group)
    else:
        parser.error('choose freeze or family/group')
