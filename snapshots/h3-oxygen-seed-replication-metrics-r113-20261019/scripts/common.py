"""Independent R113 scientific input, actual pair, media and release binding."""
from pathlib import Path
import hashlib, json, struct

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('native', 'fixed')
SEEDS = (2026101702, 2026101703)
VALID, TOTAL, FPS = 98, 107, 24
CROP = [16, 8, 1280, 720]

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')

def bound(path):
    return {'file': str(Path(path).resolve()), 'sha256': sha(path)}

def relative(path):
    path = Path(path)
    require(not path.is_absolute() and '..' not in path.parts and str(path) not in ('', '.'), 'unsafe relative path')
    return path

def verify_static():
    cfg = read(ROOT/'configs/contract.json')
    for name, digest in read(ROOT/'CONSUMER_FREEZE.json')['files'].items():
        require(sha(ROOT/relative(name)) == digest, 'consumer frozen file changed: '+name)
    for name, key in [('producer_deploy_manifest.json', 'producer_seal_sha256'),
                      ('producer_runtime.json', 'producer_runtime_sha256'),
                      ('PREREGISTERED_EVENTS.json', 'events_sha256')]:
        require(sha(ROOT/'configs'/name) == cfg[key], 'producer binding changed: '+name)
    require(sha(cfg['source']['file']) == cfg['source']['sha256'], 'source bytes changed')
    science = read(ROOT/'configs/scientific_contract.json')
    require(science['case_order'] == cfg['jobs'] and science['seeds'] == list(SEEDS), 'registered seeds/jobs changed')
    require(len(science['cases']) == 4 and all(row['video_sha256'] == cfg['source']['sha256']
            and row['valid_frame_count'] == VALID and row['reference_image_count'] == 0 for row in science['cases']),
            'source bytes or task modality differ from scientific contract')
    require(cfg['valid_frames'] == VALID and cfg['total_frames'] == TOTAL and cfg['fps'] == FPS and cfg['crop_xywh'] == CROP,
            'registered physical support changed')
    for seed in SEEDS:
        graphs = [read(ROOT/'configs/graphs'/(cfg['runs'][str(seed)][arm]+'.json')) for arm in ARMS]
        verify_graph_pair(graphs, seed, cfg)
    return cfg

def verify_graph_pair(graphs, seed, cfg):
    normalized = []
    for graph, arm in zip(graphs, ARMS):
        run = cfg['runs'][str(seed)][arm]
        require(graph['6']['inputs']['noise_seed'] == seed and graph['8']['inputs']['sampler_name'] == 'euler', 'seed or solver differs')
        require(graph['50']['inputs']['mode'] == ('native' if arm == 'native' else 'mass_preserve'), 'routing mode differs')
        value = json.loads(json.dumps(graph).replace(run, 'CURRENT_RUN'))
        value['50']['inputs']['mode'] = 'COMPARED_MODE'
        normalized.append(value)
    require(normalized[0] == normalized[1], 'graph differs beyond run identity and routing mode')

def pair_required_checks():
    keys = ['raw_noise_geometry', 'same_complete_conditions', 'same_raw_noise', 'same_actual_sigmas']
    keys += [arm+'_'+name for arm in ARMS for name in
             ['history', 'generation', 'actual_conditions', 'actual_noise', 'actual_routes', 'layout', 'reference_geometry', 'finite']]
    keys += [f'step{step}_normalized_{kind}' for step in range(6) for kind in ('video', 'audio')]
    keys += [f'step{step}_raw_{kind}' for step in (0, 1) for kind in ('state_video', 'state_audio', 'prediction_video', 'prediction_audio')]
    return keys

def checks_pass(checks, required):
    require(bool(checks) and all(checks.get(name) is True for name in required)
            and all(value is True for value in checks.values()), 'required execution check missing or failed')

def verify_pair(gate, seed, cfg):
    require(gate.get('schema') == 'r113-fresh-seed-pair-runtime-gate-v1' and gate.get('passed') is True, 'per-seed actual gate failed')
    require(gate['seed'] == seed and gate['source_id'] == 'short_0252' and set(gate['runs']) == set(ARMS), 'seed/source/arms mismatch')
    require(gate['valid_frames'] == VALID and gate['frame_rate'] == FPS and gate['evaluation_crop_xywh'] == CROP, 'pair physical support differs')
    checks_pass(gate['checks'], pair_required_checks())
    require(gate['equal_normalized_prediction_steps'] == list(range(6)) and gate['equal_raw_prefix_steps'] == [0, 1], 'pre-intervention equality evidence missing')
    for arm in ARMS:
        row = gate['runs'][arm]
        run = cfg['runs'][str(seed)][arm]
        require(row['run_id'] == run and row['seed'] == seed and row['solver'] == 'euler' and row['sampler_function'] == 'sample_euler', 'fresh run binding differs')
        require(row['NFE'] == row['solver_updates'] == 20 and row['routed_blocks'] == (450 if arm == 'fixed' else 0), 'execution count differs')
        require(row['valid_frames'] == VALID and row['evaluation_indices'] == list(range(VALID)), 'padded frames entered evaluation')
        file = Path(row['video']['file'])
        require(file.is_relative_to(Path(cfg['producer_remote'])/'output') and '..' not in file.parts
                and file.name.startswith(run+'_') and file.suffix == '.mp4', 'unsafe or stale generated video path')
        props = row['video']['properties']
        require((props['width'], props['height'], props['avg_frame_rate'], int(props['nb_read_frames'])) == (1312, 736, '24/1', TOTAL), 'actual video geometry differs')
    require(len(gate['noise_cache']['tensor_signatures']) == 2, 'audio/video noise evidence missing')
    return gate

def verify_aggregate(aggregate, pairs, cfg):
    require(aggregate.get('schema') == 'r113-two-seed-runtime-gate-v1' and aggregate.get('passed') is True, 'aggregate actual gate failed')
    require(aggregate['source_id'] == 'short_0252' and aggregate['seeds'] == list(SEEDS)
            and aggregate['jobs'] == cfg['jobs'] and aggregate['report_all_seeds'] is True, 'all four registered runs required')
    checks_pass(aggregate['checks'], ['producer_seal', 'actual_runtime_device', 'distinct_seed_noise_video_and_audio', *[f'seed{s}_actual_pair' for s in SEEDS]])
    require(aggregate['producer_seal_sha256'] == cfg['producer_seal_sha256']
            and aggregate['runtime_profile_sha256'] == cfg['producer_runtime_sha256']
            and aggregate['preregistered_events_sha256'] == cfg['events_sha256'], 'aggregate scientific binding differs')
    require(aggregate['runtime_profile'] == read(ROOT/'configs/producer_runtime.json'), 'actual runtime differs')
    require(aggregate['valid_frames'] == VALID and aggregate['frame_rate'] == FPS and aggregate['evaluation_crop_xywh'] == CROP, 'aggregate physical support differs')
    receipts = aggregate['pair_gate_receipts']
    require([row['seed'] for row in receipts] == list(SEEDS), 'pair receipt registry differs')
    for seed, receipt in zip(SEEDS, receipts):
        verify_pair(pairs[str(seed)], seed, cfg)
        require(pairs[str(seed)]['service_owner'] == aggregate['service_owner'], 'paired service identity differs')
        require(receipt['file'] == str(Path(cfg['producer_remote'])/'analysis/postrun'/f'seed{seed}'/'PAIR_RUNTIME_GATE.json'), 'pair gate path differs')
    left, right = [pairs[str(seed)]['noise_cache']['tensor_signatures'] for seed in SEEDS]
    require(all(a['sha256'] != b['sha256'] for a, b in zip(left, right)), 'separate seeds reused noise')

def verify_release(aggregate, complete, release, started, cleanup, gate_sha, cfg):
    require(complete.get('passed') is True and complete.get('GPU_released') is True
            and complete.get('jobs') == cfg['jobs'] and complete.get('remaining') == []
            and complete.get('runtime_gate_sha256') == gate_sha, 'all four actual runs and release required')
    owner = aggregate['service_owner']
    require(owner['gpu_uuid'] == read(ROOT/'configs/producer_runtime.json')['gpu_uuid']
            and owner['identity']['uid'] == 1016, 'unexpected device or owner')
    require(release.get('passed') is True and release.get('process_absent') is True and release.get('CUDA_allocation_absent') is True, 'exact release incomplete')
    require(release['owner'] == started['owner'] == owner, 'service generation changed')
    require(cleanup['pid'] == owner['pid'] and cleanup['process_absent'] is True and cleanup['own_compute_absent'] is True, 'cleanup does not match actual service')

def verify_run(folder, pair, seed, arm, cfg):
    run = cfg['runs'][str(seed)][arm]
    row = pair['runs'][arm]
    data = {kind: read(folder/f'{run}_{kind}.json') for kind in ('graph', 'job', 'history', 'router', 'conditioning', 'noise')}
    for kind in ('job', 'history', 'router', 'conditioning', 'noise'):
        require(sha(folder/f'{run}_{kind}.json') == row[kind+'_sha256'], 'actual receipt SHA differs: '+kind)
    graph, job, history, router = [data[kind] for kind in ('graph', 'job', 'history', 'router')]
    require(graph == read(ROOT/'configs/graphs'/(run+'.json')), 'actual graph differs')
    require(job['status'] == 'success' and job['name'] == run and job['graph_sha256'] == sha(folder/f'{run}_graph.json'), 'actual job differs')
    owner = pair['service_owner']
    require(job['service_pid'] == owner['pid'] and job['service_identity'] == owner['identity'], 'actual job generation differs')
    require(history['status']['completed'] is True and history['status']['status_str'] == 'success'
            and history['prompt'][2] == graph and history['prompt'][1] == job['prompt_id'], 'actual successful history differs')
    images = history['outputs']['14']['images']
    require(len(images) == 1 and images[0].get('type') == 'output', 'actual final output differs')
    output = relative(str(Path(images[0].get('subfolder', ''))/images[0]['filename']))
    require(str(Path(cfg['producer_remote'])/'output'/output) == row['video']['file'], 'history/video binding differs')
    fixed = arm == 'fixed'
    expected = {'run_id': run, 'mode': 'mass_preserve' if fixed else 'native', 'alpha': 1.,
                'radius': 0, 'time_offset': 0, 'block_interval_half_open': [0, 50], 'step_interval_half_open': [6, 15],
                'pixel_interval_inclusive': [0, 97], 'started_calls': 1000, 'completed_calls': 1000,
                'completed_forward_calls': 20, 'native_override_calls': 1000, 'routed_calls': 450 if fixed else 0,
                'calls_by_forward': [50]*20, 'calls_by_block': [20]*50,
                'routed_by_forward': [0]*6+[50 if fixed else 0]*9+[0]*5, 'routed_by_block': [9 if fixed else 0]*50}
    require(all(router.get(key) == value for key, value in expected.items()), 'actual routing differs')
    sigmas = [struct.unpack('f', struct.pack('f', float(x)))[0] for x in graph['9']['inputs']['sigmas'].split(',')]
    require(router['sample_sigmas'] == sigmas, 'actual sigma sequence differs')
    condition, noise = data['conditioning'], data['noise']
    require(condition['run_id'] == run and condition['pair_snapshot']['verified'] is True
            and condition['prompt'] == graph['5']['inputs']['prompt'], 'actual conditioning differs')
    require(noise['run_id'] == run and noise['signature']['seed'] == seed
            and noise['actual_noise_streams'] == pair['noise_cache']['tensor_signatures'], 'actual noise seed/streams differ')
    require(sha(folder/f'{run}.mp4') == row['video']['sha256'], 'downloaded output bytes differ')
    return data

def verify_collection(folder):
    cfg = verify_static()
    receipt = read(folder/'COLLECTION.json')
    require(receipt['passed'] is True and receipt['consumer_freeze_sha256'] == sha(ROOT/'CONSUMER_FREEZE.json'), 'consumer intake binding differs')
    require(receipt['all_four_retained'] is True and receipt['seeds'] == list(SEEDS)
            and receipt['valid_frames'] == VALID and receipt['fps'] == FPS, 'collection registry or physical support differs')
    for name, digest in receipt['files'].items():
        require(Path(name).name == name and sha(folder/name) == digest, 'collected file changed: '+name)
    aggregate = read(folder/'AGGREGATE_GATE.json')
    pairs = {str(seed): read(folder/f'seed{seed}_PAIR_GATE.json') for seed in SEEDS}
    verify_aggregate(aggregate, pairs, cfg)
    for seed, gate_receipt in zip(SEEDS, aggregate['pair_gate_receipts']):
        require(sha(folder/f'seed{seed}_PAIR_GATE.json') == gate_receipt['sha256'], 'pair gate SHA differs')
        values = [verify_run(folder, pairs[str(seed)], seed, arm, cfg) for arm in ARMS]
        conditions = [{key: value for key, value in item['conditioning'].items() if key != 'run_id'} for item in values]
        require(conditions[0] == conditions[1], 'paired actual conditions differ')
    verify_release(aggregate, read(folder/'COMPLETE.json'), read(folder/'ROOT_EXIT_RECEIPT.json'),
                   read(folder/'STARTED.json'), read(folder/'cleanup.json'), sha(folder/'AGGREGATE_GATE.json'), cfg)
    require(read(folder/'service.json') == aggregate['service_owner'], 'service registry differs')
    require(sha(folder/'deploy_manifest.json') == cfg['producer_seal_sha256'], 'deployed producer seal differs')
    require(sha(folder/'source.mp4') == cfg['source']['sha256'], 'collected source differs')
    return receipt
