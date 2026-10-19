"""Bounded, support-aware phase interval diagnostic. No model or file mutation."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
from physical_tolerance import align, CONF
from timing_metrics import load_pose

THRESHOLDS = (0.3, 0.5)
PARTS = ("left_arm", "right_arm")
NULL = tuple(range(-2, 3))
SEARCH = tuple(range(-24, 25))
PROPOSALS = tuple(sorted((d for d in SEARCH if d not in NULL), key=lambda d: (abs(d), d)))
EPS = 1e-12


@dataclass
class Context:
    x: np.ndarray
    confidence: np.ndarray
    targets: dict
    threshold: float
    part: str


def load_thresholds(path):
    results, failures = {}, {}
    for threshold in THRESHOLDS:
        try:
            results[threshold] = load_pose(path, threshold)
        except ValueError as exc:
            if str(exc) != "Insufficient reliable torso anchors for scale normalization":
                raise
            # Only this established scientific missingness is an UNKNOWN.
            results[threshold] = None
            failures[str(threshold)] = str(exc)
    return results, failures


def contexts(source, target, part, times, fps):
    name = part + "_direction"
    result = []
    for threshold in THRESHOLDS:
        a, b = source[threshold], target[threshold]
        if a is None:
            x = np.full((len(times), 2, 2), np.nan)
            confidence = np.zeros((len(times), 2))
        else:
            x, confidence = a[name], a[CONF[name]]
        if b is None:
            shifted = {d: (np.full_like(x, np.nan), np.zeros_like(confidence)) for d in SEARCH}
        else:
            shifted = {d: align(b, times + d / fps, name) for d in SEARCH}
        result.append(Context(x, confidence, shifted, threshold, part))
    return result


def common_arrays(context, offsets):
    """Exactly the same mask and confidence weights for every listed target."""
    arrays = [(context.x, context.confidence)] + [context.targets[d] for d in sorted(set(offsets))]
    valid = np.ones(context.x.shape[:2], dtype=bool)
    weight = np.ones(context.x.shape[:2], dtype=float)
    for values, confidence in arrays:
        valid &= np.isfinite(values).all(axis=-1)
        valid &= np.isfinite(confidence) & (confidence >= context.threshold)
        weight = np.minimum(weight, confidence)
    valid &= np.isfinite(weight)
    weight = np.where(valid, np.clip(weight, 0, 1), 0)
    return valid, weight


def distances(context, lag):
    return np.linalg.norm(context.x - context.targets[lag][0], axis=-1) / 2


def slot_evidence(context, lag):
    valid, weight = common_arrays(context, (*NULL, lag))
    proposal = distances(context, lag)
    null = np.min(np.stack([distances(context, e) for e in NULL]), axis=0)
    gain = np.where(valid, weight * (null - proposal), -1.0)
    if np.any(gain < -1 - 1e-10) or np.any(gain > 1 + 1e-10):
        raise ValueError("Unit-vector evidence exceeded its declared bounds")
    return {"gain": gain, "valid": valid, "weight": weight,
            "proposal_distance": proposal, "null_distance": null}


def interval_sums(per_frame):
    prefix = np.concatenate(([0.0], np.cumsum(per_frame, dtype=float)))
    return prefix[None, 1:] - prefix[:-1, None]


def code_cost(total, length):
    if total < 1 or length < 1 or length > total:
        raise ValueError("Invalid interval length")
    return 1 + math.ceil(math.log2(total)) + (2 * (int(length).bit_length() - 1) + 1) + 6 + 1


def code_grid(total):
    length = np.arange(1, total + 1)[None, :] - np.arange(total)[:, None]
    cost = np.zeros((total, total), dtype=float)
    for size in range(1, total + 1):
        cost[length == size] = code_cost(total, size)
    return cost, length


def scan_part(context_list):
    total = len(context_list[0].x)
    cost, length = code_grid(total)
    gains, feasible, raw = [], [], {}
    counts = {"all_intervals_per_lag": total * (total + 1) // 2,
              "support_rejected": 0, "residual_rejected": 0, "feasible": 0}
    for lag in PROPOSALS:
        both_rewards, both_okay = [], []
        for context in context_list:
            evidence = slot_evidence(context, lag)
            key = f"h{context.threshold}_d{lag}"
            raw[key + "_gain"] = evidence["gain"]
            raw[key + "_mask"] = evidence["valid"]
            raw[key + "_weight"] = evidence["weight"]
            raw[key + "_proposal_distance"] = evidence["proposal_distance"]
            valid_slots = interval_sums(evidence["valid"].sum(axis=-1))
            valid_frames = interval_sums((evidence["weight"].sum(axis=-1) > 0).astype(float))
            missing_frames = interval_sums((~evidence["valid"].any(axis=-1)).astype(float))
            support = ((length > 0) & (valid_slots >= 0.8 * length * 2) &
                       (valid_frames >= 8) & (missing_frames == 0))
            weights = interval_sums(evidence["weight"].sum(axis=-1))
            weighted_loss = interval_sums((np.nan_to_num(evidence["proposal_distance"]) * evidence["weight"]).sum(axis=-1))
            residual = np.divide(weighted_loss, weights, out=np.full_like(weights, np.inf), where=weights > 0)
            okay = support & (residual <= 0.25)
            counts["support_rejected"] += int(((length > 0) & ~support).sum())
            counts["residual_rejected"] += int((support & (residual > 0.25)).sum())
            both_rewards.append(interval_sums(evidence["gain"].sum(axis=-1) / 2))
            both_okay.append(okay)
        gains.append(np.minimum(*both_rewards))
        feasible.append(np.logical_and(*both_okay))
    gain = np.stack(gains)
    valid = np.stack(feasible)
    counts["feasible"] = int(valid.sum())
    raw.update(interval_gain=gain, interval_feasible=valid, code_cost=cost)
    return {"gain": gain, "feasible": valid, "cost": cost, "length": length,
            "raw": raw, "counts": counts, "contexts": context_list}


def full_scan(source, target, times, fps):
    return {part: scan_part(contexts(source, target, part, times, fps)) for part in PARTS}


def calibration_max(scans):
    best = None
    total_feasible = 0
    for pair_id, scan in scans:
        for part in PARTS:
            block = scan[part]
            total_feasible += int(block["feasible"].sum())
            ratio = np.divide(block["gain"], block["cost"][None],
                              out=np.full_like(block["gain"], -np.inf),
                              where=block["feasible"] & (block["cost"][None] > 0))
            i, a, b = np.unravel_index(np.argmax(ratio), ratio.shape)
            value = float(ratio[i, a, b])
            row = {"pair_id": pair_id, "part": part, "start": int(a), "end": int(b),
                   "lag": PROPOSALS[i], "reward": float(block["gain"][i, a, b]),
                   "code_cost": float(block["cost"][a, b]), "ratio": value}
            if math.isfinite(value) and (best is None or value > best["ratio"] + EPS):
                best = row
    if total_feasible == 0:
        return {"status": "UNKNOWN_CALIBRATION", "lambda": None, "feasible_intervals": 0, "maximizer": None}
    scale = max(0.0, best["ratio"])
    return {"status": "zero_empirical_scale" if scale == 0 else "empirical_scale",
            "lambda": scale, "feasible_intervals": total_feasible, "maximizer": best,
            "guarantee": "finite source pseudo-null family only; no generated-endpoint error-rate guarantee"}


def _key(row):
    return (row["start"], row["end"], abs(row["lag"]), row["lag"], PARTS.index(row["part"]))


def catalog(scan, scale, restricted=False):
    total = scan[PARTS[0]]["gain"].shape[-1]
    allowed = np.ones((total, total), dtype=bool)
    if restricted:
        allowed[:] = False
        for size in (16, 24, 32):
            if size > total:
                continue
            for a in sorted(set(range(0, total - size + 1, 4)) | {total - size}):
                allowed[a, a + size - 1] = True
    rows = []
    for part in PARTS:
        block = scan[part]
        values = np.where(block["feasible"] & allowed[None],
                          block["gain"] - scale * block["cost"][None], -np.inf)
        # PROPOSALS already follows the declared |lag|, lag order.
        best = np.max(values, axis=0)
        close = values >= best[None] - EPS
        lag_index = np.argmax(close, axis=0)
        for a, b in zip(*np.where(best > EPS)):
            i = int(lag_index[a, b])
            rows.append({"part": part, "start": int(a), "end": int(b), "lag": PROPOSALS[i],
                         "reward": float(block["gain"][i, a, b]),
                         "code_cost": float(block["cost"][a, b]), "value": float(values[i, a, b])})
    return rows


def solve_intervals(rows, total):
    """Exact weighted interval DP; missing physical frames remain on the timeline."""
    by_end = [[] for _ in range(total)]
    for row in rows:
        if not (0 <= row["start"] <= row["end"] < total):
            raise ValueError("Intervals must be zero-based closed physical frame ranges")
        if row["value"] > EPS:
            by_end[row["end"]].append(row)
    scores, paths = [0.0], [()]
    for b in range(total):
        best_score, best_path = scores[-1], paths[-1]
        for row in sorted(by_end[b], key=_key):
            value = scores[row["start"]] + row["value"]
            path = paths[row["start"]] + (row,)
            if value > best_score + EPS or (abs(value - best_score) <= EPS and
                    (len(path), tuple(map(_key, path))) < (len(best_path), tuple(map(_key, best_path)))):
                best_score, best_path = value, path
        scores.append(best_score)
        paths.append(best_path)
    return {"objective": scores[-1], "K": len(paths[-1]), "selected": list(paths[-1])}


def select(scan, scale, restricted=False, cross_part_exclusion=False):
    total = scan[PARTS[0]]["gain"].shape[-1]
    rows = catalog(scan, scale, restricted)
    counts = {p: sum(r["part"] == p for r in rows) for p in PARTS}
    if cross_part_exclusion:
        return solve_intervals(rows, total) | {"positive_best_phase_intervals_by_part": counts,
                                               "positive_complexity_penalty": scale > 0}
    parts = {p: solve_intervals([r for r in rows if r["part"] == p], total) for p in PARTS}
    selected = sorted([row for result in parts.values() for row in result["selected"]], key=_key)
    return {"objective": sum(v["objective"] for v in parts.values()), "K": len(selected),
            "selected": selected, "part_K": {p: v["K"] for p, v in parts.items()},
            "positive_best_phase_intervals_by_part": counts, "positive_complexity_penalty": scale > 0}


def phase_check(row, context_list):
    start, end, lag = row["start"], row["end"], row["lag"]
    sl = slice(start, end + 1)
    reasons, competitors, support_rows = [], [], []
    if abs(lag) == 24:
        reasons.append("UNKNOWN_SEARCH_BOUNDARY")
    for context in context_list:
        evidence = slot_evidence(context, lag)
        mask = evidence["valid"][sl]
        weight = evidence["weight"][sl]
        support_rows.append({"threshold": context.threshold, "nominal_slots": int(mask.size),
                             "known_slots": int(mask.sum()), "coverage": float(mask.mean()),
                             "known_slot_indices": [[int(start + t), int(b)] for t, b in zip(*np.where(mask))],
                             "weight_sum": float(weight.sum())})
        for other in SEARCH:
            if abs(other - lag) < 4:
                continue
            common, w = common_arrays(context, (*NULL, lag, other))
            common, w = common[sl], w[sl]
            coverage = float(common.mean())
            valid_frames = int((w.sum(axis=-1) > 0).sum())
            record = {"threshold": context.threshold, "competitor_lag": other,
                      "coverage": coverage, "valid_frames": valid_frames,
                      "known_slots": int(common.sum()), "nominal_slots": int(common.size),
                      "weight_sum": float(w.sum())}
            if coverage < 0.8 or valid_frames < 8 or w.sum() <= 0:
                record["status"] = "UNKNOWN_PHASE_COMPARISON"
                reasons.append(record["status"])
            else:
                cd = float((np.nan_to_num(distances(context, lag)[sl]) * w).sum() / w.sum())
                cq = float((np.nan_to_num(distances(context, other)[sl]) * w).sum() / w.sum())
                gap = (cq - cd) / max(cd, 1e-8)
                record.update(selected_cost=cd, competitor_cost=cq, relative_gap=gap,
                              status="separated" if gap >= 0.05 else "UNKNOWN_MULTIPLE_PHASES")
                if gap < 0.05:
                    reasons.append(record["status"])
            competitors.append(record)
    reasons = sorted(set(reasons))
    status = "UNKNOWN" if reasons else ("PHASE_CANDIDATE_DELAY" if lag > 0 else "PHASE_CANDIDATE_ADVANCE")
    return row | {"status": status, "reasons": reasons, "support": support_rows,
                  "competitors": competitors, "semantic_label": "UNKNOWN"}


def evaluate(scan, scale):
    methods = {}
    observability = frame_observability(scan)
    for name, restricted, cross_part in (("proposal", False, False),
            ("fixed_length_ablation", True, False), ("cross_part_exclusion_ablation", False, True)):
        start = time.perf_counter()
        chosen = select(scan, scale, restricted, cross_part)
        dp_seconds = time.perf_counter() - start
        start = time.perf_counter()
        chosen["selected"] = [phase_check(row, scan[row["part"]]["contexts"]) for row in chosen["selected"]]
        chosen["timing_seconds"] = {"catalog_and_dp": dp_seconds, "phase_competition": time.perf_counter() - start}
        chosen["qualified_K"] = sum(r["status"].startswith("PHASE_CANDIDATE") for r in chosen["selected"])
        chosen["rejected_K"] = chosen["K"] - chosen["qualified_K"]
        chosen["frame_selection_labels"] = {p: list(observability[p]["selection_default"]) for p in PARTS}
        for row in chosen["selected"]:
            known_frames = {t for t, bone in observed_slots(row)}
            for t in range(row["start"], row["end"] + 1):
                chosen["frame_selection_labels"][row["part"]][t] = row["status"] if t in known_frames else "UNKNOWN"
        chosen["coverage"] = method_coverage(chosen, observability)
        methods[name] = chosen
    return methods


def evidence_archive(scan):
    return {part + "__" + name: array for part, block in scan.items() for name, array in block["raw"].items()}


def frame_observability(scan):
    result = {}
    for part, block in scan.items():
        masks = [common_arrays(context, NULL)[0] for context in block["contexts"]]
        known = np.logical_and(*masks)
        result[part] = {"nominal_slots": int(known.size), "known_null_slots": int(known.sum()),
                        "known_mask": known.tolist(),
                        "base_frame_labels": ["NO_SUPPORTED_PHASE_DEVIATION" if row.any() else "UNKNOWN" for row in known],
                        "base_label_meaning": "Legacy protocol label for visible frames before selection; it does not mean all candidate phases lacked support or motion was aligned.",
                        "selection_default": ["NOT_SELECTED_BY_OBJECTIVE" if row.any() else "UNKNOWN" for row in known]}
    return result


def observed_slots(row):
    sets = [{tuple(slot) for slot in support["known_slot_indices"]} for support in row["support"]]
    return set.intersection(*sets) if sets else set()


def method_coverage(method, observability):
    selected, accepted_nominal, accepted_known, rejected, delay_known = set(), set(), set(), set(), set()
    for row in method["selected"]:
        nominal = {(row["part"], t, b) for t in range(row["start"], row["end"] + 1) for b in range(2)}
        selected |= nominal
        if row["status"].startswith("PHASE_CANDIDATE"):
            accepted_nominal |= nominal
            known = {(row["part"], t, b) for t, b in observed_slots(row)}
            accepted_known |= known
            if row["lag"] > 0:
                delay_known |= known
        else:
            rejected |= nominal
    denominator = sum(v["nominal_slots"] for v in observability.values())
    null_known = sum(v["known_null_slots"] for v in observability.values())
    return {"nominal_slots_denominator": denominator, "null_known_slots": null_known,
            "null_unknown_slots": denominator - null_known,
            "selected_nominal_slots": len(selected), "qualified_nominal_slots": len(accepted_nominal),
            "qualified_known_slots_both_thresholds": len(accepted_known),
            "qualified_delay_known_slots_both_thresholds": len(delay_known),
            "selected_but_unknown_nominal_slots": len(rejected),
            "note": "Nominal windows and observed slots are distinct. These are coverage counts, not correct/incorrect labels."}


def adjacent_persistence(indexed_methods):
    """Diagnostic persistence on adjacent physical denoising indices only."""
    pairs, participating = [], set()
    for index in sorted(indexed_methods):
        if index - 1 not in indexed_methods:
            continue
        previous = indexed_methods[index - 1]["selected"]
        current = indexed_methods[index]["selected"]
        for a in previous:
            for b in current:
                if a["status"] not in ("PHASE_CANDIDATE_DELAY", "PHASE_CANDIDATE_ADVANCE") or a["status"] != b["status"]:
                    continue
                if a["part"] != b["part"] or abs(a["lag"] - b["lag"]) > 2:
                    continue
                frames = {t for t, bone in observed_slots(a)} & {t for t, bone in observed_slots(b)}
                if frames:
                    pairs.append({"indices": [index - 1, index], "part": a["part"],
                                  "direction": "delay" if a["lag"] > 0 else "advance",
                                  "lags": [a["lag"], b["lag"]], "observed_frame_intersection": sorted(frames)})
                    participating.update((index - 1, index))
    return {"pairs": pairs, "participating_endpoints": sorted(participating),
            "delay_pairs": sum(r["direction"] == "delay" for r in pairs),
            "advance_pairs": sum(r["direction"] == "advance" for r in pairs),
            "interpretation": "correlated adjacent-endpoint persistence, not an independent confirmation probability"}
