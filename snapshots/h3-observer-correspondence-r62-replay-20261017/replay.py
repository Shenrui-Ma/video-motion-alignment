"""CPU replay of fixed R61 vetoes on existing, hash-bound observation histories."""
import argparse
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
BASE = HERE.parent
R60 = BASE / 'h3-observer-visible-segments-r60-20261017'
R61 = BASE / 'h3-observer-correspondence-r61-20261017'
R58 = BASE / 'h3-observer-visible-parts-r58-20261017'
VARIANTS = ('original', 'A', 'B', 'AB')
FAMILIES = ('whole_arm', 'upper')
SPECS = {
    'r55_short0210': ('r55', BASE / 'h3-timing-ivebench-auto-r55-20261017/analysis/postrun/audit/live_pose_export/1792245969261988000/INDEX.json', 20,
        {'whole_arm': R58 / 'results/r55_short0210_full20_v2', 'upper': R60 / 'results/replay_r55_upper'}),
    'r50_chest': ('r50', BASE / 'h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/audit/live_pose_export/1792246528856601000/INDEX.json', 20,
        {'whole_arm': R58 / 'results/r50_chest_full20_v2', 'upper': R60 / 'appendix_r50_full20/results/replay_r50_upper'}),
    'r50_crouch_failed': ('r50', HERE / 'incoming/crouch/INDEX.json', 14, {})}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    if not path.resolve().is_relative_to(HERE):
        raise ValueError('write outside owned directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as file:
        json.dump(value, file, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')


def validate_prefix(exported, expected):
    indices = [r['denoising_index'] for r in exported['rows']]
    if indices != list(range(expected)):
        raise ValueError('complete observations must be the exact contiguous prefix')
    if not all(r['original_decision_committed'] for r in exported['rows']):
        raise ValueError('uncommitted observation is outside this fixed replay')
    failures = exported.get('technical_failures', [])
    if expected == 14:
        if len(failures) != 1 or failures[0]['denoising_index'] != 14 or failures[0]['state'] != 'technical_failure':
            raise ValueError('missing explicit step014 technical failure')
        if failures[0].get('response_exists') is not False or failures[0].get('pose_usable') is not False:
            raise ValueError('technical failure cannot be treated as a usable observation')
        if exported.get('missing_after_failure') != list(range(15, 20)):
            raise ValueError('missing tail must remain unobserved')
    elif failures:
        raise ValueError('complete trajectory unexpectedly has technical failure')


def freeze():
    if (HERE / 'PROTOCOL.json').exists():
        raise FileExistsError('already frozen')
    bindings = []
    def bind(source, relative):
        source, target = Path(source), HERE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        shutil.copyfile(source, target)
        bindings.append({'original': str(source), 'path': relative, 'sha256': sha(target)})
        return relative
    for version in ('r55', 'r50'):
        for path in sorted((R60 / 'frozen' / version).rglob('*.py')):
            bind(path, f'frozen/{version}/' + str(path.relative_to(R60 / 'frozen' / version)))
    bind(R61 / 'gates.py', 'gates.py')
    bind(R61 / 'PROTOCOL.json', 'frozen/R61_PROTOCOL.json')
    bind(R61 / 'PROTOCOL_SEAL.json', 'frozen/R61_PROTOCOL_SEAL.json')
    bind(R60 / 'frozen/visible_arm_features.py', 'frozen/visible_arm_features.py')
    bind(R60 / 'segment_features.py', 'frozen/segment_features.py')
    bind(R58 / 'replay.py', 'frozen/evidence.py')
    trajectories = {}
    for name, (version, path, expected, priors) in SPECS.items():
        exported = read(path)
        validate_prefix(exported, expected)
        if expected == 14:
            failed = exported['technical_failures'][0]
            request_path = path.parent / failed['request_file']
            failure = read(path.parent / failed['failure_file'])
            assert failure['status'] == 'failed' and failure['request_sha256'] == sha(request_path)
            assert read(request_path)['physical_index'] == 14
        bind(path, f'inputs/{name}/INDEX.json')
        for relative, info in exported['files'].items():
            if not relative.endswith('.json') or Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('input export must contain JSON-only contained paths')
            source = path.parent / relative
            assert sha(source) == info['sha256']
            bind(source, f'inputs/{name}/{relative}')
        prior_files = {}
        for family, folder in priors.items():
            prior_files[family] = []
            for i in range(expected):
                prior_files[family].append(bind(folder / f'step{i:03d}.json.gz', f'prior/{name}/{family}/step{i:03d}.json.gz'))
        trajectories[name] = {'version': version, 'index': f'inputs/{name}/INDEX.json',
                              'observed_steps': expected, 'prior_files': prior_files,
                              'case': exported['case'],
                              'state_ledger': [{'index': i, 'state': 'observed_complete' if i < expected else
                                  ('technical_failure' if i == 14 and expected == 14 else 'unobserved_after_failure')}
                                  for i in range(20)]}
    for name in ('PLAN.txt', 'replay.py', 'test_replay.py', 'export_crouch_readonly.py', 'crouch_existing_json.tar.gz'):
        bindings.append({'original': str(HERE / name), 'path': name, 'sha256': sha(HERE / name)})
    protocol = {'schema': 'r62-existing-trajectory-correspondence-replay-v1',
        'status': 'FROZEN_BEFORE_NEW_SCANS', 'created_unix': time.time(), 'trajectories': trajectories,
        'families': FAMILIES, 'variants': VARIANTS, 'bindings': bindings,
        'inherited_gates': 'Exact R61 gates.py, independent reverse±24 with cycle≤2/reverse gain>.5; adjacent-frame differences with gain>.5, no new thresholds.',
        'policies': {'r55': 'signed', 'r50': 'delay-only'},
        'original_meaning': 'Per-family R56wholearm/R60upper without A/B. Actual production separately reconstructed with original torso features and matched to committed history.',
        'persistence': 'Each variant/family/trajectory has independent state; one update per completed physical denoising index. No duplicate observations.',
        'failures': 'step014 crouch is technical failure with no usable response, not scientific UNKNOWN;15..19 unobserved. None enters policy.',
        'routing': 'Compare selected window/feature/lags and actual latent-bin union. Filtered candidate sets may change group representative and add laterON; report additions as well as removals.',
        'causality': 'First route divergence relative to actual production is identified separately per variant; after it, old observations are off-policy. No generated quality inference.',
        'evaluation': 'All54complete observations×2representations×4variants;54committed production steps,3source trajectories. Steps/windows/arms not independent data.',
        'GPU_calls': 0, 'new_pose_calls': 0, 'new_dependencies': 0, 'parameter_tuning': False}
    write(HERE / 'PROTOCOL.json', protocol)
    write(HERE / 'PROTOCOL_SEAL.json', {'sha256': sha(HERE / 'PROTOCOL.json'), 'created_unix': time.time()})
    print(json.dumps({'sha256': sha(HERE / 'PROTOCOL.json'), 'bindings': len(bindings)}))


def verify():
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('explicit CPU environment required')
    protocol = read(HERE / 'PROTOCOL.json')
    assert sha(HERE / 'PROTOCOL.json') == read(HERE / 'PROTOCOL_SEAL.json')['sha256']
    for b in protocol['bindings']:
        assert sha(HERE / b['path']) == b['sha256'], b['path']
    return protocol


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    output = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(output)
    return output


def load(version):
    if 'scan_current_pose' in sys.modules:
        raise RuntimeError('fresh CPU process required')
    root = HERE / 'frozen' / version
    sys.path.insert(0, str(root / 'scripts'))
    package = types.ModuleType('H3AutomaticWindowRouter')
    package.__path__ = [str(root / 'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter'] = package
    import scan_current_pose as scanner
    import automatic_window_policy as policy
    import physical_tolerance as support
    import gates
    visible = module('r62_visible', HERE / 'frozen/visible_arm_features.py')
    segments = module('r62_segments', HERE / 'frozen/segment_features.py')
    evidence = module('r62_evidence', HERE / 'frozen/evidence.py')
    layout = module('r62_layout', root / 'layout.py')
    return scanner, policy, support, gates, visible, segments, evidence, layout


def execution(decision, geometry, layout):
    bins = set()
    for a, b in decision['physical_intervals']:
        if not 0 <= a <= b < geometry.valid_frames:
            raise ValueError('window outside original physical domain')
        lo, hi = layout.event_latent_range(a, b, geometry.latent_bins)
        bins.update(range(lo, hi))
    assert decision['active'] == bool(bins)
    return {'active': bool(bins), 'latent_bins': sorted(bins)}


def divergence(first, index, current, actual):
    if first is None and current != actual:
        first = index
    return first, first is None or index <= first


def compare_prior(path, observation, decision, family):
    with gzip.open(path, 'rt') as file:
        prior = json.load(file)
    key = 'visible' if family == 'whole_arm' else 'candidate'
    for field in observation:
        if field != 'scan_seconds':
            assert observation[field] == prior[key][field], (str(path), field)
    assert decision == prior[key + '_decision'], str(path)


def run(name, family):
    protocol = verify()
    spec = protocol['trajectories'][name]
    exported = read(HERE / spec['index'])
    validate_prefix(exported, spec['observed_steps'])
    scanner, policy, support, gates, visible, segments, evidence, layout = load(spec['version'])
    source_root = (HERE / spec['index']).parent
    source = evidence.checked_file(source_root, exported['source_pose'])
    assert sha(source) == exported['case']['source_pose_sha256']
    geometry = scanner.Geometry.from_case(exported['case'])
    production_features = scanner.features
    candidate_features = visible.features if family == 'whole_arm' else segments.make(visible, 'upper')
    production_policy = policy.Policy(.5)
    controllers = {v: policy.Policy(.5) for v in VARIANTS}
    first = {v: None for v in VARIANTS}
    output = HERE / 'results' / name / family
    output.mkdir(parents=True, exist_ok=False)
    records = []
    started = time.monotonic()
    for row in exported['rows']:
        i = row['denoising_index']
        request_path = evidence.checked_file(source_root, row['request'])
        response_path = evidence.checked_file(source_root, row['response'])
        target = evidence.checked_file(source_root, row['target_pose'])
        request, response = read(request_path), read(response_path)
        assert row['run_id'] == request['run_id'] == exported['run_id']
        assert request['physical_index'] == response['physical_index'] == i
        assert response['request_sha256'] == sha(request_path) and response['status'] == 'complete'
        assert request['endpoint_file_sha256'] == response['endpoint_file_sha256'] == row['endpoint_file_sha256']
        assert request['geometry'] == geometry.video_geometry and request['observation_domain'] == geometry.domain_record
        evidence.check_evidence(row, request, response, target, request_path, response_path)
        scanner.features = production_features
        actual_observation = scanner.observe(source, target, i, geometry)
        actual_decision = evidence.decision(production_policy, i, actual_observation)
        saved = row['original_decision']
        assert actual_decision == {k: saved[k] for k in actual_decision}, (name, i, 'committed_policy')
        assert saved['measurement_status'] == actual_observation['status']
        assert saved['measurement_reasons'] == actual_observation['reasons']
        actual_execution = execution(actual_decision, geometry, layout)
        assert saved['chosen_full'] == actual_execution['active'] and saved['latent_bins'] == actual_execution['latent_bins']
        scanner.features = candidate_features
        observation = scanner.observe(source, target, i, geometry)
        loaded = {(n, str(c)): candidate_features(scanner.valid_pose(p, geometry), geometry, c)
                  for n, p in [('source', source), ('target', target)] for c in (.3, .5)}
        differences = {k: gates.differences(v) for k, v in loaded.items()}
        checks = {}
        for j, candidate_row in enumerate(observation['windows']):
            if policy.candidate(candidate_row, .5) is not None:
                checks[str(j)] = {'A': gates.reverse_gate(loaded, candidate_row, geometry.valid_frames, scanner.m, scanner.compare),
                                  'B': gates.difference_gate(differences, candidate_row, support.align)}
        decisions, variants = {}, {}
        for variant in VARIANTS:
            filtered = gates.filtered(observation['windows'], checks, variant)
            decision = controllers[variant].update(i, filtered)
            executed = execution(decision, geometry, layout)
            first[variant], causal = divergence(first[variant], i, executed, actual_execution)
            decisions[variant] = decision
            variants[variant] = {'ON': decision['active'], 'selected': decision['selected'],
                'physical_intervals': decision['physical_intervals'], 'execution': executed,
                'qualified_rows': sum(policy.candidate(r, .5) is not None for r in filtered),
                'causal_prefix_before_this_step': causal,
                'first_execution_divergence_from_production': first[variant]}
        for variant in VARIANTS:
            variants[variant].update(added_ON_vs_original=decisions[variant]['active'] and not decisions['original']['active'],
                removed_ON_vs_original=decisions['original']['active'] and not decisions[variant]['active'],
                proposal_changed_vs_original=evidence.route_signature(decisions[variant]) != evidence.route_signature(decisions['original']),
                execution_changed_vs_original=variants[variant]['execution'] != variants['original']['execution'])
        prior = spec['prior_files'].get(family)
        if prior is not None:
            compare_prior(HERE / prior[i], observation, decisions['original'], family)
        artifact = output / f'step{i:03d}.json.gz'
        payload = {'index': i, 'state': 'observed_complete', 'request_sha256': sha(request_path),
            'response_sha256': sha(response_path), 'production_observation': actual_observation,
            'production_decision': actual_decision, 'production_execution': actual_execution,
            'observation': observation, 'candidate_gates': checks, 'decisions': decisions, 'variants': variants,
            'prior_original_verified': prior is not None}
        with gzip.open(artifact, 'xt') as file:
            json.dump(scanner.m.clean(payload), file, allow_nan=False)
        records.append({'index': i, 'state': 'observed_complete', 'production_ON': actual_decision['active'],
                        'production_committed_verified': True, 'prior_original_verified': prior is not None,
                        'variants': variants, 'artifact': str(artifact.relative_to(HERE)), 'sha256': sha(artifact)})
        print(json.dumps({'trajectory': name, 'family': family, 'index': i,
                          'ON': {v: variants[v]['ON'] for v in VARIANTS}}), flush=True)
    records.extend({**state, 'policy_updated': False, 'variants': None, 'production_ON': None}
                   for state in spec['state_ledger'] if state['state'] != 'observed_complete')
    verify()
    result = {'schema': 'r62-fixed-existing-trajectory-result-v1', 'trajectory': name, 'family': family,
        'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'input_index_sha256': sha(HERE / spec['index']),
        'observed_steps': spec['observed_steps'], 'total_planned_steps': 20, 'records': records,
        'ON_indices': {v: [r['index'] for r in records if r['variants'] and r['variants'][v]['ON']] for v in VARIANTS},
        'first_execution_divergence_from_production': first,
        'added_ON_indices_vs_original': {v: [r['index'] for r in records if r['variants'] and r['variants'][v]['added_ON_vs_original']] for v in VARIANTS},
        'removed_ON_indices_vs_original': {v: [r['index'] for r in records if r['variants'] and r['variants'][v]['removed_ON_vs_original']] for v in VARIANTS},
        'GPU_calls': 0, 'new_pose_calls': 0, 'new_generated_video': False,
        'cpu_wall_seconds': time.monotonic() - started,
        'interpretation': 'Decisions on frozen production poses. Observations following first execution divergence are off-policy; no video improvement measured.'}
    write(output / 'SUMMARY.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--trajectory', choices=list(SPECS))
    parser.add_argument('--family', choices=FAMILIES)
    args = parser.parse_args()
    if args.freeze:
        freeze()
    elif args.trajectory and args.family:
        run(args.trajectory, args.family)
    else:
        parser.error('choose freeze or trajectory/family')
