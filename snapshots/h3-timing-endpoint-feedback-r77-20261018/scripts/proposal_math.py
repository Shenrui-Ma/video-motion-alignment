"""CPU bridge to pinned R70 correspondence and known codec-residual operators."""
import sys
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))
import phase_fitter
import operators
import evaluate
from endpoint import Proposal, require, signature


def fit_current(source_pose, current_pose):
    """Consume the full current prediction's pose; no final-video input exists."""
    require(source_pose['provenance'] == current_pose['provenance'], 'pose detector provenance differs')
    source = evaluate.original_time_view(source_pose, .3)
    current = evaluate.original_time_view(current_pose, .3)
    s, sc = phase_fitter.add_features(source)['upper_arm_direction_fit']
    t, tc = phase_fitter.add_features(current)['upper_arm_direction_fit']
    cost, supported = np.full((49, 49), 2.0), np.zeros((49, 49), dtype=bool)
    for i in range(49):
        for j in range(49):
            valid = np.isfinite(s[i]).all(-1) & np.isfinite(t[j]).all(-1)
            if valid.all():
                weight = np.minimum(sc[i], tc[j]).clip(0, 1)
                require(weight.sum() > 0, 'visible pose has no confidence weight')
                cost[i, j] = float((np.linalg.norm(s[i]-t[j], axis=-1)*weight).sum()/weight.sum())
                supported[i, j] = True
    mapping, optimum = phase_fitter.monotone(cost)
    records, support_both, interpolation_neighbors_supported = {}, np.ones(49, dtype=bool), True
    for threshold in (.3, .5):
        sv = phase_fitter.add_features(evaluate.original_time_view(source_pose, threshold))
        tv = phase_fitter.add_features(evaluate.original_time_view(current_pose, threshold))
        records[str(threshold)] = [phase_fitter.compare(sv, tv, mapping, [0, 15], feature)
                                  for feature in ('arm_direction','left_arm_direction','right_arm_direction',
                                                  'forearm_direction_not_fit','wrist_relative_not_fit')]
        sf, _ = sv['upper_arm_direction_fit']
        tf, _ = tv['upper_arm_direction_fit']
        support_both &= (np.isfinite(sf).all((1,2)) & np.isfinite(tf[mapping]).all((1,2)))
        interpolation_neighbors_supported &= bool(np.isfinite(sf[:16]).all() and np.isfinite(tf[:16]).all())
    eligible = bool(mapping[0] == 0 and mapping[15] == 15 and support_both[:16].all() and
                    interpolation_neighbors_supported and
                    all(row['status'] == 'measured' for rows in records.values() for row in rows
                        if row['feature'] in ('arm_direction','left_arm_direction','right_arm_direction')))
    return {'mapping': mapping.tolist(), 'eligible': eligible,
            'selected_fit_support': supported[np.arange(49), mapping].tolist(),
            'dual_threshold_upper_arm_support': support_both.tolist(),
            'interpolation_neighbors_supported': interpolation_neighbors_supported,
            'cost_sum': optimum[0], 'confidence_results': records,
            'basis': 'current_x0', 'direction': 'source time -> current prediction read time'}


def local_coordinates(mapping):
    mapping = np.asarray(mapping, dtype=np.float64)
    require(mapping.shape == (49,) and np.isfinite(mapping).all(), '49 finite phase coordinates required')
    require(mapping[0] == 0 and mapping[15] == 15 and mapping[48] == 48 and
            np.all(np.diff(mapping) >= 0) and np.all((mapping >= 0) & (mapping <= 48)), 'phase endpoints/order invalid')
    rgb = np.arange(158, dtype=np.float64)
    rgb[:46] = np.interp(np.arange(46), np.arange(16)*3, mapping[:16]*3)
    coords = operators.coordinates(rgb)
    start, end, _ = operators.bins()
    q = np.asarray(coords['latent_positions'])
    lo, hi = np.floor(q).astype(int), np.ceil(q).astype(int)
    valid = ((start >= 0) & (end <= 45) & (start[lo] >= 0) & (end[lo] <= 45) &
             (start[hi] >= 0) & (end[hi] <= 45) & np.asarray(coords['latent_center_domain_valid']))
    mask = valid.astype(np.float32)
    indices = np.flatnonzero(valid)
    require(len(indices) >= 2 and np.all(np.diff(indices) == 1), 'insufficient contiguous supported latent bins')
    mask[indices[-2:]] = [.75, .25]
    return coords, torch.from_numpy(mask)


def codec_proposal(z, e_identity, e_phi, coordinates, mask, evidence):
    """Known LookingGlass residual, same floating-point order as R70 transport."""
    for tensor in (z, e_identity, e_phi):
        require(tensor.device.type == 'cpu' and tensor.dtype == torch.float32 and
                tensor.shape == z.shape and bool(torch.isfinite(tensor).all()), 'codec latent contract differs')
    q = np.asarray(coordinates['latent_positions'], dtype=np.float64)
    require(z.shape[2] == 47 and q.shape == (47,) and np.isfinite(q).all() and
            np.all((q >= 0) & (q <= 46)), 'latent coordinates outside supported domain')
    require(mask.shape == (47,) and mask.device.type == 'cpu' and bool(torch.isfinite(mask).all()) and
            bool(((mask >= 0) & (mask <= 1)).all()), 'invalid mask')
    if np.array_equal(q, np.arange(47)) and torch.equal(e_identity, e_phi):
        delta = torch.zeros_like(z)  # exact no-op branch in the endpoint hook
    else:
        proposal = operators.interpolate(z, q, 2) + (e_phi - operators.interpolate(e_identity, q, 2))
        delta = (proposal - z) * mask.view(1, 1, 47, 1, 1)
    return Proposal(delta=delta, mask=mask, current_video_sha256=signature(z)['sha256'], evidence=evidence)
