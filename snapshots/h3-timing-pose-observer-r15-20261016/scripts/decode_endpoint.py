#!/usr/bin/env python3
"""Validate seven frozen endpoints, then delegate unchanged R12 VAE decode.

No GPU work on import or with --validate-only. R10 native branch predictions are
counterfactual readouts on a Full-chosen history, not chosen sampler callbacks.
The adapter changes metadata validation only; it neither scales nor edits tensors.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R12 = Path('/data5/researcher/h3_runs/timing_native_observer_r12_20261016')
DECODER_SHA = '799e64e1d2e1dab3582fe4600fea810c388facbab447fd0887dc51f4a1494014'
R10_AUDIT = Path('/data5/researcher/h3_runs/timing_counterfactual_r10_20261016/audit/counterfactual/r10_s05_fixed_full_probe.json')
R10_AUDIT_SHA = 'd1f1a8b90860a2a84f91e81c8b2592bcee38dec8134b71cc19548f6155d53d43'
R14_MANIFEST_SHA = '0dde820f00f83b41f723348187d6c5911db28a0d7fb58c721be8e2e55bbbc83a'
GEOMETRY = {'width': 1312, 'height': 736, 'frames': 141, 'fps': 24}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def require(value, message):
    if not value:
        raise ValueError(message)

def decoder_module():
    path = R12 / 'scripts/decode_x0.py'
    require(sha(path) == DECODER_SHA, 'Frozen R12 decoder changed')
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('frozen_r12_vae_decoder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def selected_row(case, index):
    rows = json.loads((ROOT / 'analysis/input_inventory.json').read_text())['inputs']
    found = [r for r in rows if r['case'] == case and r['index'] == index]
    require(len(found) == 1, 'Case/index is not in the seven frozen endpoints')
    return found[0]

def validate_branch(path, core, expected):
    import torch
    require(sha(R10_AUDIT) == R10_AUDIT_SHA, 'R10 source audit hash changed')
    audit = json.loads(R10_AUDIT.read_text())
    c = audit['counterfactual']
    require(audit['status'] == 'complete' and audit['run_id'] == 'r10_s05_fixed_full_probe', 'R10 not complete')
    require(c['actual_model_nfe'] == 29 and c['actual_euler_updates'] == c['callback_count'] == 20, 'R10 execution counts differ')
    require(c['full_physical_indices'] == list(range(6, 15)), 'R10 chosen history differs')
    require(c['endpoint_scaling'] == 'video identity/audio divided4 on CPU copies; returned endpoint untouched', 'R10 normalization differs')
    rows = [r for r in c['branches'] if r['physical_index'] == expected['index'] and r['branch'] == 'native']
    require(len(rows) == 1, 'Missing/duplicate native branch')
    row = rows[0]
    require(Path(row['file']).resolve() == path.resolve() and row['file_sha256'] == expected['sha256'], 'Branch file binding differs')
    payload = torch.load(path, map_location='cpu', weights_only=True)
    require(isinstance(payload, dict) and set(payload) == {'video', 'audio', 'metadata'}, 'Unexpected branch payload')
    meta = payload['metadata']
    require(set(meta) == set(expected['metadata']) | {'raw_stream_signatures'}, 'Unexpected branch metadata keys')
    require(all(meta.get(k) == v for k, v in expected['metadata'].items()), 'Frozen branch metadata differs')
    require(all(row.get(k) == v for k, v in meta.items()), 'Branch metadata disagrees with audit')
    n = expected['index']
    require(meta['sigma'] == c['full_grid'][n] and meta['sigma_next'] == c['full_grid'][n + 1], 'Physical sigma binding differs')
    require(meta['seed'] == c['seed'] == 2026101311, 'R10 seed differs')
    require(row['global_rng_unchanged'] and row['condition_unchanged'] and row['full_grid_unchanged'], 'Branch side-effect guard failed')
    before = {}
    for name, shape in [('video', (1, 24, 42, 46, 82)), ('audio', (1, 32, 2, 235))]:
        value = payload[name]
        require(isinstance(value, torch.Tensor) and value.device.type == 'cpu' and value.dtype == torch.float32 and tuple(value.shape) == shape, 'Invalid stream shape/dtype')
        require(bool(torch.isfinite(value).all()), 'Nonfinite stream')
        before[name] = core.tensor_signature(value)
    require([before['video'], before['audio']] == row['normalized_stream_signatures'], 'Normalized stream signature differs')
    require([before['video'], core.tensor_signature(payload['audio'] * 4)] == row['raw_stream_signatures'], 'Raw/normalized scaling binding differs')
    require(before['video']['sha256'] == expected['video_sha256'], 'Frozen video signature differs')
    # Only metadata is adapted. The exact original video/audio objects are returned.
    converted = {'video': payload['video'], 'audio': payload['audio'], 'metadata': {
        'schema': 'h3-r15-counterfactual-endpoint-decode-adapter-v1',
        'run_id': audit['run_id'], 'snapshot_kind': 'counterfactual_native_endpoint',
        'physical_index_zero_based': n, 'nfe_index_zero_based': meta['nfe_index'],
        'is_chosen_sampler_callback': False, 'chosen_history_full_indices': c['full_physical_indices'],
        'normalization_stage': 'after_process_latent_out', 'audio_scale': 4.0,
        'video_latent_scale_factor': 1.0, 'geometry': GEOMETRY, 'seed': meta['seed'],
        'video': before['video'], 'audio': before['audio'], 'original_metadata': meta,
        'source_audit': str(R10_AUDIT), 'source_audit_sha256': R10_AUDIT_SHA,
        'source_snapshot_sha256': expected['sha256'], 'adapter_performed_tensor_operations': False,
        'validation_note': 'audio*4 is an ephemeral validation copy only; returned tensor objects and bytes unchanged'}}
    for name in ('video', 'audio'):
        require(converted[name] is payload[name] and core.tensor_signature(converted[name]) == before[name], 'Adapter mutated stream')
    return converted

def build_loader(decoder, expected):
    original = decoder.load_snapshot
    def load(path, core):
        require(path.resolve() == Path(expected['path']).resolve() and not path.is_symlink(), 'Snapshot path differs')
        require(sha(path) == expected['sha256'], 'Snapshot file SHA differs')
        if expected['case'] == 'r10_native':
            return validate_branch(path, core, expected)
        require(sha(path.parent / 'manifest.json') == R14_MANIFEST_SHA, 'R14 manifest SHA differs')
        payload = original(path, core)
        meta = payload['metadata']
        require(all(meta.get(k) == v for k, v in expected['metadata'].items()), 'R14 frozen metadata differs')
        require(meta['geometry'] == GEOMETRY and meta['video']['sha256'] == expected['video_sha256'], 'R14 geometry/video differs')
        return payload
    return load

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', required=True, choices=['r10_native', 'r14_native'])
    p.add_argument('--index', required=True, type=int)
    args, remainder = p.parse_known_args(argv)
    expected = selected_row(args.case, args.index)
    module = decoder_module()
    module.load_snapshot = build_loader(module, expected)
    return module.main([expected['path']] + remainder)

if __name__ == '__main__':
    raise SystemExit(main())
