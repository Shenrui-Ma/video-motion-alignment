"""File/source checks precede trusted tensor decoding; never reconstruct x_n."""
import hashlib
import json
import math
from pathlib import Path
import torch


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def tensor_info(t):
    t = t.detach().to('cpu').contiguous()
    return dict(shape=list(t.shape), dtype=str(t.dtype), finite=bool(torch.isfinite(t).all()),
                sha256=hashlib.sha256(t.view(torch.uint8).numpy().tobytes()).hexdigest())


def exact_tensor(a, b, name):
    if (not isinstance(a, torch.Tensor) or not isinstance(b, torch.Tensor)
            or a.shape != b.shape or a.dtype != b.dtype
            or not bool(torch.isfinite(a).all()) or not bool(torch.isfinite(b).all())
            or not torch.equal(a.cpu(), b.cpu())):
        raise ValueError('exact tensor gate failed: ' + name)


def unpack(x, shapes):
    return [a.reshape(s) for a, s in zip(x.split([math.prod(s) for s in shapes], -1), shapes)]


def check_files(entries):
    """Check every file before callers decode any tensor or create outputs."""
    for e in entries:
        if not Path(e['path']).is_absolute() or file_sha(e['path']) != e['sha256']:
            raise ValueError('file identity mismatch: ' + e['path'])


def check_sources(root, identities):
    check_files([dict(path=str(Path(root) / p), sha256=h) for p, h in identities.items()])


def check_checkpoint_stat(expected):
    s = Path(expected['path']).stat()
    if (s.st_ino, s.st_size, s.st_mtime_ns) != (expected['inode'], expected['bytes'], expected['mtime_ns']):
        raise ValueError('checkpoint differs from existing full-SHA receipt')


def load_live_inputs(entries, contract):
    if set(entries) != {'9', '19'}:
        raise ValueError('exactly native live steps 9 and 19 required')
    check_files([v[k] for v in entries.values() for k in ('state', 'qk')])
    result = {}
    for key, e in entries.items():
        s = torch.load(e['state']['path'], map_location='cpu', weights_only=True)
        q = torch.load(e['qk']['path'], map_location='cpu', weights_only=True)
        step = int(key)
        if (s.get('schema') != 'h3-live-phase-state-v1' or s['step_zero_based'] != step
                or q.get('schema') != 'h3-passive-qk-capture-v1' or q['step_zero_based'] != step
                or q['layer_zero_based'] != 25 or s['target_shapes'] != contract['target_shapes']
                or s['sample_sigmas_video'] != contract['sigmas_video']):
            raise ValueError('live state/capture domain mismatch')
        for name in ('packed_x', 'raw_packed_x0'):
            t = s[name]
            if t.dtype != torch.float32 or list(t.shape) != [1, 1, 2908288] or not bool(torch.isfinite(t).all()):
                raise ValueError('invalid captured complete AV ' + name)
        for stage in ('raw', 'actual'):
            for branch in ('Q_C', 'Q_R', 'K_R'):
                t = q[stage + '_' + branch]
                if tuple(t.shape) != (32, 8, 56, 128) or not t.is_floating_point() or not bool(torch.isfinite(t).all()):
                    raise ValueError('invalid actual complete captured QK')
        if (q['heads'] != 56 or q['head_dim'] != 128
                or q['spatial_ids'] != [0,135,269,404,538,673,807,942]
                or q['valid_bins'] != [True]*31+[False]):
            raise ValueError('capture probe geometry differs')
        if q['forward_identity']['state_file_sha256'] != e['state']['sha256']:
            raise ValueError('capture does not belong to saved live state')
        forward = q['forward_identity']
        for name in ('case', 'method', 'trajectory_id'):
            if forward[name] != contract[name] or q[name] != contract[name]:
                raise ValueError('capture trajectory mismatch: ' + name)
        if (forward['step_zero_based'] != step or forward['layer_zero_based'] != 25
                or forward['science_contract_sha256'] != file_sha(Path(__file__).parent / 'native_contract.json')
                or forward['sample_sigmas_video'] != contract['sigmas_video']
                or q['sample_sigmas_video'] != contract['sigmas_video']
                or forward['noise_sha256'] != contract['noise_tensor_sha256']):
            raise ValueError('capture forward identity mismatch')
        for name in ('packed_x', 'raw_packed_x0'):
            if tensor_info(s[name]) != forward[name]:
                raise ValueError('capture state tensor mismatch: ' + name)
        result[step] = (s, q)
    return result


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
