"""Fixed, CPU-only diagnostic of existing R122 latent snapshots. JSON stdout."""
import os
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
import gc
import hashlib
import json
import resource
import time
from pathlib import Path
started = time.perf_counter()
import torch
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
assert not torch.cuda.is_initialized()

PROTOCOL_SHA = 'fb58f8c32106206183f83ff671d61ed5f52e77baab5bdf3cbd30dd6db87e05a1'
ROOT = Path('/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020')
SHAPE = (1, 24, 32, 46, 82)
STEPS = (5, 10, 14, 19)
LAGS = tuple(range(-6, 7))
SUPPORT = tuple(range(6, 24))

def sha_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()

def sha_tensor(t):
    return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()

bins, cursor = [], 0
for i in range(32):
    n = (1, 4, 4, 4, 4)[i % 5]
    bins.append({'index': i, 'frames': [cursor, cursor+n-1],
                 'center_frame': cursor+(n-1)/2,
                 'valid_count': max(0, min(106, cursor+n)-cursor)})
    cursor += n
assert cursor == 107
centers = torch.tensor([b['center_frame']/24 for b in bins], dtype=torch.float64)
dt = centers[1:] - centers[:-1]

def features(video):
    assert tuple(video.shape) == SHAPE and video.dtype == torch.float32
    assert video.device.type == 'cpu' and bool(torch.isfinite(video).all())
    # Float64 difference and dot product; reference and prediction share the exact grid.
    rows = video[0].permute(1, 0, 2, 3).reshape(32, -1).to(torch.float64)
    for phase in range(5):
        selected = list(range(phase, 32, 5))
        rows[selected] -= rows[selected].mean(dim=0, keepdim=True)
    derivative = (rows[1:] - rows[:-1]) / dt[:, None]
    norms = torch.linalg.vector_norm(derivative, dim=1)
    good = norms > 0
    normalized = torch.zeros_like(derivative)
    normalized[good] = derivative[good] / norms[good, None]
    return normalized, norms, good

def analyze(ref, pred, ref_good, pred_good):
    cosine = ref @ pred.T
    good = ref_good[:, None] & pred_good[None, :]
    cosine[~good] = float('nan')
    common = [i for i in SUPPORT if all(bool(good[i, i+lag]) for lag in LAGS)]
    scores = [{'lag_bins': lag, 'cosine_mean': float(cosine[common, [i+lag for i in common]].mean()) if common else None,
               'n': len(common)} for lag in LAGS]
    finite_scores = [s for s in scores if s['cosine_mean'] is not None]
    maximum = max((s['cosine_mean'] for s in finite_scores), default=None)
    argmax = []
    for i in range(30):
        candidates = [j for j in range(max(0, i-6), min(29, i+6)+1) if bool(good[i,j])]
        best = max((float(cosine[i,j]) for j in candidates), default=None)
        ties = [j for j in candidates if float(cosine[i,j]) == best]
        argmax.append({'reference_difference': i, 'prediction_candidates': candidates,
                       'candidate_scores': [float(cosine[i,j]) for j in candidates],
                       'argmax_prediction_indices': ties,
                       'argmax_lags_bins': [j-i for j in ties], 'max_cosine': best})
    matrix = [[float(cosine[i,j]) if bool(good[i,j]) else None for j in range(31)] for i in range(31)]
    return {'cosine_matrix': matrix, 'lag_scores': scores,
            'max_score_lags': [s['lag_bins'] for s in finite_scores if s['cosine_mean'] == maximum],
            'common_support_planned': list(SUPPORT), 'common_support_used': common,
            'unknown_common_rows': sorted(set(SUPPORT)-set(common)),
            'row_neighborhood_argmax': argmax, 'padding_difference_excluded': [30]}

condition_path = ROOT / 'audit/r122_long_0039_shared_conditioning.json'
condition = json.loads(condition_path.read_text())
reference_info = condition['native_vae_calls'][0]['latent']
reference_path = ROOT / 'audit' / reference_info['tensor_file']
load_start = time.perf_counter()
reference_tensor = torch.load(reference_path, map_location='cpu', weights_only=True)
assert sha_tensor(reference_tensor) == reference_info['sha256']
ref, ref_activity, ref_good = features(reference_tensor)
raw_delayed = torch.cat([reference_tensor[:,:,:1].repeat(1,1,3,1,1), reference_tensor[:,:,:-3]], dim=2)
pre_ref, pre_activity, pre_good = features(raw_delayed)
pre_shift_result = analyze(ref, pre_ref, ref_good, pre_good)
del reference_tensor, raw_delayed, pre_ref, pre_activity, pre_good
reference_seconds = time.perf_counter()-load_start

self_result = analyze(ref, ref, ref_good, ref_good)
assert all(abs(self_result['cosine_matrix'][i][i]-1) < 1e-10 for i in range(31) if ref_good[i])
assert abs(next(s['cosine_mean'] for s in self_result['lag_scores'] if s['lag_bins'] == 0)-1) < 1e-10
shifted = torch.cat([ref[:1].repeat(3,1), ref[:-3]])
shifted_good = torch.cat([ref_good[:1].repeat(3), ref_good[:-3]])
shift_result = analyze(ref, shifted, ref_good, shifted_good)
assert abs(next(s['cosine_mean'] for s in shift_result['lag_scores'] if s['lag_bins'] == 3)-1) < 1e-10
assert 3 in shift_result['max_score_lags']
del shifted, shifted_good

result = {'schema': 'r122-phase-centered-latent-temporal-signal-diagnostic-v1',
          'preprocessing': {'phase_period':5,'mean_counts':[7,7,6,6,6],'scope':'independent per video/snapshot and channel/pixel; all32 positions'},
          'synthetic_raw_latent_delay_before_preprocessing': pre_shift_result,
          'protocol_sha256': PROTOCOL_SHA,
          'scope': 'Exploratory signal diagnostic, not benchmark metric or deployed method',
          'physical_bins': bins, 'difference_dt_seconds': dt.tolist(),
          'reference': {'file': str(reference_path), 'file_sha256': sha_file(reference_path),
                        'tensor_sha256': reference_info['sha256'], 'shape': list(SHAPE),
                        'condition_manifest_sha256': sha_file(condition_path),
                        'activity_l2_per_second': ref_activity.tolist(),
                        'zero_norm_indices': [i for i in range(31) if not ref_good[i]],
                        'read_and_feature_seconds': reference_seconds},
          'controls': {'reference_self': self_result, 'synthetic_feature_delay_3bins': shift_result},
          'runs': {}}

for arm in ('native', 'forced'):
    manifest_path = ROOT / f'audit/x0/r122_long_0039_seed2026101701_{arm}/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['status'] == 'complete'
    captures = {c['step_zero_based']: c for c in manifest['captures']}
    records = []
    for step in STEPS:
        step_started = time.perf_counter()
        capture = captures[step]
        p = manifest_path.parent / capture['file']
        payload = torch.load(p, map_location='cpu', weights_only=True)
        video = payload['video']
        video_sha = sha_tensor(video)
        assert video_sha == capture['video']['sha256']
        assert payload['metadata']['step_zero_based'] == step
        prediction, activity, pred_good = features(video)
        analysis = analyze(ref, prediction, ref_good, pred_good)
        records.append({'step_zero_based': step, 'sigma_video': capture['sigma_video'],
                        'file': str(p), 'file_sha256': sha_file(p), 'video_tensor_sha256': video_sha,
                        'activity_l2_per_second': activity.tolist(),
                        'zero_norm_indices': [i for i in range(31) if not pred_good[i]],
                        **analysis, 'read_and_analysis_seconds': time.perf_counter()-step_started})
        del payload, video, prediction, activity, pred_good
        gc.collect()
    result['runs'][arm] = {'manifest_file': str(manifest_path), 'manifest_sha256': sha_file(manifest_path),
                           'captures': records}

a, b = (result['runs'][arm]['captures'][0] for arm in ('native','forced'))
result['controls']['step5_prefix'] = {
    'video_tensor_sha_equal': a['video_tensor_sha256'] == b['video_tensor_sha256'],
    'cosine_matrix_exact_equal': a['cosine_matrix'] == b['cosine_matrix'],
    'activity_exact_equal': a['activity_l2_per_second'] == b['activity_l2_per_second']}
assert all(result['controls']['step5_prefix'].values())
result['execution'] = {'cpu_only': not torch.cuda.is_initialized(), 'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'],
                       'torch_version': str(torch.__version__), 'threads': torch.get_num_threads(),
                       'interop_threads': torch.get_num_interop_threads(),
                       'wall_seconds': time.perf_counter()-started,
                       'maxrss_KiB_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       'pid': os.getpid(), 'uid': os.getuid()}
assert result['execution']['cpu_only']
print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
