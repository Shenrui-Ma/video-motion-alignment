"""Replay frozen decisions on already-observed poses; no model or GPU calls."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')


def checked_file(root, record):
    path = root / record['relative_file']
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Export path escapes its bound root')
    if sha(path) != record['sha256']:
        raise ValueError('Export content hash differs: ' + str(path))
    return path


def load_modules(version):
    protocol = read(HERE / 'PROTOCOL.json')
    for binding in protocol['source_bindings']:
        if sha(HERE / binding['copy']) != binding['sha256']:
            raise ValueError('Frozen source changed')
    snapshot = HERE / 'frozen' / version
    sys.path.insert(0, str(snapshot / 'scripts'))
    # CPU scanner imports only the geometry submodule, without Comfy node registration.
    package = types.ModuleType('H3AutomaticWindowRouter')
    package.__path__ = [str(snapshot / 'extensions/H3AutomaticWindowRouter')]
    sys.modules['H3AutomaticWindowRouter'] = package
    import scan_current_pose as scanner
    import automatic_window_policy as policy
    spec = importlib.util.spec_from_file_location('visible_arm_features', HERE / 'visible_arm_features.py')
    visible = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(visible)
    return scanner, policy, visible


def decision(policy, index, observation):
    answer = policy.update(index, observation['windows'])
    if observation['status'] == 'unknown_visibility':
        answer['reason'] = 'unknown_visibility'
    return answer


def route_signature(result):
    return {'active': result['active'], 'physical_intervals': result['physical_intervals'],
            'selected': [{'window': row['window'], 'feature': row['feature'],
                          'lags': row['lags']} for row in result['selected']]}


def summary(observation):
    rows = observation['windows']
    return {'status': observation['status'], 'reasons': observation['reasons'],
            'window_feature_rows': len(rows),
            'baseline_counts': dict(Counter(row['baseline'] for row in rows)),
            'status_counts': dict(Counter(row['status'] for row in rows)),
            'part_measurable_rows': {feature: sum(row['feature'] == feature and
                                                row['baseline'] != 'unknown' for row in rows)
                                     for feature in ('arm_direction', 'left_arm_direction', 'right_arm_direction')}}


def run(index_path, version, output):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('Explicit CPU-only environment required')
    index_path = Path(index_path).resolve()
    export_root, exported = index_path.parent, read(index_path)
    if exported['schema'] != 'existing-observer-pose-export-v1':
        raise ValueError('Wrong export schema')
    rows = exported['rows']
    if [row['denoising_index'] for row in rows] != list(range(len(rows))):
        raise ValueError('A contiguous prefix beginning at zero is required')
    if not 1 <= len(rows) <= 20:
        raise ValueError('Invalid observation prefix length')
    scanner, policy_module, visible = load_modules(version)
    original_features = scanner.features
    original_policy, visible_policy = policy_module.Policy(.5), policy_module.Policy(.5)
    geometry = scanner.Geometry.from_case(exported['case'])
    source = checked_file(export_root, exported['source_pose'])
    if sha(source) != exported['case']['source_pose_sha256']:
        raise ValueError('Source pose is not the case-bound reference')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'INPUT_BINDING.json', {'export': str(index_path), 'sha256': sha(index_path),
          'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'script_sha256': sha(__file__),
          'version': version, 'case': exported['case'], 'GPU_calls': 0, 'new_pose_calls': 0})
    summaries, first_divergence, start = [], None, time.monotonic()
    for row in rows:
        index = row['denoising_index']
        target = checked_file(export_root, row['target_pose'])
        request_path = checked_file(export_root, row['request'])
        response_path = checked_file(export_root, row['response'])
        request, response = read(request_path), read(response_path)
        if (row['run_id'] != exported['run_id'] or request['run_id'] != exported['run_id'] or
                request['physical_index'] != index or response['physical_index'] != index or
                response['request_sha256'] != sha(request_path) or response['status'] != 'complete' or
                request['endpoint_file_sha256'] != row['endpoint_file_sha256'] or
                response['endpoint_file_sha256'] != row['endpoint_file_sha256'] or
                request['geometry'] != geometry.video_geometry or
                request['observation_domain'] != geometry.domain_record):
            raise ValueError('Request/response/endpoint/geometry binding differs')
        scanner.features = original_features
        original = scanner.observe(source, target, index, geometry)
        original_decision = decision(original_policy, index, original)
        committed = row['original_decision_committed']
        if committed:
            saved = row['original_decision']
            if (route_signature(saved) != route_signature(original_decision) or
                    saved['reason'] != original_decision['reason'] or
                    saved['measurement_status'] != original['status']):
                raise ValueError('Recomputed original decision differs from committed decision')
        scanner.features = visible.features
        candidate = scanner.observe(source, target, index, geometry)
        candidate_decision = decision(visible_policy, index, candidate)
        if first_divergence is None and route_signature(original_decision) != route_signature(candidate_decision):
            first_divergence = index
        artifact = output / f'step{index:03d}.json.gz'
        payload = {'index': index, 'original': original, 'visible': candidate,
                   'original_decision': original_decision, 'visible_decision': candidate_decision}
        with gzip.open(artifact, 'wt') as file:
            json.dump(payload, file, ensure_ascii=False, allow_nan=False)
        summaries.append({'index': index, 'original_committed_decision_verified': committed,
                          'original': summary(original), 'visible': summary(candidate),
                          'original_decision': original_decision,
                          'visible_decision': candidate_decision,
                          'causal_prefix_before_this_step': first_divergence is None or index <= first_divergence,
                          'artifact': artifact.name, 'sha256': sha(artifact)})
    result = {'schema': 'visible-part-replay-result-v1', 'status': 'complete',
              'source_version': version, 'run_id': exported['run_id'],
              'observed_prefix_length': len(rows), 'first_route_divergence': first_divergence,
              'candidate_ON_indices_on_old_trajectory': [r['index'] for r in summaries if r['visible_decision']['active']],
              'original_ON_indices': [r['index'] for r in summaries if r['original_decision']['active']],
              'GPU_calls': 0, 'new_pose_calls': 0, 'new_generated_video': False,
              'cpu_wall_seconds': time.monotonic() - start, 'records': summaries,
              'interpretation': 'Later observations after first route divergence belong to the original trajectory; no new-method final quality is inferred.'}
    write(output / 'SUMMARY.json', result)
    print(json.dumps({key: value for key, value in result.items() if key != 'records'}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', required=True)
    parser.add_argument('--version', choices=('r55', 'r50'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.index, args.version, args.output)
