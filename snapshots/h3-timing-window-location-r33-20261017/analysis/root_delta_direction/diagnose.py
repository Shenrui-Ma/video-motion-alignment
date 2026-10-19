"""Measure two archived same-state intervention directions on CPU."""
import argparse
import copy
import fcntl
import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_condition(record):
    tree = record['tree']
    encoded = json.dumps(tree, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert hashlib.sha256(encoded).hexdigest() == record['sha256']
    tree = copy.deepcopy(tree)
    a = tree['original']['positive'][0]['uuid']
    b = tree['processed']['positive'][0]['uuid']
    assert a == b and str(uuid.UUID(a)) == a
    tree['original']['positive'][0]['uuid'] = '<allowed-run-UUID>'
    tree['processed']['positive'][0]['uuid'] = '<allowed-run-UUID>'
    return tree


def geometry(a, b):
    """Both directions use the same coordinate scale; no centering."""
    import torch
    a, b = a.double().reshape(-1), b.double().reshape(-1)
    assert a.numel() == b.numel()
    aa, bb, ab = float(a.dot(a)), float(b.dot(b)), float(a.dot(b))
    if aa == 0 or bb == 0:
        return {'status': 'zero_direction', 'squared_norm_a': aa, 'squared_norm_b': bb}
    cosine = max(-1., min(1., ab / math.sqrt(aa * bb)))
    gram = torch.tensor([[aa, ab], [ab, bb]], dtype=torch.float64)
    eig = torch.linalg.eigvalsh(gram).clamp_min(0)
    norm_eig = torch.tensor([1-abs(cosine), 1+abs(cosine)], dtype=torch.float64)
    beta_b_from_a = ab / aa
    residual = b - beta_b_from_a*a
    relative_residual = float(torch.linalg.vector_norm(residual)) / math.sqrt(bb)
    return {
        'status': 'measured', 'squared_norm_a': aa, 'squared_norm_b': bb,
        'norm_b_over_a': math.sqrt(bb / aa), 'cosine': cosine,
        'best_unconstrained_scalar_b_from_a': beta_b_from_a,
        'relative_L2_projection_residual_b': relative_residual,
        'raw_2column_singular_values_ascending': eig.sqrt().tolist(),
        'unit_2column_singular_values_ascending': norm_eig.sqrt().tolist(),
        'unit_sigma_min_over_max': math.sqrt((1-abs(cosine))/(1+abs(cosine))),
    }


def selftest():
    import torch
    a = torch.tensor([1., 0.])
    assert geometry(a, 2*a)['relative_L2_projection_residual_b'] == 0
    assert geometry(a, -2*a)['cosine'] == -1
    assert geometry(a, torch.tensor([0., 1.]))['relative_L2_projection_residual_b'] == 1
    assert geometry(a, torch.zeros_like(a))['status'] == 'zero_direction'
    b = torch.tensor([1., 1.])
    g = geometry(a, b)
    assert abs(g['cosine'] - 2**-.5) < 1e-12
    assert abs(g['relative_L2_projection_residual_b'] - 2**-.5) < 1e-12
    assert abs(geometry(a*3, b*7)['cosine']-g['cosine']) < 1e-12
    print('7 synthetic invariants PASS')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.execute:
        print('Prepared; execute requires CPU-only runtime and frozen inputs.')
        return
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    for name, digest in json.loads((HERE/'FREEZE.json').read_text())['files'].items():
        assert sha(HERE/name) == digest, name
    assert not (HERE/'RESULT.json').exists()
    base = Path('/data5/researcher/h3_runs')
    lock = base/'timing_architecture_r2_20261016/analysis/pose/consumer.lock'
    with lock.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(75)
        for request in (base/'timing_auto_bedside_r35_20261017/audit/observations').glob('*/request.json'):
            if not (request.parent/'response.json').exists():
                raise SystemExit(75)
        import torch
        torch.set_num_threads(4)
        assert not torch.cuda.is_initialized()
        protocol = json.loads((HERE/'PROTOCOL.json').read_text())
        started = time.monotonic()
        pairs = []
        for case in protocol['cases']:
            pair = {}
            for branch in ['native', 'full']:
                p = Path(case['files'][branch]['path'])
                assert sha(p) == case['files'][branch]['sha256']
                v = torch.load(p, map_location='cpu', weights_only=True)
                assert set(v) == {'video', 'audio', 'metadata'}
                assert v['metadata']['physical_index'] == 4 and v['metadata']['branch'] == branch
                assert v['metadata']['seed'] == 2026101311
                assert tuple(v['video'].shape) == (1, 24, 42, 46, 82)
                for key in ['video', 'audio']:
                    assert v[key].dtype == torch.float32 and torch.isfinite(v[key]).all()
                pair[branch] = v
            for key in ['physical_index','sigma','sigma_next','seed','condition_sha256','reference_sha256']:
                assert pair['native']['metadata'][key] == pair['full']['metadata'][key]
            pairs.append(pair)
        for key in ['video', 'audio']:
            assert torch.equal(pairs[0]['native'][key], pairs[1]['native'][key])
        conditions = json.loads((HERE/'CONDITIONS.json').read_text())
        assert canonical_condition(conditions['parent']) == canonical_condition(conditions['current'])
        for pair, name in zip(pairs, ['parent', 'current']):
            assert pair['native']['metadata']['condition_sha256'] == conditions[name]['sha256']
        for key in ['physical_index','sigma','sigma_next','seed','reference_sha256']:
            assert pairs[0]['native']['metadata'][key] == pairs[1]['native']['metadata'][key]
        deltas = [{k:p['full'][k].double()-p['native'][k].double() for k in ['video','audio']} for p in pairs]
        video = geometry(deltas[0]['video'], deltas[1]['video'])
        audio = geometry(deltas[0]['audio'], deltas[1]['audio'])
        bins = [{'bin':t, **geometry(deltas[0]['video'][:,:,t], deltas[1]['video'][:,:,t])} for t in range(42)]
        result = {
            'status':'complete','observed_unix':time.time(), 'elapsed_seconds':time.monotonic()-started,
            'freeze_sha256':sha(HERE/'FREEZE.json'), 'protocol_sha256':sha(HERE/'PROTOCOL.json'),
            'names':[c['name'] for c in protocol['cases']], 'video':video, 'normalized_audio':audio,
            'all42_video_bins':bins, 'same_native_AV_exact':True, 'new_GPU_forwards':0,
            'processed_condition_match':'exact after two corresponding run UUID leaves canonicalized; each original tree SHA checked',
            'scope':'Archived same-input output directions only. Noncollinearity does not establish timing controllability, quality, or a method advantage. Audio and video remain separate coordinate spaces.',
        }
        assert not torch.cuda.is_initialized()
        (HERE/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:result[k] for k in ['status','elapsed_seconds','video','normalized_audio']}))


if __name__ == '__main__':
    main()
