"""Route-only continuations of two preserved, reviewed R72 Native outcomes."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('one_leg__movie_man_9', 'fitness__game_man_5')
ARMS = ('forced',)
GEOMETRY = {'width': 1152, 'height': 768, 'frames': 158, 'fps': 24}
SHAPES = {'video': (1, 24, 47, 48, 72), 'audio': (1, 32, 2, 263)}
ROUTER = {'mode': 'mass_preserve', 'alpha': 1., 'blocks': [0, 50], 'steps': [6, 15], 'frames': [0, 146]}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


REMOTE = Path(read(ROOT / 'configs/runtime.json')['remote_root'])


def expected_graph(root, case):
    root = Path(root); remote = Path(read(root / 'configs/runtime.json')['remote_root'])
    g = copy.deepcopy(read(root / case['parent_graph']))
    run = case['run_id']
    for node, key, suffix in [('5', 'audit_dir', 'audit'), ('6', 'audit_dir', 'audit'),
            ('50', 'audit_dir', 'audit/router'), ('51', 'source_audit_dir', 'audit'),
            ('52', 'output_dir', 'audit/x0')]:
        g[node]['inputs'][key] = str(remote / suffix)
    g['5']['inputs']['run_id'] = case['reference_cache_id']
    g['51']['inputs']['source_run_id'] = case['reference_cache_id']
    for node in ('6', '50', '51', '52'):
        g[node]['inputs']['run_id'] = run
    g['14']['inputs']['filename_prefix'] = run
    # pair_id and noise seed remain exactly those of the historical Native.
    g['50']['inputs'].update(mode='mass_preserve', alpha=1., radius=0, time_offset=0,
        start_frame=0, end_frame=146, block_start=0, block_end=50, step_start=6, step_end=15)
    return g


def registry(root=ROOT):
    root = Path(root); s = read(root / 'configs/scientific_contract.json')
    order = ['r84_' + source + '_seed2026101701_forced' for source in SOURCES]
    require(s['source_ids'] == list(SOURCES) and s['arms'] == ['forced'] and
            s['case_order'] == order and len(s['cases']) == 2, 'fixed two sources/order changed')
    q = read(root / 'configs/queue.json')
    require(q == {'jobs': order, 'finalize': True}, 'manual registered queue changed')
    jobs = {}
    for case, source, run, old_arm in zip(s['cases'], SOURCES, order, ('p0', 'p1')):
        require(case['run_id'] == run and case['source_id'] == case['pair_key'] == source and
                case['arm'] == 'forced' and case['seed'] == 2026101701 and
                case['geometry'] == GEOMETRY and case['valid_frame_count'] == 147,
                'source/seed/geometry changed')
        require(case['baseline_run'] == 'r72_' + source + '_seed2026101701_' + old_arm and
                case['baseline_root'] == '/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018',
                'historical Native changed')
        require(case['reference_cache_id'] == 'r84_' + source + '_shared', 'new cache identity differs')
        p = root / case['parent_graph']; original = read(p)
        require(sha(p) == case['parent_graph_sha256'], 'actual parent graph changed')
        require(original['50']['inputs']['mode'] == 'native' and
                original['5']['inputs']['prompt'] == case['prompt'] == (root / case['prompt_file']).read_text(),
                'historical Native prompt/mode changed')
        require(sha(root / case['prompt_file']) == case['prompt_sha256'], 'prompt bytes changed')
        require(original['6']['inputs']['pair_id'] == case['baseline_noise_pair_id'], 'old noise binding changed')
        graph = root / 'configs/graphs' / (run + '.json')
        require(read(graph) == expected_graph(root, case), 'route-only graph differs')
        jobs[run] = {'case': case, 'source_id': source, 'pair_key': source,
            'seed': case['seed'], 'arm': 'forced', 'graph_sha256': sha(graph)}
    return jobs, order


def validate_job(run, root=ROOT):
    root = Path(root); jobs, _ = registry(root)
    require(run in jobs, 'unknown run'); row = jobs[run]
    for key in ('video', 'portrait', 'provenance'):
        c = row['case']; p = root / 'inputs' / c[key]
        require(Path(c[key]).name == c[key] and not p.is_symlink() and
                sha(p) == c[key + '_sha256'], 'input changed: ' + key)
    return row


def audit_dir(value):
    p = Path(value)
    require(p.is_absolute() and p.resolve() == REMOTE / 'audit', 'audit root differs')
    return p


def validate_router(mode, alpha, radius, time_offset, start_frame, end_frame,
                    block_start, block_end, step_start, step_end, run_id, audit_dir):
    validate_job(run_id)
    require(Path(audit_dir) == REMOTE / 'audit/router', 'router audit differs')
    require((mode, alpha, radius, time_offset, start_frame, end_frame, block_start,
        block_end, step_start, step_end) == ('mass_preserve', 1., 0, 0, 0, 146, 0, 50, 6, 15),
        'fixed route parameters differ')


def prepare_loader_inputs(run, root=ROOT):
    import shutil
    root = Path(root); row = validate_job(run, root); c = row['case']
    folder = root / 'input'; folder.mkdir(exist_ok=True)
    for key in ('video', 'portrait'):
        p = folder / c[key]
        if not p.exists():
            with (root / 'inputs' / c[key]).open('rb') as before, p.open('xb') as after:
                shutil.copyfileobj(before, after)
        require(not p.is_symlink() and sha(p) == c[key + '_sha256'], 'loader source changed')
    return row


def prompt_pair_condition_checks(a, b):
    return {key + '_equal': a[key] == b[key] for key in
        ('input_video', 'native_vae_calls', 'qwen_presentation', 'target_latent_shapes')}
