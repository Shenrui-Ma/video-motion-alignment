"""Bind the actual R119 Native output to the existing official 105-frame source cache."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
CONSUMER = BASE / 'h3-ive-basketball-official-prompt-metrics-r119-20261019'
OLD = BASE / 'h3-ive-followup-quantitative-r97-r99-r100-20261019/audit/recovery_20261019/r100_short_0114'
sys.path.insert(0, str(ROOT / 'runtime/ive/metric_runtime'))
from ive_mf_adapter import frame_hashes, media_info, validate_time_view, verify_vendor

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def bound(p): return {'file': str(p), 'sha256': sha(p)}
def save(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    assert not p.exists(), str(p)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def copy(p, q):
    q.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, q)
    assert sha(p) == sha(q)

assert not (ROOT / 'SEAL.json').exists()
manifest_path = CONSUMER / 'prepared/short_0114/native/MF_INPUTS.json'
m = read(manifest_path)
assert m['valid_frames'] == 105 and m['fps'] == 24 and m['crop_xywh'] == [16, 8, 1280, 720]
assert m['evaluation_indices'] == list(range(105)) and set(m['raw_videos']) == {'source', 'native'}
gate_path = CONSUMER / 'incoming/short_0114/NATIVE_RUNTIME_GATE.json'
gate = read(gate_path)
assert gate['passed'] and all(gate['checks'].values())
assert gate['runs']['native']['video']['sha256'] == m['raw_videos']['native']['sha256']
release = read(ROOT / 'configs/PRODUCER_RELEASE.json')
assert release['passed'] and release['process_absent'] and release['CUDA_allocation_absent']
case = ROOT / 'cases/short_0114'
for role in ('source', 'native'):
    x = m['raw_videos'][role]; assert sha(x['file']) == x['sha256']
    copy(Path(x['file']), case / ('source_full.mp4' if role == 'source' else 'native/full.mp4'))
copy(OLD / 'cases/r100_short_0114/inputs/source_score.mp4', case / 'source_score.mp4')
cache = OLD / 'actual_host41/cases/r100_short_0114/tracks/source'
for n in ('REPORT.json', 'tracks.npz'): copy(cache / n, case / 'tracks/source' / n)
r = read(case / 'tracks/source/REPORT.json')
assert r['passed'] and r['effective_frame_count'] == 105 and r['score_frame_indices'] == list(range(105))
assert r['source_prepared_sha256'] == sha(case / 'source_full.mp4')
assert r['source_score_sha256'] == sha(case / 'source_score.mp4')
assert r['tracks_sha256'] == sha(case / 'tracks/source/tracks.npz')
assert r['checkpoint_sha256'] == read(ROOT / 'configs/RUNTIME.json')['checkpoint_sha256']
assert r['tracker'] == {'grid_size': 10, 'grid_query_frame': 0, 'backward_tracking': False, 'offline': True, 'window_len': 60}
assert r['vendor']['manifest_sha256'] == verify_vendor()['manifest_sha256']
crop = 'crop=1280:720:16:8,trim=end_frame=105,setsar=1'
ffmpeg = '/opt/homebrew/bin/ffmpeg'; ffprobe = '/opt/homebrew/bin/ffprobe'
source_md5 = frame_hashes(case / 'source_score.mp4', ffmpeg)
assert source_md5 == r['decoded_frame_md5'] == frame_hashes(case / 'source_full.mp4', ffmpeg, crop)
validate_time_view(media_info(case / 'source_score.mp4', ffprobe), 105)
score = case / 'native/score.mp4'
assert not score.exists()
subprocess.run([ffmpeg, '-v', 'error', '-threads', '2', '-i', str(case / 'native/full.mp4'), '-an', '-vf', crop,
                '-vsync', '0', '-c:v', 'libx264', '-qp', '0', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-threads', '2', str(score)], check=True)
target_md5 = frame_hashes(score, ffmpeg)
assert target_md5 == frame_hashes(case / 'native/full.mp4', ffmpeg, crop)
validate_time_view(media_info(score, ffprobe), 105)
target = {'role': 'native', 'full_file': 'native/full.mp4', 'full_sha256': sha(case / 'native/full.mp4'),
          'score_file': 'native/score.mp4', 'score_sha256': sha(score), 'score_frame_md5': target_md5,
          'inventory_bindings': [{'id': 'r119_short_0114_official_prompt', 'field': 'native'}]}
save(case / 'INPUTS.json', {'schema': 'r119-native-official-mf-v1', 'benchmark': 'IVEBench', 'canonical_id': 'short_0114',
     'valid_frames': 105, 'evaluation_frames': 105, 'evaluation_fps': 24, 'crop_xywh': [16, 8, 1280, 720],
     'source_full_sha256': sha(case / 'source_full.mp4'), 'source_score_sha256': sha(case / 'source_score.mp4'),
     'source_frame_md5': source_md5, 'source_cache': {'report_sha256': sha(case / 'tracks/source/REPORT.json'), 'tracks_sha256': r['tracks_sha256']},
     'selection_sha256': r['selection_sha256'], 'targets': [target], 'consumer_input_sha256': sha(manifest_path),
     'actual_native_gate_sha256': sha(gate_path), 'guided_generated': False})
save(ROOT / 'configs/PLAN.json', {'groups': ['short_0114'], 'jobs': [{'case': 'short_0114', 'role': 'native'}]})
for src, dst in [(manifest_path, 'CONSUMER_INPUTS.json'), (gate_path, 'NATIVE_RUNTIME_GATE.json'),
                 (CONSUMER / 'incoming/short_0114/COLLECTION.json', 'COLLECTION.json'),
                 (BASE / 'h3-timing-ive-basketball-official-prompt-r119-20261019/audit/NATIVE_INDEPENDENT_REVIEW.json', 'ROOT_DECISION.json')]:
    copy(src, ROOT / 'configs' / dst)
save(ROOT / 'configs/CACHE_REUSE.json', {'passed': True, 'source_full': bound(case / 'source_full.mp4'),
     'source_score': bound(case / 'source_score.mp4'), 'cached_tracks': bound(cache / 'tracks.npz'),
     'cached_report': bound(cache / 'REPORT.json'), 'source_pixel_and_time_equal': True, 'frame_count': 105,
     'checkpoint_sha256': r['checkpoint_sha256'], 'tracker': r['tracker'], 'official_vendor': r['vendor'],
     'original_runtime': {'torch': r['torch_version'], 'cuda': r['cuda_version'], 'gpu_uuid': r['gpu_uuid']}})
files = {str(p.relative_to(ROOT)): sha(p) for sub in ['scripts', 'configs', 'runtime', 'cases', 'tests']
         for p in (ROOT / sub).rglob('*') if p.is_file() and ('__pycache__' not in p.parts or 'official_source' in p.parts)}
save(ROOT / 'SEAL.json', {'schema': 'r119-official-mf-host9-v1', 'files': files, 'GPU_started': False,
     'official_numerical_source': 'byte-identical to completed R115 IVE runtime', 'created_unix': time.time()})
save(ROOT / 'audit/PREPARE_RECEIPT.json', {'passed': True, 'seal_sha256': sha(ROOT / 'SEAL.json'), 'file_count': len(files),
     'generated_roles': ['native'], 'source_cache_reused': True, 'source_frame_count': 105, 'fps': 24,
     'source_frame_md5_equal': True, 'target_frame_md5_equal': True, 'GPU_started': False})
print(json.dumps(read(ROOT / 'audit/PREPARE_RECEIPT.json')))
