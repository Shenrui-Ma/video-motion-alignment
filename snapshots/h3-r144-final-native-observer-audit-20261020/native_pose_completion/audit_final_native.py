"""CPU-only reuse of frozen R133/R138 rules over existing final Native pose."""
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "frozen/scripts"), str(ROOT / "frozen/extensions")]
import scan_current_pose as scan
from H3AutomaticWindowRouter import automatic_window_policy as policy
from H3AutomaticWindowRouter.geometry import Geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def supported(diagnostic):
    same = diagnostic["same_frame"]
    return same["coverage"] >= .8 and same["valid_frame_count"] >= 8


def reasons(row):
    if policy.candidate(row) is not None:
        return []
    tags = []
    for value in row["measurements"].values():
        if value["status"] == "unreliable_detection_coverage":
            tags.append("unreliable_detection_coverage")
        tags.extend(value.get("flags", []))
    if row["baseline"] == "aligned":
        tags.append("within_two_frame_tolerance")
    elif row["baseline"] == "unknown":
        tags.append("no_consistent_reliable_signed_lag")
    for value in row.get("comparison", {}).values():
        tags.extend(r["status"] for r in value["null_comparisons"] if r["status"] != "valid")
    if row["status"] == "measured" and row["min_gain"] <= .5:
        tags.append("min_gain_not_above_0.5")
    return sorted(set(tags))


def main():
    manifest = json.loads((ROOT / "INPUTS.json").read_text())
    for item in manifest["rules"]:
        assert sha(ROOT / item["copy"]) == item["sha256"]
    result = {"scope": manifest["scope"],
              "definitions": {
                  "row": "one inclusive window × arm descriptor; confidence thresholds jointly checked",
                  "source_supported_rows": "source self-pair at lag 0 has coverage>=0.8 and >=8 valid frames at both confidences",
                  "supported_pair_rows": "source/Native lag0 pair has coverage>=0.8 and >=8 valid frames at both confidences",
                  "coverage_qualified_lag_rows": "both original local diagnostics pass their full lag-support gate",
                  "signed_lag_candidates": "consistent reliable lag outside ±2 at confidence 0.3 and 0.5",
                  "eligible_candidates": "unchanged automatic_window_policy.candidate(row,0.5) returns a proposal",
                  "lags": "positive means Native is later; frames at24fps",
                  "rejection_reason_counts": "row counts per reason; reasons overlap",
                  "online_persistence": "not evaluated; no consecutive sampler observations are available",
                  "content_boundary_filter": False},
              "cases": []}
    for case in manifest["cases"]:
        g = Geometry.from_case(case["geometry_case"])
        paths = case["poses"]
        for entry in paths.values():
            if entry:
                assert sha(entry["path"]) == entry["sha256"]
        raw = scan.valid_pose(paths["source"]["path"], g)
        features = {c: scan.features(raw, g, c) for c in scan.CONFIDENCE}
        source_support = [
            {"window": window, "feature": feature}
            for window in g.windows() for feature in scan.FEATURES
            if all((p := scan.m.pair_error(features[c], features[c], window, 0, feature))["coverage"] >= .8
                   and p["valid_frame_count"] >= 8 for c in scan.CONFIDENCE)]
        item = {"source_id": case["source_id"], "native_run": case["native_run"],
                "status": case["status"], "valid_frames": g.valid_frames,
                "total_window_feature_rows": len(list(g.windows())) * len(scan.FEATURES),
                "source_supported_rows": len(source_support), "source_support": source_support,
                "poses": paths, "supported_pair_rows": None, "eligible_candidates": None}
        if paths["native"] is None:
            item["reason"] = "No matching final Native pose found in recorded local/known producer and MF caches."
            result["cases"].append(item)
            continue
        observed = scan.observe(paths["source"]["path"], paths["native"]["path"], 0, g)
        observed["offline_final_native_only"] = True
        observed["physical_index_semantics"] = "0 is an API placeholder, not a sampler observation or trigger."
        output = ROOT / f"{case['source_id']}_FINAL_NATIVE_SCAN.json"
        output.write_text(json.dumps(observed, ensure_ascii=False, allow_nan=False) + "\n")
        rows = observed["windows"]
        candidates = [c for row in rows if (c := policy.candidate(row)) is not None]
        rejected = [row for row in rows if policy.candidate(row) is None]
        item.update({
            "scan": {"path": output.name, "sha256": sha(output)},
            "supported_pair_rows": sum(all(supported(d) for d in r["measurements"].values()) for r in rows),
            "coverage_qualified_lag_rows": sum(all(d["status"] != "unreliable_detection_coverage"
                                                 for d in r["measurements"].values()) for r in rows),
            "baseline_counts": dict(collections.Counter(r["baseline"] for r in rows)),
            "signed_lag_candidates": sum(r["baseline"] in ("delayed_candidate", "advanced_candidate") for r in rows),
            "eligible_candidates": len(candidates), "candidates": candidates,
            "eligible_lag_counts": dict(collections.Counter(
                str(c["lags"]["0.3"]) + "/" + str(c["lags"]["0.5"]) for c in candidates)),
            "components": policy.components(rows),
            "rejection_reason_counts": dict(collections.Counter(t for row in rejected for t in reasons(row))),
            "rejected_rows": [{"window": r["window"], "feature": r["feature"], "baseline": r["baseline"],
                               "reasons": reasons(r)} for r in rejected],
        })
        # Existing handkerchief scan is an independent previous invocation of the same rules.
        original = Path(paths["native"]["path"]).parents[1] / "SCAN.json"
        if original.exists():
            old = json.loads(original.read_text())
            assert old["source_pose_sha256"] == observed["source_pose_sha256"]
            assert old["edited_pose_sha256"] == observed["edited_pose_sha256"]
            assert old["windows"] == observed["windows"]
            item["previous_scan_exact_rows_match"] = {"path": str(original), "sha256": sha(original)}
        result["cases"].append(item)
    assert "torch" not in sys.modules, "CPU audit must not import model runtime"
    result["validation"] = {"frozen_rule_hashes_match": True, "pose_hashes_match": True,
                            "torch_imported_by_scan": False, "new_pose_extraction_by_scan": False,
                            "separate_authorized_CPU_extractions": ["long_0039", "short_0358"],
                            "CPU_extraction_manifest": "EXTRACTION_MANIFEST.json", "GPU_started": False}
    (ROOT / "RESULTS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps([{k: v for k, v in c.items() if k not in (
        "source_support", "poses", "candidates", "components", "rejected_rows")} for c in result["cases"]],
        ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
