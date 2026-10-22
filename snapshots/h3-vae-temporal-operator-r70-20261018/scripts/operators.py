"""Explicit RGB-time and nonuniform H3 output-bin interpolation coordinates."""
import numpy as np
import torch


def bins():
    spans = np.array(([1, 4, 4, 4, 4] * 10)[:47])
    start = np.r_[0, np.cumsum(spans)[:-1]]
    end = start + spans - 1
    # Nominal output-bin centers; not attention RoPE anchors or receptive-field centers.
    center = (start + end) / 2
    return start, end, center


def make_maps(original49):
    original49 = np.asarray(original49, dtype=np.float64)
    assert original49.shape == (49,) and original49[0] == 0 and original49[-1] == 48
    assert np.all(np.diff(original49) >= 0)
    rgb = np.arange(158, dtype=np.float64)
    dtw = np.interp(rgb, np.arange(49) * 3, original49 * 3)
    dtw[144:] = rgb[144:]
    return {'identity': rgb, 'shift3': rgb + 3, 'offline_mapping': dtw}


def interpolate(value, positions, axis):
    assert value.dtype == torch.float32 and value.device.type == 'cpu'
    x = value.movedim(axis, 0)
    positions = np.asarray(positions, dtype=np.float64)
    assert len(positions) == len(x) and np.isfinite(positions).all()
    q = np.clip(positions, 0, len(x) - 1)
    lower = np.floor(q).astype(int)
    upper = np.ceil(q).astype(int)
    out = torch.empty_like(x)
    for i, (a, b, f) in enumerate(zip(lower, upper, q - lower)):
        if a == b:
            out[i].copy_(x[a])
        else:
            out[i].copy_(x[a] * (1.0 - float(f)) + x[b] * float(f))
    return out.movedim(0, axis).contiguous()


def coordinates(phi):
    start, end, center = bins()
    phi = np.asarray(phi, dtype=np.float64)
    target_at_center = np.interp(center, np.arange(158), phi)
    index = np.interp(target_at_center, center, np.arange(47))
    latent_valid = (target_at_center >= center[0]) & (target_at_center <= center[-1])
    owner = np.repeat(np.arange(47), end - start + 1)
    lower = np.floor(index).astype(int)
    upper = np.ceil(index).astype(int)
    f = np.arange(158)
    return {'rgb_positions': phi.tolist(), 'latent_positions': index.tolist(),
            'nominal_bin_centers_rgb_frames': center.tolist(),
            'latent_query_rgb_frames': target_at_center.tolist(),
            'rgb_full_domain_valid': ((phi >= 0) & (phi <= 157)).tolist(),
            'observed147_valid': ((f < 147) & (phi >= 0) & (phi < 147)).tolist(),
            'latent_center_domain_valid': latent_valid.tolist(),
            'output_bin_latent_domain_valid': latent_valid[owner].tolist(),
            'cross17_rgb': ((f // 17) != (np.floor(np.clip(phi, 0, 157)).astype(int) // 17)).tolist(),
            'cross17_latent_interpolation': ((lower // 5) != (upper // 5)).tolist(),
            'cross17_latent_source_block': ((np.arange(47) // 5) != (np.floor(np.clip(target_at_center, 0, 157)).astype(int) // 17)).tolist(),
            'decoder_overlap_first5': ((f >= 17) & (f < 153) & (f % 17 < 5)).tolist(),
            'decoder_tail5': (f >= 153).tolist(), 'output_bin_index': owner.tolist()}


def frame_mae(actual, target):
    assert actual.shape == target.shape == (158, 768, 1152, 3)
    return [float((a - b).abs().mean()) for a, b in zip(actual, target)]


def frame_mae_to_rgb_warp(actual, base, positions):
    errors = []
    for frame, q in zip(actual, np.clip(positions, 0, 157)):
        lo, hi = int(np.floor(q)), int(np.ceil(q))
        target = base[lo] if lo == hi else base[lo] * (1 - float(q - lo)) + base[hi] * float(q - lo)
        errors.append(float((frame - target).abs().mean()))
    return errors


def reductions(errors, mapping):
    errors = np.asarray(errors)
    valid = np.array(mapping['rgb_full_domain_valid']) & np.array(mapping['observed147_valid']) & np.array(mapping['output_bin_latent_domain_valid'])
    groups = {'full158': np.ones(158, dtype=bool), 'common_valid147': valid,
              'cross17_common_valid147': valid & np.array(mapping['cross17_rgb']),
              'within17_common_valid147': valid & ~np.array(mapping['cross17_rgb']),
              'overlap_common_valid147': valid & np.array(mapping['decoder_overlap_first5']),
              'invalid_or_padding': ~valid}
    return {name: {'frames': int(mask.sum()), 'mean_absolute_rgb_error': float(errors[mask].mean()) if mask.any() else None}
            for name, mask in groups.items()}
