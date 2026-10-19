"""Immutable input, execution and release checks for the R111 consumer."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECKS = (
    'producer_seal', 'actual_R107_fixed_comparison', 'same_host_numerical_runtime', 'actual_runtime_device',
    'actual_history', 'actual_service_generation', 'actual_condition_snapshot',
    'all_conditions_equal_actual_Native', 'pre_DiT_condition_gate',
    'actual_parent_six_condition_tensors', 'actual20NFE20Euler450routes',
    'valid_physical_support', 'sampled_finite', 'same_sampler_grid_and_initial_packed_noise',
    'AV_prediction_prefix_0_5_bitwise_equal', 'actual_raw_AV_noise_equal_Native', 'output_geometry')


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def bound(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}


def config():
    return read(ROOT/'configs/contract.json')


def verify_static():
    cfg = config()
    for name, digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():
        require(sha(ROOT/name) == digest, 'consumer file changed: '+name)
    require(sha(ROOT/'configs/producer_deploy_manifest.json') == cfg['producer_seal_sha256'],
            'producer seal binding changed')
    require(sha(ROOT/'configs/producer_runtime.json') == cfg['producer_runtime_sha256'],
            'producer runtime binding changed')
    for role, item in cfg['historical_media'].items():
        require(sha(item['file']) == item['sha256'], 'historical '+role+' changed')
    for name, item in cfg['historical_evidence'].items():
        require(sha(item['file']) == item['sha256'], 'historical evidence changed: '+name)
    verify_graph_control(read(ROOT/'configs/producer_graph.json'),
                         read(ROOT/'configs/R107_GRAPH.json'), cfg)
    return cfg


def verify_graph_control(current, fixed, cfg):
    require(current['5']['inputs']['prompt'] == fixed['5']['inputs']['prompt'],
            'prompt changed between fixed and spatial routing')
    require(current['50']['inputs']['mode'] == 'spatial_marginal' and
            fixed['50']['inputs']['mode'] == 'mass_preserve', 'routing comparison modes differ')
    def normalize(graph, remote, prefix):
        value = json.loads(json.dumps(graph).replace(remote, 'PRODUCER_ROOT').replace(prefix, 'RUN_'))
        value['50']['inputs']['mode'] = 'COMPARED_ROUTING_MODE'
        return value
    require(normalize(current, cfg['producer_remote'], 'r111_') ==
            normalize(fixed, cfg['fixed_producer_remote'], 'r107_'),
            'graph changed beyond routing mode and administrative paths')


def verify_gate(gate, cfg):
    require(gate.get('schema') == 'r111-historical-native-paired-runtime-gate-v1'
            and gate.get('passed') is True, 'actual R111 gate failed')
    require(gate.get('source_id') == 'long_0174' and
            gate.get('runtime_profile_sha256') == cfg['producer_runtime_sha256'],
            'source or runtime binding changed')
    checks = gate.get('checks', {})
    require(all(checks.get(name) is True for name in REQUIRED_CHECKS)
            and all(value is True for value in checks.values()), 'required gate check failed')
    fixed = gate['fixed_comparison']
    require(fixed['passed'] is True and fixed['binding'] == cfg['fixed_binding'] and
            fixed['checks'].get('fixed_exact_release') is True and
            all(v is True for v in fixed['checks'].values()), 'actual R107 fixed comparison differs')
    require(set(gate['runs']) == {'native', 'forced'}, 'unexpected paired runs')
    native, spatial = gate['runs']['native'], gate['runs']['forced']
    require(native['run_id'] == cfg['native_run_id'] and
            native['video']['sha256'] == cfg['historical_media']['native']['sha256'],
            'historical native binding changed')
    require(spatial['run_id'] == cfg['run_id'], 'R111 run identity changed')
    require((native['NFE'], native['routed_blocks'], spatial['NFE'], spatial['routed_blocks']) ==
            (20, 0, 20, 450), 'execution counts differ')
    require(native['valid_frames'] == spatial['valid_frames'] == gate['valid_frames'] == 145
            and gate['total_frames'] == 158 and gate['fps'] == 24
            and gate['evaluation_crop_xywh'] == [16, 8, 1280, 720], 'physical support differs')
    prefix = gate['prefix_tensor_comparison']
    require(len(prefix) == 6, 'pre-intervention prediction evidence absent')
    for i, row in enumerate(prefix):
        require(row['step_zero_based'] == i and row['video'] is True and row['audio'] is True
                and row['parent_file_sha256'] == cfg['first_six_predictions'][i]['sha256'],
                'pre-intervention prediction differs')
    path = Path(spatial['video']['file'])
    require(path == Path(cfg['producer_remote'])/'output'/(cfg['run_id']+'_00001_.mp4'),
            'unexpected generated output path')
    props = spatial['video']['properties']
    require((props['width'], props['height'], props['avg_frame_rate'], int(props['nb_read_frames'])) ==
            (1312, 736, '24/1', 158), 'generated output geometry differs')
    return spatial


def verify_release(gate, complete, release, started, cleanup, gate_sha, cfg):
    owner = gate['service_owner']
    require(complete.get('passed') is True and complete.get('GPU_released') is True and
            complete.get('jobs') == [cfg['run_id']] and complete.get('remaining') == [],
            'completed single run required')
    require(complete['gates']['long_0174']['sha256'] == gate_sha, 'completed gate hash differs')
    require(release.get('passed') is True and release.get('process_absent') is True and
            release.get('CUDA_allocation_absent') is True, 'exact release pending')
    require(release['owner'] == started['owner'] == owner, 'service generation differs')
    require(cleanup['pid'] == owner['pid'] and cleanup['process_absent'] is True and
            cleanup['own_compute_absent'] is True, 'cleanup does not match actual service')


def verify_job(folder, gate, cfg):
    graph, job, history, router = [read(folder/(name+'.json')) for name in
                                  ('graph', 'job', 'history', 'router')]
    require(graph == read(ROOT/'configs/producer_graph.json'), 'actual graph differs')
    require(job['status'] == 'success' and job['name'] == cfg['run_id'] and
            job['graph_sha256'] == sha(folder/'graph.json'), 'actual job differs')
    owner = gate['service_owner']
    require(job['service_pid'] == owner['pid'] and job['service_identity'] == owner['identity'],
            'actual job service generation differs')
    require(history['status']['completed'] is True and history['status']['status_str'] == 'success'
            and history['prompt'][2] == graph and history['prompt'][1] == job['prompt_id'],
            'actual history differs')
    expected = {'run_id': cfg['run_id'], 'mode': 'spatial_marginal', 'alpha': 1.0,
        'radius': 0, 'time_offset': 0, 'block_interval_half_open': [0, 50],
        'step_interval_half_open': [6, 15], 'pixel_interval_inclusive': [0, 144],
        'completed_forward_calls': 20, 'routed_calls': 450,
        'routed_by_forward': [0]*6+[50]*9+[0]*5, 'routed_by_block': [9]*50}
    require(all(router.get(k) == v for k, v in expected.items()),
            'actual spatial routing mode or schedule differs')


def verify_collection(folder):
    cfg = verify_static()
    receipt = read(folder/'COLLECTION.json')
    require(receipt['passed'] is True and receipt['consumer_freeze_sha256'] ==
            sha(ROOT/'CONSUMER_FREEZE.json'), 'consumer intake binding differs')
    for name, digest in receipt['files'].items():
        require(Path(name).name == name and sha(folder/name) == digest,
                'collected file changed: '+name)
    gate = read(folder/'PAIR_RUNTIME_GATE.json')
    verify_gate(gate, cfg)
    verify_release(gate, read(folder/'COMPLETE.json'), read(folder/'ROOT_EXIT_RECEIPT.json'),
                   read(folder/'STARTED.json'), read(folder/'cleanup.json'),
                   sha(folder/'PAIR_RUNTIME_GATE.json'), cfg)
    verify_job(folder, gate, cfg)
    require(sha(folder/'spatial.mp4') == gate['runs']['forced']['video']['sha256'],
            'actual R111 media differs')
    for role, item in cfg['historical_media'].items():
        require(sha(folder/(role+'.mp4')) == item['sha256'], 'historical media bytes differ')
    return receipt
