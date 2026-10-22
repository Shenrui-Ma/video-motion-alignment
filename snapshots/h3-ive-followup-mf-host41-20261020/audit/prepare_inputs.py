"""Bind completed media to the existing official MF entry; CPU only."""
from pathlib import Path
import ast, hashlib, json, os, subprocess, sys, time

B = Path('/Users/researcher/DevProjects')
R = Path(__file__).resolve().parents[1]
BASE = B / 'h3-ive-context-mf-host41-20261020'
sys.path.insert(0, str(BASE / 'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes, media_info, validate_time_view

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def bound(p): return {'file': str(p), 'sha256': sha(p)}
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def link(p, q):
    q.parent.mkdir(parents=True, exist_ok=True)
    if not q.exists(): os.link(p, q)
    assert sha(p) == sha(q)

assert not (R / 'SEAL.json').exists()
for p in (BASE / 'scripts').glob('*.py'):
    ast.parse(p.read_text())
    link(p, R / 'scripts' / p.name)
if not (R / 'runtime').exists(): (R / 'runtime').symlink_to(BASE / 'runtime', target_is_directory=True)
for name in ['EXISTING_SERVICES.json', 'ive_NUMERIC.json']:
    link(BASE / 'configs' / name, R / 'configs' / name)
runtime = read(BASE / 'configs/RUNTIME.json')
runtime.update(remote_root='/data4/researcher/h3_runs/ive_followup_mf_20261020',
    peer_roots=[
        '/data4/researcher/h3_runs/timing_ive_full_context_long0161_r123_20261020',
        '/data4/researcher/h3_runs/timing_ive_full_context_long0034_r123_20261020',
        '/data4/researcher/h3_runs/timing_ive_full_context_long0122_r127_20261020'])
save(R / 'configs/RUNTIME.json', runtime)
for name in ['final_release.py', 'verify_inputs.py', 'collect.py']:
    link(BASE / 'audit' / name, R / 'audit' / name)

records = [
    ('long_0034', B / 'h3-ive-prompt-envelope-metrics-r123-20261020/variants/long0034_full_context', 'paired', 'r123_long_0034_full_context'),
    ('short_0362', B / 'h3-ive-book-color-metrics-r128-20261020', 'native', 'r128_short_0362_full_context'),
]
jobs, inputs = [], {}
for key, consumer, stage, inventory_id in records:
    mp = consumer / 'prepared' / key / stage / 'MF_INPUTS.json'
    m = read(mp)
    incoming = consumer / ('incoming_pairs' if stage == 'paired' else 'incoming') / key
    gate = incoming / ('PAIR_RUNTIME_GATE.json' if stage == 'paired' else 'NATIVE_RUNTIME_GATE.json')
    g = read(gate)
    assert g['passed'] and all(g['checks'].values())
    n = m['valid_frames']
    assert m['fps'] == 24 and m['crop_xywh'] == [16, 8, 1280, 720]
    assert m['evaluation_indices'] == list(range(n))
    crop = f'crop=1280:720:16:8,trim=end_frame={n},setsar=1'
    case = R / 'cases' / key
    roles = ['source', 'native'] + (['forced'] if stage == 'paired' else [])
    source = None
    targets = []
    for original_role in roles:
        role = 'guided' if original_role == 'forced' else original_role
        raw = m['raw_videos'][original_role]
        full = Path(raw['file'])
        assert sha(full) == raw['sha256']
        folder = case if role == 'source' else case / role
        destination = folder / ('source_full.mp4' if role == 'source' else 'full.mp4')
        score = folder / ('source_score.mp4' if role == 'source' else 'score.mp4')
        link(full, destination)
        if not score.exists():
            subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i', str(full),
                '-an', '-vf', crop, '-vsync', '0', '-c:v', 'libx264', '-qp', '0', '-preset', 'fast',
                '-pix_fmt', 'yuv420p', '-threads', '2', str(score)], check=True)
        hashes = frame_hashes(score, '/opt/homebrew/bin/ffmpeg')
        assert hashes == frame_hashes(full, '/opt/homebrew/bin/ffmpeg', crop)
        validate_time_view(media_info(score, '/opt/homebrew/bin/ffprobe'), n)
        if role == 'source':
            source = dict(source_full_sha256=raw['sha256'], source_score_sha256=sha(score), source_frame_md5=hashes)
        else:
            assert g['runs'][original_role]['video']['sha256'] == raw['sha256']
            targets.append(dict(role=role, full_file=role + '/full.mp4', full_sha256=raw['sha256'],
                score_file=role + '/score.mp4', score_sha256=sha(score), score_frame_md5=hashes,
                inventory_bindings=[{'id': inventory_id, 'field': role}], actual_consumer_input=bound(mp),
                actual_runtime_gate=bound(gate), evaluation_indices=list(range(n))))
    manifest = dict(schema='existing-official-mf-input-manifest-v1', benchmark='IVEBench', canonical_id=key,
        valid_frames=n, evaluation_frames=n, evaluation_fps=24, crop_xywh=m['crop_xywh'],
        source_cache=None, selection_sha256=sha(mp), targets=targets, **source)
    save(case / 'INPUTS.json', manifest)
    for p, name in [(mp, 'MF_INPUTS.json'), (gate, gate.name), (incoming / 'COLLECTION.json', 'COLLECTION.json')]:
        link(p, R / 'configs' / key / name)
    inputs[key] = bound(case / 'INPUTS.json')
    jobs.append({'case': key, 'role': 'source'})
    jobs.extend({'case': key, 'role': t['role']} for t in targets)
save(R / 'configs/PLAN.json', dict(groups=list(inputs), jobs=jobs, unique_targets=3, source_cache_count=0,
    status='ACTUAL_THREE_TARGETS_READY'))
save(R / 'audit/INPUTS_READY.json', dict(passed=True, inputs=inputs, source_count=2, generated_targets=3,
    serial_trackers=5, numerical_scripts_byte_identical=True, GPU_started=False,
    base_seal=bound(BASE / 'SEAL.json'), created_unix=time.time()))
print(json.dumps({'passed': True, 'targets': 3, 'trackers': 5, 'receipt': bound(R / 'audit/INPUTS_READY.json')}))
