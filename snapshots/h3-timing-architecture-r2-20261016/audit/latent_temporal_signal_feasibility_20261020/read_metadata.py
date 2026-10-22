"""Read existing JSON and stat files only; never deserialize tensors."""
import hashlib
import json
from pathlib import Path

root = Path('/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020')
def metadata(path):
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()
def stat(path):
    s = path.stat()
    return {'file': str(path), 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns}

condition_path = root / 'audit/r122_long_0039_shared_conditioning.json'
condition, condition_sha = metadata(condition_path)
reference = condition['native_vae_calls'][0]['latent']
result = {
    'scope': 'existing JSON metadata and filesystem stat only; no torch import or tensor load',
    'host': 'H3_SERVER_A', 'root': str(root),
    'condition_manifest': {'file': str(condition_path), 'sha256': condition_sha},
    'reference_latent': {**reference, **stat(root / 'audit' / reference['tensor_file'])},
    'runs': {},
}
for arm in ('native', 'forced'):
    path = root / f'audit/x0/r122_long_0039_seed2026101701_{arm}/manifest.json'
    d, sha = metadata(path)
    selected = [c for c in d['captures'] if c['step_zero_based'] in (0, 5, 9, 14, 19)]
    files = [stat(path.parent / c['file']) for c in selected]
    files.append(stat(path.parent / d['final_sampler_result']['file']))
    keys = ('status', 'geometry', 'target_latent_shapes', 'sigmas_video', 'normalization_stage',
            'normalization', 'snapshot_semantics', 'sampler', 'seed', 'callback_count',
            'capture_steps_zero_based', 'final_sampler_result', 'endpoint_comparison')
    result['runs'][arm] = {'manifest': {'file': str(path), 'sha256': sha},
                           **{k: d[k] for k in keys}, 'selected_captures': selected,
                           'existing_files': files}
print(json.dumps(result, ensure_ascii=False, indent=2))
