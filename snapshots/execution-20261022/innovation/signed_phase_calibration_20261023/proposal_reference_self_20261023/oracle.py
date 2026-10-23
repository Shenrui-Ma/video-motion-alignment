"""Synthetic, NumPy-only identifiability oracles. Not a production phase reader.

No actual captures, method labels, GPU libraries or temporal-control code.
All tolerances supplied to matching are explicit diagnostic assumptions.
"""
from __future__ import annotations

import numpy as np


def probabilities(value, *, ndim=2):
    x = np.asarray(value, dtype=np.float64)
    if x.ndim != ndim or x.shape[-1] < 2 or not np.isfinite(x).all():
        raise ValueError("finite probability array with at least two keys required")
    if np.any(x < 0) or not np.allclose(x.sum(-1), 1, rtol=0, atol=1e-12):
        raise ValueError("nonnegative, normalized probabilities required")
    return x


def time_code(reference, times, *, ridge_relative=0.0):
    """Centered linear readout, with an intercept and explicit inverse gain.

    ridge_relative is a dimensionless ratio to the largest eigenvalue of C' C.
    ridge=0 uses the numerical Moore--Penrose inverse. The synthetic tests never
    claim that a training fit or a finite inverse gain is semantic validation.
    """
    c = probabilities(reference)
    tau = np.asarray(times, dtype=np.float64)
    if tau.shape != (len(c),) or not np.isfinite(tau).all():
        raise ValueError("one finite time per reference row required")
    if not np.isfinite(ridge_relative) or ridge_relative < 0:
        raise ValueError("nonnegative finite ridge_relative required")
    mean_c, mean_t = c.mean(0), float(tau.mean())
    x, y = c - mean_c, tau - mean_t
    u, s, vh = np.linalg.svd(x, full_matrices=False)
    cutoff = np.finfo(np.float64).eps * max(x.shape) * (s[0] if len(s) else 0)
    retained = s > cutoff
    regularizer = ridge_relative * (float(s[0]) ** 2 if len(s) else 0)
    filt = np.zeros_like(s)
    if regularizer > 0:
        filt = s / (s * s + regularizer)
    else:
        filt[retained] = 1.0 / s[retained]
    w = vh.T @ (filt * (u.T @ y))
    offset = mean_t - float(mean_c @ w)
    fitted = c @ w + offset
    projection = u[:, retained] @ (u[:, retained].T @ y)
    return {
        "weights": w,
        "offset": offset,
        "fitted": fitted,
        "singular_values": s,
        "numerical_rank": int(retained.sum()),
        "unregularized_unidentifiable_residual": float(np.linalg.norm(y - projection)),
        "training_rmse": float(np.sqrt(np.mean((fitted - tau) ** 2))),
        "inverse_l2_gain": float(np.linalg.norm(w)),
        "ridge_relative": float(ridge_relative),
        "ridge_absolute": regularizer,
    }


def read_time(code, generated):
    p = probabilities(generated)
    if p.shape[1] != len(code["weights"]):
        raise ValueError("reference key support mismatch")
    return p @ code["weights"] + code["offset"]


def trajectory_matches(reference, observations, times, *, assumed_radius,
                       requested_time_resolution):
    """Reference-fingerprint matching in sqrt-probability Euclidean distance.

    Reports ALL templates within an assumed radius. Never averages disjoint
    temporal matches. The radius is only a supplied synthetic/diagnostic bound;
    calibration on reference probes cannot certify generated-query domain shift.
    """
    c, p = probabilities(reference), probabilities(observations)
    tau = np.asarray(times, dtype=np.float64)
    if c.shape[1] != p.shape[1] or tau.shape != (len(c),):
        raise ValueError("support/time mismatch")
    if not np.isfinite(tau).all() or np.any(np.diff(tau) <= 0):
        raise ValueError("strictly increasing finite reference times required")
    if not np.isfinite(assumed_radius) or assumed_radius < 0:
        raise ValueError("explicit nonnegative radius required")
    if not np.isfinite(requested_time_resolution) or requested_time_resolution < 0:
        raise ValueError("explicit nonnegative time resolution required")
    distances = np.linalg.norm(np.sqrt(p)[:, None, :] - np.sqrt(c)[None, :, :], axis=-1)
    result = []
    for row in distances:
        indices = np.flatnonzero(row <= assumed_radius + 1e-14)
        matched = tau[indices]
        width = float(np.ptp(matched)) if len(matched) else None
        if not len(indices):
            status = "out_of_reference_support"
        elif width > requested_time_resolution:
            status = "temporally_ambiguous"
        else:
            status = "unique_at_requested_resolution"
        result.append({"status": status, "candidate_indices": indices.tolist(),
                       "candidate_times": matched.tolist(), "diameter": width,
                       "nearest_distance": float(row.min())})
    return result


def separation(reference, times, *, minimum_time_separation):
    """Minimum fingerprint distance between temporally separated templates.

    If each observed fingerprint error is <= eps, separation > 2 eps is a
    sufficient discrete-template identifiability certificate at this resolution.
    """
    c = probabilities(reference)
    tau = np.asarray(times, dtype=np.float64)
    if tau.shape != (len(c),) or not np.isfinite(tau).all():
        raise ValueError("time mismatch")
    if not np.isfinite(minimum_time_separation) or minimum_time_separation <= 0:
        raise ValueError("strictly positive resolution required")
    d = np.linalg.norm(np.sqrt(c)[:, None, :] - np.sqrt(c)[None, :, :], axis=-1)
    keep = np.abs(tau[:, None] - tau[None, :]) >= minimum_time_separation
    if not keep.any():
        return None
    return float(d[keep].min())


def leave_probe_split(reference_by_probe, times, *, train_probes, test_probes,
                      ridge_relative=0.0):
    """Reference-only spatial holdout, arrays [time,probe,key_time].

    Fit no generated outputs; preserve individual held-out probe residuals.
    Probe independence and transfer to generated queries are NOT assumed.
    """
    c = probabilities(reference_by_probe, ndim=3)
    train, test = list(train_probes), list(test_probes)
    if not train or not test or set(train) & set(test):
        raise ValueError("nonempty disjoint probe folds required")
    if len(set(train)) != len(train) or len(set(test)) != len(test):
        raise ValueError("duplicate probe indices")
    if any(i < 0 or i >= c.shape[1] for i in train + test):
        raise ValueError("probe index outside support")
    code = time_code(c[:, train].mean(1), times, ridge_relative=ridge_relative)
    estimates = read_time(code, c[:, test].reshape(-1, c.shape[-1])).reshape(len(c), len(test))
    error = estimates - np.asarray(times)[:, None]
    return {"code": code, "predictions": estimates, "errors": error,
            "heldout_rmse": float(np.sqrt(np.mean(error ** 2))),
            "heldout_max_error": float(np.max(np.abs(error)))}
