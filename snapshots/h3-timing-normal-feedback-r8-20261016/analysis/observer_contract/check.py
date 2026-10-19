"""CPU-only exact regression against retained R7 caches; never duplicates tensors."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import torch

ROOT = Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def signature(value):
    return {'shape': list(value.shape), 'dtype': str(value.dtype),
            'sha256': hashlib.sha256(value.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}

def main(source, destination):
    started = time.perf_counter()
    env, rng = dict(os.environ), torch.random.get_rng_state().clone()
    sys.path.insert(0, str(ROOT / 'extensions'))
    from H3FeedbackRouter.observer import FrozenGap5Observer, next_decision, VIDEO_SHAPE
    results_path = source / 'RESULTS.json'
    results = json.loads(results_path.read_text())
    frozen_results_sha = sha(results_path)
    manifest = json.loads((source / 'manifest.json').read_text())['files']
    refpath = source / 'inputs/audit/tensor_blobs/ce5a5e9d0a28d4f01c87e8bf69fd2bdd25357f9fdb5fcbe0c89508bed2f9cae2.pt'
    assert sha(refpath) == manifest[str(refpath.relative_to(source))]['sha256']
    reference = torch.load(refpath, map_location='cpu', weights_only=False)
    assert signature(reference) == results['reference']
    assert tuple(reference.shape) == VIDEO_SHAPE == (1, 24, 42, 36, 64)
    observer = FrozenGap5Observer(reference)
    checks = {item['file']: item for item in results['input_checks']}
    rows, expected_curves = [], []
    assert len(results['rows']) == 9
    for row in results['rows']:
        path = source / 'inputs/audit/x0/r7_s05_normal_native_x0' / row['file']
        file_sha = sha(path)
        assert file_sha == manifest[str(path.relative_to(source))]['sha256']
        payload = torch.load(path, map_location='cpu', weights_only=False)
        assert signature(payload['video']) == checks[row['file']]['video']
        assert signature(payload['audio']) == checks[row['file']]['audio']
        found = observer(payload['video'])
        expected = row['windows'][0]
        assert found['window_inclusive'] == [50, 65]
        assert len(found['curve']) == 49
        assert found == expected, row['file']
        expected_curves.append({'file': row['file'], 'window': expected})
        active, reason = next_decision(found, False)
        rows.append({'file': row['file'], 'file_sha256': file_sha, 'video': checks[row['file']]['video'],
                     'denoising_index_zero_based': row['denoising_index_zero_based'],
                     'full49_curve_and_rejections_exact': True,
                     'lag_frames': found['best']['lag_frames'] if found['best'] else None,
                     'accepted': found['accepted'], 'decision_from_inactive': {'active': active, 'reason': reason}})
    assert dict(os.environ) == env and torch.equal(rng, torch.random.get_rng_state())
    assert not torch.cuda.is_initialized()
    assert sha(results_path) == frozen_results_sha, 'source changed during validation'
    curves_bytes = (json.dumps(expected_curves, indent=2, sort_keys=True) + '\n').encode()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'expected_main_curves.json').write_bytes(curves_bytes)
    report = {'schema': 'r8-normal1024-frozen-observer-equivalence-v1', 'passed': True,
              'input_source_read_only': str(source), 'source_results_sha256': frozen_results_sha,
              'source_protocol_sha256': sha(source / 'PROTOCOL.json'),
              'r8_protocol_sha256': sha(ROOT / 'configs/protocol.json'),
              'observer_module_sha256': sha(ROOT / 'extensions/H3FeedbackRouter/observer.py'),
              'frozen_functions_sha256': sha(ROOT / 'extensions/H3FeedbackRouter/observer_frozen.py'),
              'expected_main_curves_sha256': hashlib.sha256(curves_bytes).hexdigest(),
              'reference': signature(reference), 'snapshots': rows,
              'snapshot_count': 9, 'points_checked': 441, 'environment_unchanged': True,
              'torch_rng_unchanged': True, 'cuda_initialized': False,
              'no_tensor_blobs_copied': True, 'elapsed_seconds': time.perf_counter() - started,
              'interpretation': 'Implementation equivalence only; R7 native trajectory values do not predict R8 feedback outcome.'}
    (destination / 'RESULTS.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--r7-observer-root', required=True, type=Path)
    p.add_argument('--output', default=Path(__file__).parent, type=Path)
    a = p.parse_args()
    main(a.r7_observer_root, a.output)
