"""CPU verification of retained R72 Native against a new R84 fixed-route result."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import torch
from r84_contract import read, sha, require, registry, validate_job, SOURCES, SHAPES
from execution_gate import atomic, historical_evidence
from capture_checks import inspect_capture, checked_snapshot, inspect_blob, condition_files, signature, expected_routing
from legacy_checks import walk_blobs, reference_geometry_matches, output_file, video_properties


def equal_condition_fields(a, b):
    return {key + '_equal': a[key] == b[key] for key in ('prompt', 'input_video',
        'native_vae_calls', 'qwen_presentation', 'tokenization_before_vision_expansion',
        'conditioning_embedding', 'token_tags', 'target_latent_shapes', 'packed_layout')}


def verify(root, source):
    torch.set_num_threads(1); root = Path(root).resolve()
    require(source in SOURCES, 'unknown source'); jobs, _ = registry(root)
    run = 'r84_' + source + '_seed2026101701_forced'; row = validate_job(run, root); case = row['case']
    historical = historical_evidence(run, root)
    runtime = read(root / 'configs/runtime.json'); owner = read(root / 'processes/service.json')
    checks = {'producer_seal': all(sha(root / p) == v['sha256'] for p, v in read(root / 'deploy_manifest.json')['files'].items()),
              'new_service_device': owner['gpu_uuid'] == runtime['gpu_uuid'] and owner['port'] == runtime['port']}
    result = {'schema': 'r84-historical-native-paired-runtime-gate-v1', 'source_id': source,
        'prompt_version': case['prompt_version'], 'same_service_generation': False,
        'pairing_scope': 'same-host numeric profile across service generations; actual conditions/noise/prefix equality required',
        'runtime_profile_sha256': sha(root / 'configs/runtime.json'), 'historical_evidence': historical,
        'checks': checks, 'runs': {}, 'created_unix': time.time(), 'condition_tensor_files': []}
    conditions = {}; noises = {}; manifests = {}; folders = {}; runs = {}
    for arm in ('native', 'forced'):
        forced = arm == 'forced'; work = root if forced else Path(case['baseline_root'])
        current = run if forced else case['baseline_run']; runs[arm] = current
        graph = read(root / 'configs/graphs' / (run + '.json')) if forced else read(root / case['parent_graph'])
        grid = torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')], dtype=torch.float32).tolist()
        hist = read(work / 'logs' / (current + '_history.json')); job = read(work / 'logs' / (current + '_job.json'))
        checks[arm + '_history'] = (hist['status']['completed'] is True and hist['status']['status_str'] == 'success' and
            hist['prompt'][2] == graph and hist['prompt'][1] == job['prompt_id'] and job['status'] == 'success' and job['name'] == current)
        checks[arm + '_graph_binding'] = job['graph_sha256'] == sha(root / 'configs/graphs' / (run + '.json') if forced else root / case['parent_graph'])
        if forced:
            checks['new_actual_service_identity'] = job['service_pid'] == owner['pid'] and job['service_identity'] == owner['identity']
        c = read(work / 'audit' / (current + '_conditioning.json')); n = read(work / 'audit' / (current + '_noise.json'))
        conditions[arm] = c; noises[arm] = n
        shared_id = case['reference_cache_id'] if forced else case['baseline_reference_cache_id']
        shared = work / 'audit' / (shared_id + '_conditioning.json')
        checks[arm + '_shared_conditions'] = (c['run_id'] == current and c['pair_snapshot']['verified'] is True and
            c['pair_snapshot']['source_run_id'] == shared_id and c['pair_snapshot']['source_manifest_sha256'] == sha(shared) and c['prompt'] == case['prompt'])
        require(len(condition_files(c)) == 8, 'expected eight image-plus-video condition blobs')
        seen = set()
        for record in walk_blobs(read(shared)):
            if record['tensor_file'] not in seen:
                seen.add(record['tensor_file']); result['condition_tensor_files'].append({'arm': arm, **inspect_blob(work / 'audit', record)})
        router = read(work / 'audit/router' / (current + '.json'))
        expected = {'run_id': current, 'mode': 'mass_preserve' if forced else 'native', 'alpha': 1.,
            'radius': 0, 'time_offset': 0, 'block_interval_half_open': [0, 50],
            'step_interval_half_open': [6, 15] if forced else [0, 20], 'pixel_interval_inclusive': [0, 146],
            'started_calls': 1000, 'completed_calls': 1000, 'completed_forward_calls': 20,
            'native_override_calls': 1000, 'routed_calls': 450 if forced else 0,
            'calls_by_forward': [50] * 20, 'calls_by_block': [20] * 50,
            'routed_by_forward': expected_routing(forced), 'routed_by_block': [9 if forced else 0] * 50,
            'sample_sigmas': grid, 'expected_sampling_steps': 20}
        checks[arm + '_actual_execution_counts'] = all(router.get(k) == v for k, v in expected.items())
        plan = router['validated_layout']; seq = c['packed_layout']['seq_len']
        checks[arm + '_actual_layout'] = (router['first_attention']['qkv_shape'] == [1, 56, seq, 128] and
            plan['frame_rows'] == 864 and plan['latent_interval_half_open'] == [0, 44] and
            plan['position_bin_coverage_inclusive'] == [0, 148] and
            plan['query_interval_half_open'] == [plan['target_video_segment'][0], plan['target_video_segment'][0] + 44*864] and
            plan['key_interval_half_open'] == [plan['reference_video_segment'][0], plan['reference_video_segment'][0] + 44*864])
        checks[arm + '_reference_geometry'] = reference_geometry_matches(c, case, plan)
        checks[arm + '_sampled_finite'] = all(x.get('sampled_finite', True) for x in router['forward_summaries'])
        folder = work / 'audit/x0' / current; folders[arm] = folder
        manifest, files, _ = inspect_capture(folder, current, grid, case['seed']); manifests[arm] = manifest
        cache = work / 'audit' / (case['baseline_noise_pair_id'] + '_noise.pt')
        saved = torch.load(cache, map_location='cpu', weights_only=True)
        hashes = [{k: signature(t)[k] for k in ('shape', 'dtype', 'sha256')} for t in saved['tensors']]
        checks[arm + '_actual_noise_cache'] = (n['run_id'] == current and n['pair_id'] == case['baseline_noise_pair_id'] and
            n['signature']['seed'] == case['seed'] and [x['shape'] for x in hashes] == [list(SHAPES[k]) for k in ('video', 'audio')] and
            saved['signature'] == n['signature'] and saved['hashes'] == hashes == n['actual_noise_streams'])
        video = output_file(work, hist); properties = video_properties(video)
        result['runs'][arm] = {'run_id': current, 'video': {'file': str(video), 'sha256': sha(video), 'properties': properties},
            'valid_frames': 147, 'evaluation_crop_xywh': [0, 0, 1152, 768], 'evaluation_indices': list(range(0, 147, 3)),
            'evaluation_fps': 8, 'NFE': 20, 'Euler_updates': 20, 'routed_blocks': router['routed_calls'],
            'job_wall_seconds': job['observed_unix'] - job['submitted_unix'], 'snapshots': files}
        del saved
    checks.update(equal_condition_fields(conditions['native'], conditions['forced']))
    checks['actual_initial_AV_noise_equal'] = (noises['native']['signature'] == noises['forced']['signature'] and
        noises['native']['actual_noise_streams'] == noises['forced']['actual_noise_streams'])
    prefix = []
    for i in range(6):
        a, _ = checked_snapshot(folders['native'], manifests['native']['captures'][i], runs['native'])
        b, _ = checked_snapshot(folders['forced'], manifests['forced']['captures'][i], runs['forced'])
        prefix.append({'step_zero_based': i, **{k: torch.equal(a[k], b[k]) for k in ('video', 'audio')}})
    result['prefix_checks'] = prefix
    checks['Native_prefix_0_5_equal'] = all(x['video'] and x['audio'] for x in prefix)
    result['passed'] = all(checks.values())
    return result


def main():
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=SOURCES, required=True)
    a = p.parse_args(); dest = ROOT / 'analysis/postrun' / a.source / 'PAIR_RUNTIME_GATE.json'
    try: result = verify(ROOT, a.source)
    except BaseException as e:
        atomic(dest.with_name('PAIR_RUNTIME_GATE_FAILURE.json'), {'passed': False, 'source': a.source, 'error': repr(e), 'unix': time.time()}); raise
    atomic(dest, result); print(json.dumps({'receipt': str(dest), 'passed': result['passed'], 'checks': result['checks']}, indent=2))
    if not result['passed']: raise SystemExit(2)


if __name__ == '__main__': main()
