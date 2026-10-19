"""R14 native/off artifact and execution audit; CPU only, no model imports."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
import torch
torch.set_num_threads(4)
torch.set_num_interop_threads(1)

ROOT = Path('/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016')
RUN = 'r14_s05_seed1313_native_host9'
SEED = 2026101313


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def sig(t):
    return {'shape': list(t.shape), 'dtype': str(t.dtype), 'bytes': t.numel() * t.element_size(),
            'sha256': hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}


def main():
    start = time.time()
    audit = json.loads((ROOT / 'audit/feedback' / (RUN + '.json')).read_text())
    f = audit['feedback']
    assert audit['status'] == 'complete' and f['policy'] == 'off' and f['fixed_indices'] == []
    assert audit['completed_forward_calls'] == 20 and audit['calls_by_forward'] == [50] * 20
    assert audit['completed_calls'] == 1000 and audit['routed_calls'] == 0
    assert audit['routed_by_forward'] == [0] * 20 and audit['routed_by_block'] == [0] * 50
    assert f['callback_count'] == 20 and f['active_indices'] == [] and f['active_forward_count'] == 0
    assert f['active_sigma_intervals'] == [] and f['sigma_dose'] == 0
    assert f['seed'] == SEED and f['sampler'] == 'sample_euler'
    assert len(f['sigmas_video']) == 21 and f['sigmas_video'][-1] == 0
    assert [x['forward_index'] for x in f['latched_forwards']] == list(range(20))
    assert all(not x['active'] for x in f['latched_forwards'])
    observations = []
    assert [x['callback_index'] for x in f['observations']] == list(range(5, 20))
    for x in f['observations']:
        index = x['callback_index']; terminal = index == 19; o = x['observation']
        lag = None if o.get('best') is None else o['best']['lag_frames']
        if not o['accepted']: proposal, reason = False, 'OFF_UNKNOWN'
        elif lag >= 4: proposal, reason = True, 'ON_DELAYED'
        elif -2 <= lag <= 2: proposal, reason = False, 'OFF_ALIGNED'
        elif lag == 3: proposal, reason = False, 'HOLD_LAG3'
        else: proposal, reason = False, 'OFF_ADVANCED'
        assert x['observer_proposed_active'] == proposal and x['reason'] == reason
        assert x['current_forward_active'] is False
        assert x['aligned_streak_before'] == x['aligned_streak_proposed'] == x['aligned_streak_after'] == 0
        assert x['terminal_audit_only'] == terminal
        assert x['next_forward_index'] == (None if terminal else index + 1)
        assert x['next_active'] == (None if terminal else False)
        assert x['applied_reason'] == ('TERMINAL_AUDIT_ONLY' if terminal else 'POLICY_OFF')
        observations.append({'callback_index': index, 'lag': lag, 'accepted': o['accepted'],
                             'proposed_active': proposal, 'actually_applied': False, 'reason': reason,
                             'readout_seconds': x['readout_seconds']})
    folder = ROOT / 'audit/x0' / RUN
    manifest = json.loads((folder / 'manifest.json').read_text())
    indices = [5, 6, 7, 8, 9, 10, 15, 19]
    assert manifest['status'] == 'complete' and manifest['run_id'] == RUN and manifest['seed'] == SEED
    assert manifest['capture_steps_zero_based'] == indices
    captures = manifest['captures']; entries = captures + [manifest['final_sampler_result']]
    assert [x['step_zero_based'] for x in captures] == indices
    assert [x['file'] for x in captures] == [f'x0_step{i:03d}.pt' for i in indices]
    assert manifest['final_sampler_result']['file'] == 'sampler_final.pt'
    assert {p.name for p in folder.glob('*.pt')} == {x['file'] for x in entries} and len(entries) == 9
    assert manifest['sigmas_video'] == f['sigmas_video'] and manifest['noise'] == f['noise']
    inventory = []
    for row in entries:
        p = folder / row['file']; data = torch.load(p, map_location='cpu', weights_only=True)
        assert data['metadata']['run_id'] == RUN and data['metadata']['seed'] == SEED
        for k, value in data['metadata'].items(): assert row[k] == value, k
        streams = {}
        for name, shape in [('video', [1, 24, 42, 46, 82]), ('audio', [1, 32, 2, 235])]:
            t = data[name]
            assert list(t.shape) == shape and t.dtype == torch.float32 and torch.isfinite(t).all()
            streams[name] = sig(t)
            assert streams[name] == row[name]
        inventory.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p),
                          'metadata': data['metadata'], 'streams': streams, 'finite': True})
    noise = json.loads((ROOT / 'audit' / (RUN + '_noise.json')).read_text())
    assert noise['signature']['seed'] == SEED and noise['run_id'] == RUN
    np = Path(noise['cache_file']); assert np.resolve().is_relative_to((ROOT / 'audit').resolve())
    nd = torch.load(np, map_location='cpu', weights_only=True)
    assert nd['signature'] == noise['signature'] and len(nd['tensors']) == 2
    for t, s in zip(nd['tensors'], noise['actual_noise_streams']):
        actual = sig(t); assert all(actual[k] == v for k, v in s.items()) and torch.isfinite(t).all()
    packed_noise = torch.cat([t.reshape(1, 1, -1) for t in nd['tensors']], -1)
    assert sig(packed_noise) == f['noise']
    # Verify the actual clean reference blobs; the large prepared RGB blobs are
    # compared by recorded signatures in the separate conditioning pair report.
    c = json.loads((ROOT / 'audit' / (RUN + '_conditioning.json')).read_text())
    refs = []
    for row in c['native_vae_calls']:
        s = row['latent']; p = ROOT / 'audit' / s['tensor_file']
        d = torch.load(p, map_location='cpu', weights_only=True)
        actual = sig(d)
        assert all(actual[k] == v for k, v in s.items() if k != 'tensor_file') and torch.isfinite(d).all()
        refs.append({'path': str(p), 'file_sha256': sha(p), 'tensor': actual})
    # Real source files rather than a provenance assertion.
    comfy = Path('/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI')
    core = json.loads((ROOT / 'configs/parent_core_hashes.json').read_text())
    actual_core = {rel: sha(comfy / rel) for rel in core}
    assert actual_core == core
    bundle = json.loads((ROOT / 'configs/bundle_manifest.json').read_text())
    actual_bundle = {rel: sha(ROOT / rel) for rel in bundle['files']}
    assert actual_bundle == bundle['files']
    result = {'schema': 'r14-native-off-independent-inventory-v1', 'passed': True, 'run_id': RUN,
              'seed': SEED, 'actual_NFE': 20, 'sampler_updates': 20, 'callbacks': 20,
              'completed_blocks': 1000, 'routed_blocks': 0, 'observer_is_passive': True,
              'active_indices': [], 'observations': observations, 'capture_indices': indices,
              'capture_inventory': inventory, 'capture_manifest_sha256': sha(folder / 'manifest.json'),
              'clean_reference_inventory': refs, 'noise_file': str(np), 'noise_file_sha256': sha(np),
              'packed_noise': sig(packed_noise), 'actual_core_sha256': actual_core,
              'bundle_file_count': len(actual_bundle), 'bundle_file_sha256': actual_bundle,
              'observer_seconds_total': f['observer_seconds_total'],
              'observer_compute_seconds': sum(x['observer_compute_seconds'] for x in f['observations']),
              'cpu_verification_seconds': time.time() - start, 'new_gpu_started': False,
              'augmentation_limit': 'Actual seed and clean reference bytes checked; native seed-dependent reference augmentation follows pinned model code. Its post-augmentation tensor was not separately archived.'}
    out = ROOT / 'analysis/pose/replication/complete_integrity_gate.json'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'seed': SEED, 'capture_files': 9, 'actual_NFE': 20,
                      'internal_final_lag': observations[-1]['lag']}))


if __name__ == '__main__':
    lock = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        main()
