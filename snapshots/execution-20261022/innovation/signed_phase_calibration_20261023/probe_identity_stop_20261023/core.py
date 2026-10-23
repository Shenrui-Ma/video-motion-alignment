"""Reference fingerprint stability only; no learned readout or alpha output."""
from __future__ import annotations

import numpy as np

TIE_TOLERANCE = 64 * np.finfo(np.float64).eps


def fingerprint(probability, valid):
    """Preserve the ordered H x P coordinates; remove invalid query/key bins."""
    p = np.asarray(probability)
    valid = np.asarray(valid)
    if p.ndim != 4 or p.dtype != np.float64 or valid.dtype != np.bool_:
        raise ValueError("expected float64 H,T,P,T probabilities and boolean support")
    h, t, probes, keys = p.shape
    if h < 1 or probes < 1 or keys != t or valid.shape != (t,) or valid.sum() < 2:
        raise ValueError("invalid probability geometry/support")
    if not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError("probabilities must be finite nonnegative")
    if np.any(p[:, ~valid]) or np.any(p[..., ~valid]):
        raise ValueError("nonzero padding probability")
    if not np.allclose(p[:, valid].sum(-1), 1, atol=1e-12, rtol=0):
        raise ValueError("probability rows must sum to one")
    bins = np.flatnonzero(valid)
    selected = p[:, bins][:, :, :, bins]
    return np.sqrt(selected).transpose(1, 0, 2, 3).reshape(len(bins), -1) / np.sqrt(h * probes)


def squared_distances(dictionary, query):
    """Rows are query times, columns are dictionary times. No Gram subtraction."""
    a, b = np.asarray(dictionary), np.asarray(query)
    if a.ndim != 2 or b.shape != a.shape or a.dtype != np.float64 or b.dtype != np.float64:
        raise ValueError("fingerprint geometry/dtype differs")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("nonfinite fingerprint")
    result = np.empty((len(b), len(a)), dtype=np.float64)
    for t, row in enumerate(b):
        delta = a - row
        result[t] = np.sum(delta * delta, axis=1, dtype=np.float64)
    if not np.isfinite(result).all() or np.any(result < 0) or np.any(result > 2 + TIE_TOLERANCE):
        raise ValueError("squared probability distance outside [0,2]")
    return result


def analyze(dictionary_probability, query_probability, valid, spans):
    """Readout sees all dictionary rows; time labels enter only the evaluation."""
    a = fingerprint(dictionary_probability, valid)
    b = fingerprint(query_probability, valid)
    distances = squared_distances(a, b)
    bins = np.flatnonzero(valid)
    spans = np.asarray(spans)
    if spans.shape != (len(valid), 2) or spans.dtype.kind not in "iuf" or not np.isfinite(spans).all():
        raise ValueError("invalid physical spans")
    if np.any(spans[:, 1] < spans[:, 0]):
        raise ValueError("reversed physical span")
    times = spans[bins].astype(np.float64).mean(-1)
    if np.any(np.diff(times) <= 0):
        raise ValueError("physical time centers must increase")
    nearest = distances <= distances.min(-1, keepdims=True) + TIE_TOLERANCE
    diagonal = np.diag(distances).copy()
    off_diagonal = distances.copy()
    np.fill_diagonal(off_diagonal, np.inf)
    margins = off_diagonal.min(-1) - diagonal
    counts = nearest.sum(-1)
    unique_correct = (counts == 1) & np.diag(nearest) & (margins > TIE_TOLERANCE)
    bin_error = bins[None, :] - bins[:, None]
    time_error = times[None, :] - times[:, None]
    return {
        "squared_distances": distances,
        "diagonal_squared_distance": diagonal,
        "off_diagonal_margin": margins,
        "nearest_mask": nearest,
        "nearest_count": counts,
        "unique_correct": unique_correct,
        "nearest_min_absolute_bin_error": np.min(np.where(nearest, abs(bin_error), np.inf), -1),
        "nearest_max_absolute_bin_error": np.max(np.where(nearest, abs(bin_error), -np.inf), -1),
        "nearest_min_absolute_nominal_frame_error": np.min(np.where(nearest, abs(time_error), np.inf), -1),
        "nearest_max_absolute_nominal_frame_error": np.max(np.where(nearest, abs(time_error), -np.inf), -1),
        "valid_indices": bins,
        "nominal_frame_centers": times,
    }


def summarize(result):
    bins = result["valid_indices"]
    times = result["nominal_frame_centers"]
    rows = []
    for t, physical_bin in enumerate(bins):
        nearest = result["nearest_mask"][t]
        rows.append({
            "query_bin": int(physical_bin),
            "nominal_frame_center": float(times[t]),
            "off_diagonal_margin": float(result["off_diagonal_margin"][t]),
            "diagonal_squared_distance": float(result["diagonal_squared_distance"][t]),
            "nearest_dictionary_bins": bins[nearest].tolist(),
            "nearest_signed_bin_errors": (bins[nearest] - physical_bin).tolist(),
            "nearest_signed_nominal_frame_errors": (times[nearest] - times[t]).tolist(),
            "unique_correct": bool(result["unique_correct"][t]),
        })
    return {
        "tested_correlated_bins": len(bins),
        "unique_correct_count": int(result["unique_correct"].sum()),
        "all_unique_correct": bool(result["unique_correct"].all()),
        "minimum_margin": float(result["off_diagonal_margin"].min()),
        "mean_best_absolute_nominal_frame_error": float(result["nearest_min_absolute_nominal_frame_error"].mean()),
        "mean_worst_absolute_nominal_frame_error": float(result["nearest_max_absolute_nominal_frame_error"].mean()),
        "per_bin": rows,
    }
