"""Reference-only probability fingerprints; no model or generated-query input."""
from __future__ import annotations

import numpy as np


def finite(x, name):
    if not np.isfinite(x).all():
        raise ValueError(f"nonfinite {name}")
    return x


def pair_distance(a, b):
    """a [...,J], b [T,J]; output [...,T], no distance rescaling."""
    return np.linalg.norm(np.sqrt(a)[..., None, :] - np.sqrt(b), axis=-1)


def linear_code(template, observations, times):
    """Fit reference template only; retain per-heldout-row errors and inverse gain."""
    delta = template - template[0]
    x = delta - delta.mean(0)  # Exactly zero for identical reference rows.
    y = times - times.mean()
    u, singular, vh = np.linalg.svd(x, full_matrices=False)
    cutoff = np.finfo(np.float64).eps * max(x.shape) * np.linalg.norm(template, 2)
    retained = singular > cutoff
    weights = np.zeros(template.shape[-1], dtype=np.float64)
    if np.any(retained):
        weights = vh[retained].T @ ((u[:, retained].T @ y) / singular[retained])
    offset = times.mean() - template.mean(0) @ weights
    fit = template @ weights + offset
    prediction = observations @ weights + offset
    unresolved = y - u[:, retained] @ (u[:, retained].T @ y)
    result = {
        "weights": weights,
        "singular_values": singular,
        "rank": np.array(retained.sum(), dtype=np.int64),
        "rank_cutoff": np.array(cutoff),
        "inverse_gain": np.array(np.linalg.norm(weights)),
        "unresolved_time_norm": np.array(np.linalg.norm(unresolved)),
        "offset": np.array(offset),
        "fit_error": fit - times,
        "heldout_prediction": prediction,
        "heldout_error": prediction - times[:, None],
    }
    for name, value in result.items():
        finite(value, "linear " + name)
    return result


def analyze_reference(probability, spans, valid, folds):
    """One reference branch at one step, input [H,T,P,J].

    Caller validates fixed scientific geometry and probabilities. Every head is
    independently retained. No generated inputs, temporal labels or grid search.
    """
    bins = np.flatnonzero(valid)
    c = probability[:, bins][:, :, :, bins]
    times = np.asarray(spans, dtype=np.float64)[bins].mean(-1)
    time_distance = abs(times[:, None] - times[None, :])
    resolutions = np.unique(time_distance[time_distance > 0])
    by_head = []
    eps64 = np.finfo(np.float64).eps
    for head in c:
        by_fold = []
        for fold in folds:
            train = head[:, fold["train"], :]
            heldout = head[:, fold["test"], :]
            template = train.mean(1)
            loo_distances = []
            for i in range(train.shape[1]):
                other = np.delete(train, i, axis=1).mean(1)
                loo_distances.append(np.linalg.norm(np.sqrt(train[:, i]) - np.sqrt(other), axis=-1))
            loo_distances = np.stack(loo_distances, axis=1)
            radius = float(loo_distances.max())
            distances = pair_distance(heldout, template)
            diagonal = distances[np.arange(len(times)), :, np.arange(len(times))]
            numeric_tolerance = 64 * eps64
            candidates = distances <= radius + numeric_tolerance
            count = candidates.sum(-1)
            lower = np.min(np.where(candidates, times, np.inf), axis=-1)
            upper = np.max(np.where(candidates, times, -np.inf), axis=-1)
            diameter = np.where(count > 0, upper - lower, np.nan)
            # NaN denotes empty sets in numeric arrays; JSON summaries mask them.
            nearest_distance = distances.min(-1)
            nearest = abs(distances - nearest_distance[..., None]) <= numeric_tolerance
            errors = abs(times[None, None, :] - times[:, None, None])
            nearest_min_error = np.min(np.where(nearest, errors, np.inf), axis=-1)
            nearest_max_error = np.max(np.where(nearest, errors, -np.inf), axis=-1)
            pairwise = pair_distance(template, template)
            curve = np.array([pairwise[time_distance >= resolution].min() for resolution in resolutions])
            row = {
                "template": template,
                "pairwise_distance": pairwise,
                "heldout_distances": distances,
                "training_loo_residual": loo_distances,
                "training_radius": np.array(radius),
                "heldout_correct_template_distance": diagonal,
                "heldout_max_radius_descriptive": np.array(diagonal.max()),
                "candidate_mask": candidates,
                "candidate_count": count,
                "candidate_diameter": diameter,
                "candidate_contains_correct_time": candidates[np.arange(len(times)), :, np.arange(len(times))],
                "nearest_mask": nearest,
                "nearest_distance": nearest_distance,
                "nearest_min_abs_time_error": nearest_min_error,
                "nearest_max_abs_time_error": nearest_max_error,
                "minimum_separation_curve": curve,
                "training_radius_margin_curve": curve - 2 * radius,
                "heldout_radius_margin_descriptive": curve - 2 * diagonal.max(),
            }
            row.update({"linear_" + k: v for k, v in linear_code(template, heldout, times).items()})
            by_fold.append(row)
        by_head.append({name: np.stack([fold[name] for fold in by_fold]) for name in by_fold[0]})
    arrays = {name: np.stack([head[name] for head in by_head]) for name in by_head[0]}
    arrays.update(valid_indices=bins, physical_time_centers=times, resolutions=resolutions)
    return arrays


def stats(value):
    value = np.asarray(value, dtype=np.float64)
    value = value[np.isfinite(value)]
    if not value.size:
        return {"count": 0, "mean": None, "min": None, "median": None, "max": None}
    return {"count": int(value.size), "mean": float(value.mean()), "min": float(value.min()),
            "median": float(np.median(value)), "max": float(value.max())}


def summarize(arrays):
    """Small summaries after all heads/folds computed; no acceptance decision."""
    rows = []
    for h in range(arrays["candidate_count"].shape[0]):
        for f in range(arrays["candidate_count"].shape[1]):
            count = arrays["candidate_count"][h, f]
            error = arrays["linear_heldout_error"][h, f]
            rows.append({
                "head": h, "fold": f,
                "training_radius": float(arrays["training_radius"][h, f]),
                "heldout_max_radius_descriptive": float(arrays["heldout_max_radius_descriptive"][h, f]),
                "empty_fraction": float(np.mean(count == 0)),
                "singleton_fraction": float(np.mean(count == 1)),
                "multiple_fraction": float(np.mean(count > 1)),
                "correct_time_in_candidate_fraction": float(arrays["candidate_contains_correct_time"][h, f].mean()),
                "candidate_count": stats(count),
                "candidate_diameter_nonempty": stats(arrays["candidate_diameter"][h, f]),
                "nearest_best_abs_time_error": stats(arrays["nearest_min_abs_time_error"][h, f]),
                "nearest_worst_abs_time_error": stats(arrays["nearest_max_abs_time_error"][h, f]),
                "linear_rank": int(arrays["linear_rank"][h, f]),
                "linear_inverse_gain": float(arrays["linear_inverse_gain"][h, f]),
                "linear_unresolved_time_norm": float(arrays["linear_unresolved_time_norm"][h, f]),
                "linear_heldout_rmse": float(np.sqrt(np.mean(error ** 2))),
                "linear_heldout_max_abs_error": float(np.max(abs(error))),
            })
    return {"per_head_fold": rows, "all_heads_retained": len(rows) // 2,
            "generated_domain_validated": False, "controller_released": False,
            "candidate_threshold_is_reference_training_radius_only": True}
