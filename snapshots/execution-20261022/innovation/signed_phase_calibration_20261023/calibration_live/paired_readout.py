"""Pair observations at identical query times, without generated-event selection."""
import numpy as np

from evaluate_live import base


def cross_key_decomposition(native, weak, weak_query_native_key, native_query_weak_key, spans, valid):
    """Symmetric finite-difference attribution to changed Q and changed K.

    These terms identify the source of the retrieval change, not a causal
    separation of motion and appearance.
    """
    if len({np.asarray(a).shape for a in (native, weak, weak_query_native_key, native_query_weak_key)}) != 1:
        raise ValueError("all four retrievals must retain the same heads, probes and time support")
    _, checked = compare(native, weak, native, weak, spans, valid, [])
    _, cross = compare(native_query_weak_key, weak_query_native_key,
                       native_query_weak_key, weak_query_native_key, spans, valid, [])
    total = checked["weak_minus_native"]
    query = .5 * (total + cross["weak_minus_native"])
    key = .5 * (total - cross["weak_minus_native"])
    return {"paired_total": total, "query_contribution": query, "key_contribution": key,
            "max_decomposition_error": float(np.max(np.abs(total - query - key)))}


def compare(native, weak, native_self, weak_self, spans, valid, source_events):
    valid = np.asarray(valid, dtype=bool)
    spans = base.validate_spans(spans, valid)
    arrays = [np.asarray(a, dtype=np.float64) for a in (native, weak, native_self, weak_self)]
    shape = arrays[0].shape
    if len(shape) != 4 or shape[1] != len(valid) or shape[3] != len(valid):
        raise ValueError("expected H,T,P,T probability arrays")
    for a in arrays:
        if (a.shape != shape or not np.isfinite(a).all() or (a < 0).any()
                or not np.allclose(a[:, valid].sum(-1), 1, rtol=0, atol=1e-12)
                or np.any(a[:, ~valid]) or np.any(a[..., ~valid])):
            raise ValueError("all methods must use identical finite valid support")
    centers = spans.mean(axis=1)
    means = [np.einsum("htpj,j->htp", a, centers) for a in arrays]
    delta = means[1] - means[0]
    self_delta = means[3] - means[2]
    contrast = delta - self_delta
    # Remove a constant time bias only as a separately named diagnostic.
    # It is never substituted for the raw paired readout.
    centered = delta - delta[:, valid].mean(axis=1, keepdims=True)
    rows = []
    for event in source_events:
        lo, hi = event["source_interval_frames"]
        bins = np.flatnonzero(valid & (spans[:, 0] <= hi) & (spans[:, 1] >= lo))
        row = {"event_id": event["id"], "source_interval": [lo, hi], "common_query_bins": bins.tolist()}
        if not len(bins):
            rows.append({**row, "status": "missing_source_bin_support"})
            continue
        rows.append({**row, "status": "measured_at_identical_query_times",
                     "weak_minus_native_reference_mean_frames": base.quantiles(delta[:, bins]),
                     "reference_self_drift_frames": base.quantiles(self_delta[:, bins]),
                     "self_drift_subtracted_diagnostic": base.quantiles(contrast[:, bins]),
                     "time_constant_bias_removed_diagnostic": base.quantiles(centered[:, bins])})
    report = {"scope": "paired content retrieval at the same physical query bins",
              "positive_sign": "weak queries retrieve later reference content than native queries",
              "generated_event_times_used_to_select_query_rows": False,
              "events": rows, "expected_event_count": len(source_events),
              "measured_event_count": sum(r["status"] == "measured_at_identical_query_times" for r in rows),
              "all_valid_rows": base.quantiles(delta[:, valid]),
              "reference_self_drift_all_rows": base.quantiles(self_delta[:, valid]),
              "semantic_phase_validated": False}
    return report, {"native_mean": means[0], "weak_mean": means[1],
                    "weak_minus_native": delta, "reference_self_drift": self_delta,
                    "self_drift_subtracted": contrast, "time_constant_bias_removed": centered,
                    "valid_bins": valid, "physical_frame_spans_inclusive": spans}
