"""R110 numerical inputs with one approved framing prompt, then matched guidance."""
import copy, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = PAIR_KEYS = ('short_0114',)
ARMS = ('native', 'forced')
GEOMETRY = {'width': 1312, 'height': 736, 'frames': 107, 'fps': 24}
SHAPES = {'video': (1, 24, 32, 46, 82), 'audio': (1, 32, 2, 178)}
PROMPT = "Edit <Video 1>: change only the basketball's appearance to a neon-lit basketball. Preserve the original framing and camera angle, the player's on-screen position, scale and head visibility in each frame, and the ball's size, dribbling path and timing."
PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()
ROUTER = {'mode': 'mass_preserve', 'alpha': 1.0, 'blocks': [0, 50], 'steps': [6, 15], 'physical_frames': '[0,valid_frame_count-1] per source', 'query_support': 'all spatial queries in each position bin overlapping valid physical time; pure-pad bins remain native', 'native_mask_parameters': 'same as forced; mode native'}

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def require(ok, message):
    if not ok:
        raise ValueError(message)

REMOTE = Path(read(ROOT / 'configs/runtime.json')['remote_root'])

def geometry(case):
    return dict(GEOMETRY)

def latent_shapes(case):
    return dict(SHAPES)

def routing_layout(case):
    return {'latent_interval_half_open': [0, 32], 'position_bin_coverage_inclusive': [0, 106], 'pixel_interval_inclusive': [0, 104], 'total_latent_bins': 32, 'pure_pad_bins': [], 'frame_rows': 943}

def definitions(root=ROOT):
    root = Path(root)
    binding = read(root / 'configs/parent_bindings.json')
    p = root / 'design/CASE_DEFINITION.json'
    require(sha(p) == binding['definition_sha256'], 'source definition changed')
    value = read(p)
    require(value['pair_key'] == SOURCES[0], 'source changed')
    return [value]

def expected_graph(root, case):
    root = Path(root)
    remote = Path(read(root / 'configs/runtime.json')['remote_root'])
    graph = copy.deepcopy(read(root / case['parent_graph']))
    run = case['run_id']
    shared = 'r117_short_0114_shared'
    for node, key, suffix in [('5', 'audit_dir', 'audit'), ('6', 'audit_dir', 'audit'), ('50', 'audit_dir', 'audit/router'), ('51', 'source_audit_dir', 'audit'), ('52', 'output_dir', 'audit/x0')]:
        graph[node]['inputs'][key] = str(remote / suffix)
    graph['5']['inputs'].update(prompt=PROMPT, run_id=shared)
    graph['51']['inputs']['source_run_id'] = shared
    for node in ('6', '50', '51', '52'):
        graph[node]['inputs']['run_id'] = run
    graph['6']['inputs']['pair_id'] = 'r117_short_0114_seed2026101701'
    graph['14']['inputs']['filename_prefix'] = run
    graph['50']['inputs']['mode'] = 'mass_preserve' if case['arm'] == 'forced' else 'native'
    return graph

def registry(root=ROOT):
    root = Path(root)
    science = read(root / 'configs/scientific_contract.json')
    order = ['r117_short_0114_seed2026101701_' + arm for arm in ARMS]
    require(science['case_order'] == order and len(science['cases']) == 2 and science['arms'] == list(ARMS) and science['source_ids'] == science['pair_keys'] == list(SOURCES), 'single paired registry changed')
    require(read(root / 'configs/queue.json') == {'jobs': order, 'finalize': True}, 'Native-first queue changed')
    binding = read(root / 'configs/parent_bindings.json')
    definition = definitions(root)[0]
    promptfile = root / 'configs/prompts/short_0114.txt'
    require(sha(promptfile) == binding['prompt_sha256'] == PROMPT_SHA and promptfile.read_text() == PROMPT, 'approved prompt changed')
    oldruntime = root / 'source_snapshot/r110/configs/runtime.json'
    require(sha(oldruntime) == binding['r110_runtime_sha256'], 'R110 runtime record changed')
    runtime = read(root / 'configs/runtime.json')
    previous = read(oldruntime)
    for key in ('host', 'core', 'python', 'dependencies', 'models', 'kj_nodes', 'reserve_vram', 'memory_mode', 'gpu_uuid', 'expected_gpu_index'):
        require(runtime[key] == previous[key], 'R110 numerical runtime differs: ' + key)
    parent = root / 'configs/parent_graphs/r110_actual_native.json'
    require(sha(parent) == binding['r110_native_graph_sha256'], 'R110 parent graph changed')
    original = read(root / 'source_snapshot/r110/configs/scientific_contract.json')['cases'][0]
    jobs = {}
    for case, arm, run in zip(science['cases'], ARMS, order):
        require(case['run_id'] == run and case['source_id'] == case['pair_key'] == SOURCES[0] and case['arm'] == arm and case['seed'] == 2026101701, 'case identity changed')
        require(case['geometry'] == GEOMETRY and case['valid_frame_count'] == 105 and case['evaluation_crop_xywh'] == [16, 8, 1280, 720] and case['evaluation_indices'] == list(range(105)), 'physical evaluation geometry changed')
        require(case['reference_image_count'] == 0 and case['reference_video_count'] == 1, 'reference scope changed')
        require(case['prompt'] == PROMPT and case['prompt_sha256'] == PROMPT_SHA and case['prompt_version'] == 'frame-preservation-short-v1', 'prompt contract changed')
        require(case['parent_graph'] == str(parent.relative_to(root)) and case['parent_graph_sha256'] == sha(parent), 'parent graph differs')
        require(case['original_task'] == original['original_task'] and case['clip'] == original['clip'], 'official task or source clip changed')
        for key in ('video', 'provenance'):
            require(case[key] == definition['source'][key] and case[key + '_sha256'] == definition['source'][key + '_sha256'], 'frozen source binding changed')
        graph = root / 'configs/graphs' / (run + '.json')
        require(read(graph) == expected_graph(root, case), 'graph differs outside prompt/admin/mode')
        jobs[run] = {'case': case, 'source_id': SOURCES[0], 'pair_key': SOURCES[0], 'motion_source_id': SOURCES[0], 'seed': case['seed'], 'arm': arm, 'graph_sha256': sha(graph)}
    return jobs, order

def validate_job(run, root=ROOT):
    root = Path(root)
    jobs, _ = registry(root)
    require(run in jobs, 'unknown run')
    row = jobs[run]
    for key in ('video', 'provenance'):
        case = row['case']
        path = root / 'inputs' / case[key]
        require(Path(case[key]).name == case[key] and not path.is_symlink() and sha(path) == case[key + '_sha256'], 'input changed: ' + key)
    return row

def audit_dir(value):
    p = Path(value)
    require(p.is_absolute() and p.resolve() == REMOTE / 'audit', 'audit root differs')
    return p

def validate_router(mode, alpha, radius, time_offset, start_frame, end_frame, block_start, block_end, step_start, step_end, run_id, audit_dir):
    row = validate_job(run_id)
    require(Path(audit_dir) == REMOTE / 'audit/router', 'router audit differs')
    require((mode, alpha, radius, time_offset, start_frame, end_frame, block_start, block_end, step_start, step_end) == ('mass_preserve' if row['arm'] == 'forced' else 'native', 1., 0, 0, 0, 104, 0, 50, 6, 15), 'fixed routing changed')

def prepare_loader_inputs(run, root=ROOT):
    import shutil
    root = Path(root)
    row = validate_job(run, root)
    case = row['case']
    folder = root / 'input'
    folder.mkdir(exist_ok=True)
    path = folder / case['video']
    if not path.exists():
        with (root / 'inputs' / case['video']).open('rb') as before, path.open('xb') as after:
            shutil.copyfileobj(before, after)
    require(not path.is_symlink() and sha(path) == case['video_sha256'], 'loader source changed')
    return row
