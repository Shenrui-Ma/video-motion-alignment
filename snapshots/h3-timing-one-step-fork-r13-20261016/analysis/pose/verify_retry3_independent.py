"""CPU-only, read-only runtime acceptance; writes only analysis evidence."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import time
import traceback

os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['MKL_NUM_THREADS'] = '4'
import torch
torch.set_num_threads(4)
torch.set_num_interop_threads(1)


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def differences(a, b, path=''):
    if type(a) is not type(b):
        return [{'path': path, 'left': a, 'right': b}]
    if isinstance(a, dict):
        assert set(a) == set(b), (path, set(a) ^ set(b))
        return sum((differences(a[k], b[k], path + '.' + k) for k in a), [])
    if isinstance(a, list):
        assert len(a) == len(b), path
        return sum((differences(x, y, path + f'[{i}]') for i, (x, y) in enumerate(zip(a, b))), [])
    return [] if a == b else [{'path': path.lstrip('.'), 'left': a, 'right': b}]


def main(root):
    out = root / 'analysis/pose'
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    official = runpy.run_path(str(root / 'scripts/verify_fork.py'))
    base = official['verify'](root)
    Source, sig = official['Source'], official['readout'].tensor_signature
    source = Source(root / 'configs/source_manifest.json')
    audit = json.loads((root / 'audit/fork/r13_s05_one_step_fork.json').read_text())
    f = audit['fork']
    history = json.loads((root / 'logs/r13_s05_one_step_fork_history.json').read_text())
    assert history['status']['status_str'] == 'success' and history['status']['completed'] is True
    assert [p['source_euler_index'] for p in f['pairs']] == [6, 10, 14]
    assert f['source_indices'] == [6, 10, 14]
    assert f['global_rng_unchanged'] and f['materialization_rng_unchanged']
    assert f['output_is_report_only'] and not f['observer_controls_selection']
    predictions = f['predictions']
    pairs = {p['source_euler_index']: p for p in f['pairs']}
    rows = [p[s] for p in f['pairs'] for s in ('u_full', 'u_native')] + predictions
    snapshots = root / 'audit/fork/r13_s05_one_step_fork_snapshots'
    expected = {f'n{n:02d}_{suffix}.pt' for n in (6, 10, 14) for suffix in
                ('u_full_raw', 'u_native_raw', 'replay_full_endpoint', 'fork_native_endpoint')}
    actual = {p.name for p in snapshots.glob('*.pt')}
    assert len(rows) == 12 and actual == expected
    assert len({str(Path(r['file']).resolve()) for r in rows}) == 12
    assert {Path(r['file']).name for r in rows} == expected
    inventory = []
    loaded = {}
    for row in rows:
        p = snapshots / Path(row['file']).name
        assert p.resolve() == Path(row['file']).resolve()
        assert not p.is_symlink() and sha(p) == row['file_sha256']
        data = torch.load(p, map_location='cpu', weights_only=True)
        assert set(data) == {'packed', 'video', 'audio', 'metadata'}
        for key, shape in [('packed', (1, 1, 3817216)), ('video', (1, 24, 42, 46, 82)), ('audio', (1, 32, 2, 235))]:
            t = data[key]
            assert tuple(t.shape) == shape and t.dtype == torch.float32 and t.device.type == 'cpu'
            assert t.is_contiguous() and bool(torch.isfinite(t).all())
        reconstructed = torch.cat([data['video'].reshape(1, 1, -1), (data['audio'] * 4).reshape(1, 1, -1)], -1)
        assert torch.equal(data['packed'], reconstructed)
        assert sig(data['packed']) == row['packed_signature']
        assert [sig(data['video']), sig(data['audio'])] == row['normalized_stream_signatures']
        assert [sig(data['video']), sig(data['audio'] * 4)] == row['raw_stream_signatures']
        assert all(row[k] == v for k, v in data['metadata'].items())
        inventory.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p),
                          'tensor_signatures': {k: sig(data[k]) for k in ('packed', 'video', 'audio')},
                          'metadata': data['metadata'], 'finite': True, 'streams_repack_bitwise': True})
        loaded[p.name] = data
    assert len(f['pdd']) == 6
    head_records = []
    for h, r in zip(f['pdd'], predictions):
        assert h['head_mode'] == 'single_linear' and h['pdd_active'] is False and h['bank_size'] == 1
        assert h['start'] is None and h['stop'] is None and h['shifts'] == [12, 3]
        for k in ('source_euler_index', 'eval_euler_index', 'branch', 'probe_nfe'):
            assert h[k] == r[k]
        assert h['index'] == r['eval_euler_index']
        assert h['grid_signature'] == sig(torch.tensor(f['full_grid'], dtype=torch.float32))
        assert abs(h['sigma'] - f['full_grid'][h['index']]) < 1e-6
        assert h['sigma_next'] == f['full_grid'][h['index'] + 1]
        for name, width in [('video_out', 96), ('audio_out', 32)]:
            head = h['heads'][name]
            assert head['weight_shape'] == [width, 5376] and head['bias_shape'] == [width]
            assert head['weight_dtype'] == head['bias_dtype'] == 'torch.bfloat16'
        assert r['global_rng_unchanged'] and r['input_unchanged']
        assert r['condition_sha256'] == f['condition']['sha256']
        assert r['seed'] == f['seed'] == 2026101311
        head_records.append(h)
    replay = []
    for n in (6, 10, 14):
        pair = pairs[n]
        x, xrow = source.input(n)
        assert pair['source_x'] == xrow
        for side in ('native', 'full'):
            y, row = source.endpoint(n, side)
            assert pair['source_' + side] == row
        # Inputs were reconstructed on CUDA; use stored exact-replay comparison as
        # the arithmetic gate, not a potentially different CPU fused-op formula.
        expected_next = source.branches[n + 1, 'native']
        uf = loaded[f'n{n:02d}_u_full_raw.pt']
        endpoint = loaded[f'n{n:02d}_replay_full_endpoint.pt']
        known = source.tensor(expected_next)
        assert sig(uf['packed']) == expected_next['same_input']
        assert torch.equal(endpoint['video'], known['video']) and torch.equal(endpoint['audio'], known['audio'])
        replay.append({'source_index': n, 'evaluation_index': n + 1, 'input_actual_sha_equal': True,
                       'video_endpoint_tensor_equal': True, 'audio_endpoint_tensor_equal': True})

    r12 = root.parent / 'timing_native_observer_r12_20261016'
    c12 = json.loads((r12 / 'audit/counterfactual/r12_s05_native_observer.json').read_text())['counterfactual']
    b12 = {(r['physical_index'], r['branch']): r for r in c12['branches']}
    i12 = {r['physical_index']: r for r in c12['inputs']}
    diffs = differences(f['condition']['tree'], c12['conditioning']['tree'])
    assert {d['path'] for d in diffs} == {'original.positive[0].uuid', 'processed.positive[0].uuid'}
    assert len(diffs) == 2
    for n in (6, 7, 8, 9):
        a, b = source.branches[n, 'full'], b12[n, 'full']
        for k in ('same_input', 'raw_stream_signatures', 'normalized_stream_signatures', 'seed', 'reference_sha256', 'sigma', 'sigma_next'):
            assert a[k] == b[k]
    assert source.branches[10, 'native']['same_input'] == b12[10, 'native']['same_input']
    bridge_files = []
    def r12load(row, kind):
        p = Path(row['file'])
        assert p.resolve().is_relative_to(r12.resolve()) and sha(p) == row['file_sha256']
        d = torch.load(p, map_location='cpu', weights_only=True)
        assert all(row[k] == v for k, v in d['metadata'].items())
        if kind == 'input':
            assert sig(d['packed']) == row['packed_signature'] and torch.isfinite(d['packed']).all()
        else:
            assert [sig(d['video']), sig(d['audio'])] == row['normalized_stream_signatures']
            assert [sig(d['video']), sig(d['audio'] * 4)] == row['raw_stream_signatures']
            assert torch.isfinite(d['video']).all() and torch.isfinite(d['audio']).all()
        bridge_files.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)})
        return d
    input10 = r12load(i12[10], 'input')
    native10 = r12load(b12[10, 'native'], 'endpoint')
    native11 = r12load(b12[11, 'native'], 'endpoint')
    source_input10 = source.input(10)[0]
    source_native10 = source.tensor(source.branches[10, 'native'])
    assert torch.equal(input10['packed'], source_input10)
    assert pairs[10]['source_x']['packed_signature'] == i12[10]['packed_signature']
    assert torch.equal(source_native10['video'], native10['video']) and torch.equal(source_native10['audio'], native10['audio'])
    candidate = loaded['n10_u_native_raw.pt']
    fork11 = loaded['n10_fork_native_endpoint.pt']
    pred11 = next(r for r in predictions if r['source_euler_index'] == 10 and r['branch'] == 'fork_native')
    assert sig(candidate['packed']) == b12[11, 'native']['same_input'] == pred11['input_signature']
    assert pred11['sigma'] == b12[11, 'native']['sigma'] and pred11['sigma_next'] == b12[11, 'native']['sigma_next']
    assert torch.equal(fork11['video'], native11['video']) and torch.equal(fork11['audio'], native11['audio'])
    assert pred11['raw_stream_signatures'] == b12[11, 'native']['raw_stream_signatures']
    bridge = {'passed': True, 'source_index': 10, 'evaluation_index': 11, 'condition_differences': diffs,
              'r13_condition_sha256': f['condition']['sha256'], 'r12_condition_sha256': c12['conditioning']['sha256'],
              'prefix_full6to9_actual_signatures_equal': True, 'raw_input10_tensor_equal': True,
              'native10_video_audio_tensor_equal': True, 'candidate_input11': sig(candidate['packed']),
              'input11_evidence_limit': 'R13 raw candidate tensor matches R12 actual model-input SHA; R12 did not separately save input11 tensor.',
              'native11_normalized_video_audio_bitwise_equal': True, 'native11_raw_signatures': pred11['raw_stream_signatures'],
              'r12_files_checked': bridge_files, 'no_claim_for_n14_bridge': True}
    result = {'schema': 'h3-r13-independent-retry3-acceptance-v1', 'passed': True,
              'official_verifier_passed': base['passed'], 'exact_pairs': [6, 10, 14],
              'snapshot_file_count': 12, 'inventory': inventory, 'single_head_records': head_records,
              'replay_pairs': replay, 'r12_index11_bridge': bridge,
              'NFE': 6, 'sampler_updates': 0, 'sampler_callbacks': 0,
              'candidate_construction': 'Six Euler-formula candidate buffers; zero sampler trajectory updates is not zero mathematical computation.',
              'wall_seconds': f['wall_seconds'], 'model_seconds': base['model_seconds'],
              'condition_hash_seconds': base['condition_hash_seconds'],
              'archive_readout_seconds': base['archive_readout_seconds'],
              'candidate_archive_seconds': sum(p[s]['archive_readout_seconds'] for p in f['pairs'] for s in ('u_full', 'u_native')),
              'reconstruction_seconds': sum(p['reconstruction_seconds'] for p in f['pairs']),
              'condition_materialization_seconds': f['condition_materialization_seconds'],
              'observations': base['observations'], 'CPU_verification_seconds': time.time() - started,
              'scope': 'Three selected one-step counterfactuals on a historical trajectory, no new complete video or pose result.'}
    (out / 'complete_integrity_gate.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('passed', 'exact_pairs', 'snapshot_file_count', 'NFE', 'wall_seconds', 'CPU_verification_seconds')}))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    lock = Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            main(args.root)
        except Exception:
            error = {'passed': False, 'traceback': traceback.format_exc(), 'epoch': time.time()}
            target = args.root / 'analysis/pose/verification_failure.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(error, indent=2) + '\n')
            raise
