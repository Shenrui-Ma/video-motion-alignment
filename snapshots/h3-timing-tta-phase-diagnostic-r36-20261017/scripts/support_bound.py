"""Necessary support only: no feature distances, phase scores or argmin."""
import numpy as np
from math_core import LAGS


def identity_bound(source, target, source_conf, target_conf, window, threshold):
    s, t = np.asarray(source), np.asarray(target)
    sc, tc = np.asarray(source_conf), np.asarray(target_conf)
    if s.shape != t.shape or s.ndim != 3 or s.shape[0] != 141 or s.shape[-1] != 2:
        raise ValueError('Expected141 xlimbs x2 identity features')
    if sc.shape != s.shape[:-1] or tc.shape != t.shape[:-1] or not np.isfinite(sc).all() or not np.isfinite(tc).all():
        raise ValueError('Invalid confidence shape/finite gate')
    a, b = window
    if not (type(a) is int and type(b) is int and 0 <= a <= b < 141):
        raise ValueError('Invalid inclusive window')
    frames = np.arange(a, b+1)
    valid = np.isfinite(s[frames]).all(axis=-1) & (sc[frames] >= threshold)
    weights = sc[frames].copy()
    for lag in LAGS:
        idx = frames+lag
        inside = (idx >= 0) & (idx < 141)
        safe = np.clip(idx, 0, 140)
        valid &= inside[:, None] & np.isfinite(t[safe]).all(axis=-1) & (tc[safe] >= threshold)
        weights = np.minimum(weights, tc[safe])
    positive = valid & (weights.clip(0, 1) > 0)
    coverage = float(valid.mean())
    valid_frames = int(positive.any(axis=-1).sum())
    possible = coverage >= .8 and valid_frames >= 8 and bool(positive.any())
    return {'status':'POSSIBLE_support_only' if possible else 'IMPOSSIBLE_strict_common_support',
            'possibly_eligible':possible, 'coverage_upper_bound':coverage,
            'positive_weight_frames_upper_bound':valid_frames,
            'valid_vectors_upper_bound':int(valid.sum()), 'mask':valid.tolist(),
            'window':list(window), 'threshold':threshold,
            'phase_or_cost_computed':False}
