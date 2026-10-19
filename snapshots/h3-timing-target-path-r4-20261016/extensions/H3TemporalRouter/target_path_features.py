"""Passive same-forward native target and full-correction candidate capture.

The candidate is an actuator's hypothetical output, not an action ground truth.
No candidate is returned to the model. No new DiT evaluation is performed.
"""
import json
import math
from pathlib import Path
import re

from .native_features import _exclusive_tensor_save, _file_sha, _signature

HEADS = (0, 14, 28, 42)
STEPS = (6, 10, 14)


def candidate_readout(full, full_lse, q, k, v, plan, *, selected_heads=HEADS,
                      attention, aligned_attention):
    import torch

    if q.shape != k.shape or q.shape != v.shape or full.shape != q.shape:
        raise ValueError('equal [B,H,N,D] QKV and native output required')
    if q.ndim != 4 or q.shape[0] != 1 or full_lse.shape != q.shape[:-1]:
        raise ValueError('unexpected native attention layout')
    if not selected_heads or len(set(selected_heads)) != len(selected_heads):
        raise ValueError('unique selected heads required')
    if any(type(h) is not int or not 0 <= h < q.shape[1] for h in selected_heads):
        raise ValueError('invalid head index')
    qa, qb = plan['query_interval_half_open']
    ra, rb = plan['reference_video_segment']
    ta, tb = plan['target_video_segment']
    if not (0 <= qa < qb <= q.shape[2] and 0 <= ra < rb <= q.shape[2]
            and ta <= qa < qb <= tb <= q.shape[2]):
        raise ValueError('invalid packed token spans')
    h = torch.tensor(selected_heads, dtype=torch.long, device=q.device)
    query = q[:, :, qa:qb].index_select(1, h)
    keys = k[:, :, ra:rb].index_select(1, h)
    values = v[:, :, ra:rb].index_select(1, h)
    ref, ref_lse = attention(query, keys, values)
    mass = (ref_lse.float() - full_lse[:, :, qa:qb].index_select(1, h).float()).clamp(max=0).exp()
    aligned, _ = aligned_attention(query, keys, values,
                                   latent_lo=plan['latent_interval_half_open'][0],
                                   frame_rows=plan['frame_rows'], radius=0, time_offset=0,
                                   attention=attention)
    original = full[:, :, qa:qb].index_select(1, h)
    candidate = (original.float() + mass.unsqueeze(-1) * (aligned.float() - ref.float())).to(full.dtype)
    target = full[:, :, ta:tb].index_select(1, h)
    return target, candidate, mass


def save_target_path_features(full, full_lse, q, k, v, plan, *, output_dir,
                              run_id, step, block, sigma_video, attention,
                              aligned_attention, selected_heads=HEADS,
                              expected_grid=(42, 23, 41)):
    import torch

    if block != 25 or step not in STEPS:
        raise ValueError('only block25 calls6/10/14 are registered')
    if full.dtype != torch.bfloat16 or any(x.dtype != full.dtype for x in (q, k, v)):
        raise ValueError('native BF16 capture required')
    if not isinstance(run_id, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', run_id) is None:
        raise ValueError('invalid run identifier')
    if not math.isfinite(float(sigma_video)) or not 0 <= float(sigma_video) <= 1:
        raise ValueError('invalid sigma')
    signature = plan['signature']
    grid = (signature[1], signature[2] // 2, signature[3] // 2)
    lo, hi = plan['latent_interval_half_open']
    if (signature[2] % 2 or signature[3] % 2 or grid != tuple(expected_grid)
            or plan['frame_rows'] != grid[1] * grid[2]
            or plan['seq_len'] != full.shape[2]):
        raise ValueError('actual token geometry mismatch')
    if plan['target_video_segment'][1] - plan['target_video_segment'][0] != math.prod(grid):
        raise ValueError('incomplete target grid')
    if plan['query_interval_half_open'] != [plan['target_video_segment'][0] + lo * plan['frame_rows'],
                                           plan['target_video_segment'][0] + hi * plan['frame_rows']]:
        raise ValueError('candidate query frame mapping mismatch')
    root = Path(output_dir)
    if not root.is_absolute():
        raise ValueError('absolute capture root required')
    root.mkdir(parents=True, exist_ok=True)
    destination = root / run_id
    if destination.is_symlink():
        raise ValueError('capture directory cannot be a symlink')
    destination.mkdir(exist_ok=True)
    path = destination / f'block{block}_step{step:03d}.pt'
    if path.exists():
        raise FileExistsError(path)
    target, candidate, mass = candidate_readout(
        full, full_lse, q, k, v, plan, selected_heads=selected_heads,
        attention=attention, aligned_attention=aligned_attention)
    captured = {
        'target': target.reshape(1, len(selected_heads), *grid, full.shape[-1]).detach().cpu().contiguous(),
        'candidate': candidate.reshape(1, len(selected_heads), hi-lo, grid[1], grid[2], full.shape[-1]).detach().cpu().contiguous(),
        'reference_mass': mass.reshape(1, len(selected_heads), hi-lo, grid[1], grid[2]).detach().cpu().contiguous(),
    }
    if not all(bool(torch.isfinite(x).all()) for x in captured.values()):
        raise ValueError('nonfinite captured features')
    metadata = {
        'schema': 'h3-target-path-candidate-v1', 'run_id': run_id,
        'forward_index': step, 'block_index': block, 'sampler_sigma_video': float(sigma_video),
        'stage': 'same native forward, attention output before W_O',
        'candidate_formula': 'native O + m_ref * (same-bin attention V - all-reference attention V)',
        'candidate_scope': 'hypothetical full actuator output at this one block on the native trajectory; not correct-action ground truth',
        'computation': 'same Flash implementation and FP32 correction accumulation then native BF16 cast as formal full arm',
        'head_indices': list(selected_heads), 'grid': list(grid),
        'candidate_latent_interval_half_open': [lo, hi],
        'tensor_axis_order': ['batch', 'head', 'time', 'y', 'x', 'channel'],
        'layout': json.loads(json.dumps(plan)),
        'tensors': {name: _signature(value) for name, value in captured.items()},
    }
    _exclusive_tensor_save(path, {**captured, 'metadata': metadata})
    return {'path': str(path), 'sha256': _file_sha(path), 'bytes': path.stat().st_size, 'metadata': metadata}
