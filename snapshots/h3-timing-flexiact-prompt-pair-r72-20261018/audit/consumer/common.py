"""CPU presentation contract; production code and numerical settings stay frozen."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PAIRS = ('fitness__game_man_5', 'one_leg__movie_man_9')
ARMS = ('p0', 'p1')
VALID, TOTAL, FPS, WIDTH, HEIGHT = 147, 158, 24, 1152, 768
INDICES = [round(i * (VALID - 1) / 5) for i in range(6)]
LABELS = ('1.动作参考视频', '2.P0 编辑后视频', '3.P1 编辑后视频')
HOST = 'H3_SERVER_B'
REMOTE = '/data3/researcher/h3_runs/timing_flexiact_prompt_pair_r72_20261018'
REMOTE_PYTHON = '/data3/researcher/ComfyUI/.venv/bin/python'
REMOTE_DEPS = '/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps'
CPU_LOCK = '/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)

def bound(path):
    path = Path(path)
    return {'file': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}

def run_id(pair, arm):
    require(pair in PAIRS and arm in ARMS, 'unknown pair/arm')
    return f'r72_{pair}_seed2026101701_{arm}'

def cases(root, pair):
    rows = [c for c in read(Path(root) / 'configs/scientific_contract.json')['cases'] if c['source_id'] == pair]
    require([r['arm'] for r in rows] == list(ARMS), 'case order differs')
    for row in rows:
        require(row['run_id'] == run_id(pair, row['arm']), 'case identity differs')
        require(row['geometry'] == {'width': WIDTH, 'height': HEIGHT, 'frames': TOTAL, 'fps': FPS}, 'case geometry differs')
        for key in ('video', 'portrait', 'provenance'):
            path = Path(root) / 'inputs' / row[key]
            require(path.is_file() and not path.is_symlink() and sha(path) == row[key + '_sha256'], key + ' bytes differ')
    return rows

def validate_gate(gate, pair):
    require(pair in PAIRS, 'unregistered pair')
    require(gate.get('schema') == 'r72-paired-runtime-gate-v1' and gate.get('passed') is True, 'actual R72 gate did not pass')
    require(gate.get('source_id') == pair and gate.get('prompt_versions') == ['P0', 'P1'], 'wrong pair/prompt versions')
    checks = gate.get('checks', {})
    require(bool(checks) and all(v is True for v in checks.values()), 'gate contains failed checks')
    for key in ('producer_seal', 'actual_runtime_device', 'input_video_equal', 'native_vae_calls_equal', 'qwen_presentation_equal', 'target_latent_shapes_equal', 'actual_initial_AV_noise_equal', 'independent_prompt_conditioning'):
        require(checks.get(key) is True, 'missing actual check: ' + key)
    require(set(gate['runs']) == set(ARMS), 'wrong arms')
    for arm, row in gate['runs'].items():
        require(row['run_id'] == run_id(pair, arm), 'run identity differs')
        require(row['valid_frames'] == VALID and row['NFE'] == row['Euler_updates'] == 20 and row['routed_blocks'] == 0, 'execution counts differ')
        require(row['evaluation_crop_xywh'] == [0, 0, WIDTH, HEIGHT] and row['evaluation_indices'] == list(range(0, 147, 3)) and row['evaluation_fps'] == 8, 'evaluation protocol differs')
        p = row['video']['properties']
        require((p['width'], p['height'], int(p['nb_read_frames']), p['avg_frame_rate']) == (WIDTH, HEIGHT, TOTAL, '24/1'), 'video shape differs')
    return gate

def readiness(root, pair):
    """Running/partially written JSON is pending; terminal failure is retained."""
    root = Path(root)
    states = []
    for arm in ARMS:
        run = run_id(pair, arm)
        job, hist = root / 'logs' / (run + '_job.json'), root / 'logs' / (run + '_history.json')
        if not job.exists():
            states.append('PENDING')
            continue
        try:
            j = read(job)
            h = read(hist) if hist.exists() else {}
        except json.JSONDecodeError:
            states.append('PENDING_WRITING')
            continue
        if j.get('status') in ('error', 'failed', 'submission_uncertain', 'unknown_missing') or h.get('status', {}).get('status_str') == 'error':
            return 'PRODUCER_FAILED'
        if j.get('status') != 'success' or h.get('status', {}).get('completed') is not True or h.get('status', {}).get('status_str') != 'success':
            states.append('PENDING')
        else:
            states.append('COMPLETE')
    if states != ['COMPLETE', 'COMPLETE']:
        return 'PENDING_WRITING' if 'PENDING_WRITING' in states else 'PENDING'
    gate = root / 'analysis/postrun' / pair / 'PAIR_RUNTIME_GATE.json'
    if gate.exists():
        validate_gate(read(gate), pair)
        return 'PASSED'
    return 'READY'

def probe(path):
    raw = subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time', '-of', 'json', str(path)], timeout=120)
    value = json.loads(raw)
    require(len(value['streams']) == 1, 'expected one video stream')
    stream = value['streams'][0]
    stream['pts'] = [float(f['best_effort_timestamp_time']) for f in value['frames']]
    return stream

def check_timeline(path, width=WIDTH, height=HEIGHT, frames=TOTAL):
    value = probe(path)
    require((value['width'], value['height'], value['avg_frame_rate'], len(value['pts'])) == (width, height, '24/1', frames), 'shape or frame count differs: ' + str(path))
    require(all(abs(t - i / FPS) < 1e-6 for i, t in enumerate(value['pts'])), 'PTS differ: ' + str(path))
    return value
