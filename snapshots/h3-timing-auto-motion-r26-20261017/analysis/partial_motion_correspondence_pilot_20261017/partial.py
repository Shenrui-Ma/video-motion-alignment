"""CPU diagnostic using the published four-state double-Drop-DTW recurrence.

Source indices are rows and generated indices are columns. Positive lag means
the generated event is later. This module makes no timing reliability decision.
"""
from dataclasses import dataclass
import numpy as np


@dataclass
class Alignment:
    objective: float
    pairs: np.ndarray
    source_unmatched: np.ndarray
    target_unmatched: np.ndarray


def double_drop(cost, source_drop=0.25, target_drop=0.25):
    """Four states, in author order: matched, drop target, drop source, drop both.

    Match transitions: diagonal from any state, top from0/2, left from0/1.
    Single drops preserve the other currently matched endpoint. State3 extends
    a dropped endpoint. Ties follow the author's neighbor order deterministically.
    """
    cost = np.asarray(cost, dtype=float)
    if cost.ndim != 2 or np.isnan(cost).any() or (cost < 0).any():
        raise ValueError('cost must be a nonnegative matrix; infinity is allowed')
    n, m = cost.shape
    ds = np.broadcast_to(np.asarray(source_drop, dtype=float), (n,))
    dt = np.broadcast_to(np.asarray(target_drop, dtype=float), (m,))
    if not np.isfinite(ds).all() or not np.isfinite(dt).all() or (ds < 0).any() or (dt < 0).any():
        raise ValueError('drop costs must be finite and nonnegative')
    table = np.full((n + 1, m + 1, 4), np.inf)
    previous = np.zeros((n + 1, m + 1, 4, 3), dtype=np.int32)
    table[0, 0, 0] = 0
    for i in range(1, n + 1):
        for state in (2, 3):
            table[i, 0, state] = ds[:i].sum()
            previous[i, 0, state] = (i - 1, 0, state)
    for j in range(1, m + 1):
        for state in (1, 3):
            table[0, j, state] = dt[:j].sum()
            previous[0, j, state] = (0, j - 1, state)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diagonal = [(i - 1, j - 1, s) for s in range(4)]
            top = [(i - 1, j, s) for s in (0, 2)]
            left = [(i, j - 1, s) for s in (0, 1)]
            choices = (
                [(p, cost[i - 1, j - 1]) for p in diagonal + top + left],
                [(p, dt[j - 1]) for p in left],
                [(p, ds[i - 1]) for p in top],
                [((i, j - 1, s), dt[j - 1]) for s in (2, 3)]
                + [((i - 1, j, s), ds[i - 1]) for s in (1, 3)],
            )
            for state, candidates in enumerate(choices):
                values = [table[p] + added for p, added in candidates]
                best = int(np.argmin(values))
                table[i, j, state] = values[best]
                previous[i, j, state] = candidates[best][0]

    state = int(np.argmin(table[n, m]))
    objective = float(table[n, m, state])
    i, j = n, m
    pairs = []
    while i or j:
        if state == 0:
            pairs.append((i - 1, j - 1))
        i, j, state = map(int, previous[i, j, state])
    pairs = np.asarray(pairs[::-1], dtype=int).reshape(-1, 2)
    source_used = np.unique(pairs[:, 0])
    target_used = np.unique(pairs[:, 1])
    result = Alignment(objective, pairs, np.setdiff1d(np.arange(n), source_used),
                       np.setdiff1d(np.arange(m), target_used))
    reconstructed = cost[tuple(pairs.T)].sum() + ds[result.source_unmatched].sum() + dt[result.target_unmatched].sum()
    if not np.isclose(reconstructed, objective, atol=1e-9):
        raise AssertionError('traceback objective does not match the DP')
    return result


def pair_cost(source, target, source_conf, target_conf, minimum_fraction=0.8):
    """Mean bone distance; a missing bone never becomes a free zero-cost match."""
    source, target = np.asarray(source), np.asarray(target)
    valid = np.isfinite(source[:, None]).all(-1) & np.isfinite(target[None, :]).all(-1)
    weights = np.minimum(source_conf[:, None], target_conf[None, :]).clip(0, 1)
    weights = np.where(valid, weights, 0)
    distances = np.linalg.norm(np.nan_to_num(source[:, None] - target[None, :]), axis=-1)
    sums = weights.sum(-1)
    numerator = (distances * weights).sum(-1)
    cost = np.divide(numerator, sums, out=np.full(sums.shape, np.inf), where=sums > 0)
    fraction = valid.mean(-1)
    cost[fraction < minimum_fraction] = np.inf
    return cost, fraction


def summarize(alignment, cost, source, target, fps=24):
    pairs = alignment.pairs
    n, m = cost.shape
    source_valid = np.isfinite(source).all(-1).mean(-1) >= 0.8
    target_valid = np.isfinite(target).all(-1).mean(-1) >= 0.8
    source_lag = np.full(n, np.nan)
    source_residual = np.full(n, np.nan)
    for i in np.unique(pairs[:, 0]):
        js = pairs[pairs[:, 0] == i, 1]
        source_lag[i] = np.median(js) - i
        source_residual[i] = cost[i, js].mean()
    matched = np.isfinite(source_lag)
    lags = source_lag[matched]
    diag = np.diag(cost)
    finite_diag = diag[np.isfinite(diag)]
    return {
        'objective': alignment.objective,
        'matched_pairs': len(pairs),
        'source_matched_frames': int(matched.sum()),
        'target_matched_frames': int(len(np.unique(pairs[:, 1]))),
        'source_unmatched_fraction': len(alignment.source_unmatched) / max(n, 1),
        'target_unmatched_fraction': len(alignment.target_unmatched) / max(m, 1),
        'source_unobservable_fraction': float((~source_valid).mean()),
        'target_unobservable_fraction': float((~target_valid).mean()),
        'source_observable_but_unmatched_frames': int(source_valid[alignment.source_unmatched].sum()),
        'target_observable_but_unmatched_frames': int(target_valid[alignment.target_unmatched].sum()),
        'matched_geometry_residual_pair_mean': float(cost[tuple(pairs.T)].mean()) if len(pairs) else None,
        'matched_geometry_residual_source_mean': float(source_residual[matched].mean()) if matched.any() else None,
        'same_frame_geometry_residual': float(finite_diag.mean()) if len(finite_diag) else None,
        'same_frame_valid_fraction': len(finite_diag) / max(n, m, 1),
        'lag_median_frames': float(np.median(lags)) if len(lags) else None,
        'lag_q25_q75_frames': np.quantile(lags, [0.25, 0.75]).tolist() if len(lags) else None,
        'lag_min_max_frames': [float(lags.min()), float(lags.max())] if len(lags) else None,
        'lag_median_seconds': float(np.median(lags) / fps) if len(lags) else None,
        'fraction_matched_source_abs_lag_gt24': float((abs(lags) > 24).mean()) if len(lags) else None,
        'max_targets_per_source': int(np.bincount(pairs[:, 0], minlength=n).max()) if len(pairs) else 0,
        'max_sources_per_target': int(np.bincount(pairs[:, 1], minlength=m).max()) if len(pairs) else 0,
        'source_lag_frames': source_lag.tolist(),
        'source_geometry_residual': source_residual.tolist(),
        'source_unmatched_indices': alignment.source_unmatched.tolist(),
        'target_unmatched_indices': alignment.target_unmatched.tolist(),
        'interpretation': 'descriptive alignment only; no calibrated timing or identity verdict',
    }
