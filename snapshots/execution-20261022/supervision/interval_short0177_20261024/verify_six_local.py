#!/usr/bin/env python3
"""Read-only local six-arm completion gate; writes a passed receipt only when all pass."""
import argparse
import base64
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time

import collect_completed as collection

HERE = Path(__file__).resolve().parent
EXPECTED_ROOT = '/data4/research-user/h3_runs/interval_short0177_20261024_v3'
SIGMAS = [float(x) for x in '1,0.995633187773,0.990825688073,0.985507246377,0.979591836735,0.972972972973,0.965517241379,0.957055214724,0.947368421053,0.936170212766,0.923076923077,0.90756302521,0.888888888889,0.865979381443,0.837209302326,0.8,0.75,0.679245283019,0.571428571429,0.387096774194,0'.split(',')]
require = collection.require


def probe_video(path, ffprobe='ffprobe'):
    result = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames',
        '-show_entries', 'stream=codec_type,width,height,nb_frames,nb_read_frames,r_frame_rate,avg_frame_rate',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True, timeout=120)
    require(not result.stderr.strip(), 'ffprobe reported video decode errors: ' + result.stderr[-500:])
    streams = json.loads(result.stdout)['streams']
    require(len(streams) == 1, 'Expected one selected video stream')
    stream = streams[0]
    require((stream['width'], stream['height'], int(stream['nb_frames']), int(stream['nb_read_frames'])) ==
            (1312, 736, 73, 73), 'Decoded frame count/geometry mismatch')
    require(Fraction(stream['r_frame_rate']) == Fraction(stream['avg_frame_rate']) == 24, 'Actual video FPS mismatch')
    return stream


def validate_sampling(arm, values):
    a, t, v, r, b = (values[key] for key in ('router', 'timing', 'verified', 'result', 'backend'))
    active = collection.STEPS[arm]
    require('error' not in a, 'Router contains an error')
    require(a['started_calls'] == a['completed_calls'] == a['native_override_calls'] == 1000, 'Incomplete block call totals')
    require(a['calls_by_block'] == [20] * 50 and a['calls_by_forward'] == [50] * 20, 'Block/forward coverage mismatch')
    require(a['routed_by_block'] == [len(active)] * 50, 'Per-block routing mismatch')
    require(a['routed_by_forward'] == [50 if i in active else 0 for i in range(20)], 'Per-forward routing mismatch')
    require(v['routed_blocks'] == a['routed_calls'] == 50 * len(active), 'Verified routing total mismatch')
    require(a['mode'] == ('native' if arm == 'native' else 'mass_preserve'), 'Router mode mismatch')
    require(a['alpha'] == r['metadata']['alpha'] == (.25 if arm == 'global_weak' else 1.), 'Guidance strength mismatch')
    require(a['pixel_interval_inclusive'] == [0, 59] and a['block_interval_half_open'] == [0, 50], 'Routing coverage domain mismatch')
    require(a['expected_sampling_steps'] == 20 and a['backend'] == 'aten._scaled_dot_product_flash_attention.default', 'Attention/sampling backend mismatch')
    require(a['radius'] == 0 and a['time_offset'] == 0 and a['phase_displacement'] == 0, 'Unexpected routing offset')
    require(len(a['forward_summaries']) == 20, 'Incomplete forward summaries')
    for i, item in enumerate(a['forward_summaries']):
        require(item['forward_index'] == i and item['completed_blocks'] == 50 and
                item['routed_blocks'] == (50 if i in active else 0), 'Forward summary mismatch')
        require(item.get('sampled_finite', True) is True, 'Nonfinite sampled router diagnostic')
    require(len(a['sample_sigmas']) == 21 and all(math.isclose(x, y, abs_tol=6e-8, rel_tol=0)
            for x, y in zip(a['sample_sigmas'], SIGMAS)), 'Executed sigma sequence mismatch')
    require(v['valid_frames'] == r['metadata']['valid_frames'] == 60, 'Valid source-frame range mismatch')
    require([x['step'] for x in t['steps']] == list(range(1, 21)), 'Timing step indices mismatch')
    require([x['seconds'] for x in t['steps']] == t['per_step_seconds'], 'Timing step arrays disagree')
    require(math.isfinite(t['sampler_wall_seconds']) and t['sampler_wall_seconds'] > 0, 'Invalid sampler timing')
    mean = sum(t['per_step_seconds']) / 20
    require(math.isclose(mean, t['mean_sampling_step_seconds'], rel_tol=1e-10) and
            math.isclose(mean, v['mean_step_seconds'], rel_tol=1e-10), 'Mean timing mismatch')
    require(r['timing']['sampling_step_seconds'] == t['per_step_seconds'] and
            r['timing']['sampling_seconds'] == t['sampler_wall_seconds'], 'Result timing binding mismatch')
    require(values['backend_contract']['backend'] == 'cuda', 'Expected frozen CUDA contract')
    require(not b['logging_errors'], 'Backend snapshot logging error')
    counts = {kind: sum(op['successful_calls'] for name, op in b['operations'].items() if name.startswith(kind + '.'))
              for kind in ('cuda', 'triton', 'eager')}
    require(counts['cuda'] > 0 and counts['triton'] == counts['eager'] == 0, 'Mixed or fallback INT8 backend')
    require(all(op['failed_calls'] == 0 for op in b['operations'].values()), 'Failed INT8 backend call')
    require(counts['cuda'] >= v['dispatch_process_cumulative_successful_calls']['cuda'], 'Backend snapshot predates verified calls')
    return counts


def validate_graph(arm, path, result):
    graph = json.loads(path.read_text())
    graph = graph.get('prompt', graph)
    digest = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
    require(digest == result['graph_sha256'], 'Local submitted graph differs from result graph SHA')
    def one(kind):
        nodes = [x['inputs'] for x in graph.values() if x.get('class_type') == kind]
        require(len(nodes) == 1, 'Expected one ' + kind)
        return nodes[0]
    require(one('KSamplerSelect')['sampler_name'] == 'euler', 'Sampler is not Euler')
    require(one('RandomNoise')['noise_seed'] == 2026101701, 'Graph seed mismatch')
    require([float(x) for x in one('ManualSigmas')['sigmas'].split(',')] == SIGMAS, 'Graph sigma list changed')
    ref = one('H3StudyReference')
    require((ref['width'], ref['height'], ref['length'], ref['prompt']) ==
            (1312, 736, 73, 'Replace the tiger with a lion'), 'Graph reference/prompt mismatch')
    require(one('CreateVideo')['fps'] == 24, 'Graph FPS mismatch')
    router = one('H3StudySchedule')
    require(router['schedule'] == arm and router['alpha'] == (.25 if arm == 'global_weak' else 1.), 'Graph schedule/alpha mismatch')
    require((router['start_frame'], router['end_frame'], router['block_start'], router['block_end'],
             router['step_start'], router['step_end'], router['radius'], router['time_offset']) ==
            (0, 59, 0, 50, 0, 20, 0, 0), 'Graph routing range mismatch')
    require(one('MiniMaxH3SigmaShift')['shift_video'] == 12 and one('MiniMaxH3SigmaShift')['shift_audio'] == 3, 'Sigma shifts changed')
    require(one('UNETLoader')['unet_name'] == 'minimax_h3_ref2va_pruned_int8_convrot.safetensors', 'UNET model changed')
    require(one('LoadVideo')['file'] == 'short_0177_video.mp4', 'Graph source file changed')
    return {'path': str(path), 'file_sha256': collection.sha_file(path), 'submitted_graph_sha256': digest,
            'sampler': 'euler', 'steps': 20, 'seed': 2026101701}


def validate_local_arm(arm, entry, directory, package, ffprobe):
    item = collection.inspect_existing(directory, arm)
    require(entry['artifacts'] == item['artifacts'], 'Index artifacts differ from immutable COLLECTION receipt')
    require(entry['job_id'] == item['job_id'] and entry['attempt_id'] == item['attempt_id'] and
            entry['cohort'] == collection.COHORT, 'Index identity mismatch')
    for key, artifact in item['artifacts'].items():
        require(entry[key] == artifact['path'], 'Index path mismatch: ' + key)
    require(entry['sha256'] == item['video_sha256'], 'Index video SHA mismatch')
    encoded = {key: {'base64': base64.b64encode(Path(item['artifacts'][key]['path']).read_bytes()).decode(),
                     'remote_path': item['artifacts'][key]['remote_path']} for key in collection.FILES}
    bundle = {'json': encoded, 'video_remote_path': item['artifacts']['video']['remote_path'],
              'video_bytes': item['artifacts']['video']['bytes']}
    _, values = collection.validate_bundle(arm, bundle)
    require(item['video_sha256'] == values['result']['files'][0]['sha256'], 'Collected video differs from raw result SHA')
    counts = validate_sampling(arm, values)
    lane = package / ('gpu' + str(collection.ARMS[arm]))
    graph = validate_graph(arm, lane / 'graphs' / (item['job_id'] + '.json'), values['result'])
    source = lane / 'input/short_0177_video.mp4'
    require(source.is_file() and not source.is_symlink() and collection.sha_file(source) == collection.SOURCE_SHA, 'Frozen local source payload SHA mismatch')
    require(values['config']['input_sha256'] == collection.SOURCE_SHA, 'Remote config source SHA mismatch')
    probe = probe_video(Path(entry['video']), ffprobe)
    return {'passed': True, 'arm': arm, 'job_id': item['job_id'], 'attempt_id': item['attempt_id'],
            'cohort': collection.COHORT, 'video': entry['video'], 'video_sha256': item['video_sha256'],
            'probe': probe, 'valid_frames': 60, 'routing_steps': collection.STEPS[arm],
            'routed_blocks': values['router']['routed_calls'], 'completed_forwards': 20, 'completed_blocks': 1000,
            'alpha': values['router']['alpha'], 'sampling_seconds': values['timing']['sampler_wall_seconds'],
            'mean_step_seconds': values['timing']['mean_sampling_step_seconds'], 'graph': graph,
            'backend_contract': values['backend_contract'], 'backend_contract_sha256': item['artifacts']['backend_contract']['sha256'],
            'backend_snapshot_counts': counts, 'source': str(source), 'source_sha256': collection.SOURCE_SHA,
            'artifacts': item['artifacts']}


def inspect_six(manifest, package, ffprobe='ffprobe'):
    raw = manifest.read_bytes(); index = json.loads(raw)
    require(index['cohort'] == collection.COHORT and index['remote_root'] == EXPECTED_ROOT == collection.REMOTE_ROOT,
            'Collection cohort or run root mismatch')
    checked, pending, errors = {}, {}, {}
    for arm in collection.ARMS:
        entry = index.get('arms', {}).get(arm, {})
        if entry.get('status') != 'completed':
            (errors if entry.get('status') == 'error' else pending)[arm] = entry.get('reason', 'Completed collection absent')
            continue
        try:
            checked[arm] = validate_local_arm(arm, entry, manifest.parent / arm, package, ffprobe)
        except Exception as error:
            errors[arm] = type(error).__name__ + ': ' + str(error)
    if index.get('errors'):
        errors['collection_index'] = index['errors']
    if checked:
        contracts = {x['backend_contract_sha256'] for x in checked.values()}
        if len(contracts) != 1:
            errors['backend_contract'] = 'The six arms must share the exact frozen native-pilot contract'
    passed = len(checked) == 6 and not pending and not errors
    return {'schema': 'interval-short0177-six-local-verification-v1', 'checked_unix': time.time(),
            'status': 'passed' if passed else 'error' if errors else 'pending', 'passed': passed,
            'cohort': collection.COHORT, 'remote_root': EXPECTED_ROOT, 'collection_manifest': str(manifest),
            'collection_manifest_sha256': hashlib.sha256(raw).hexdigest(), 'package': str(package),
            'arms': checked, 'pending': pending, 'errors': errors, 'raw_inputs_changed': False}


def atomic(path, value):
    temporary = path.with_suffix('.tmp.' + str(os.getpid()))
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def publish(result, output):
    output.mkdir(parents=True, exist_ok=True)
    atomic(output / 'ROOT_SIX_ARMS_STATUS.json', result)
    if not result['passed']:
        return None
    gate = output / 'ROOT_SIX_ARMS_VERIFIED.json'
    atomic(gate, result)
    native = result['arms']['native']
    videos = {'source': {'file': native['source'], 'sha256': native['source_sha256']}}
    videos.update({arm: {'file': item['video'], 'sha256': item['video_sha256']} for arm, item in result['arms'].items()})
    atomic(output / 'ROOT_SIX_ARMS_BINDINGS.json', {'task_id': 'short_0177', 'cohort': collection.COHORT,
            'completion_gate': str(gate), 'completion_gate_sha256': collection.sha_file(gate), 'videos': videos})
    return gate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=HERE / 'collection/LOCAL_COLLECTION.json')
    parser.add_argument('--package', type=Path, default=HERE / 'runtime/v3/package')
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--ffprobe', default='ffprobe')
    args = parser.parse_args()
    result = inspect_six(args.manifest.resolve(), args.package.resolve(), args.ffprobe)
    gate = publish(result, args.output.resolve())
    print(json.dumps({'status': result['status'], 'passed': result['passed'], 'checked_arms': list(result['arms']),
          'pending': result['pending'], 'errors': result['errors'], 'completion_gate': str(gate) if gate else None}, ensure_ascii=False, indent=2))
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
