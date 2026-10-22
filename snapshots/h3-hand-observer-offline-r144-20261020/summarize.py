"""Report the already required common-support gate without changing any scans."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def sha(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def supported(row):
    return (row.get("best_lag") is not None
            and row.get("all_null_support_qualified") is True
            and row.get("delta_support_qualified_every_null") is True)


def compact(row):
    names = ("window", "confidence", "best_lag", "all_null_support_qualified",
             "delta_support_qualified_every_null",
             "minimum_centered_relative_improvement",
             "delta_same_lag_improves_every_null")
    return {key: row.get(key) for key in names}


actual, controls, first = read("ACTUAL_ALL_WINDOWS.json"), read("CONTROL_WINDOWS.json"), read("RESULT.json")
assert len(actual) == 124
expected = {"self": 0, "constant2Doffset": 0, "missing64..79": 0}
for lag in (-8, -4, 4, 8):
    expected[f"delay{lag:+d}"] = lag
expected.update({"delay-8_plus_offset": -8, "delay+8_plus_offset": 8})
control_rows = {}
for name, rows in controls.items():
    if name == "equal_distance_opposite_direction":
        control_rows[name] = first["controls"][name]
        continue
    qualified = [row for row in rows if supported(row)]
    rejected = [row for row in rows if row.get("best_lag") is not None and not supported(row)]
    wrong = ([row for row in qualified if row["best_lag"] != expected[name]]
             if name in expected else qualified)
    control_rows[name] = {
        "total_window_threshold_rows": len(rows),
        "common_frame_and_difference_support_qualified": len(qualified),
        "all_other_rows_UNKNOWN": len(rows) - len(qualified),
        "raw_argmins_rejected_for_support": len(rejected),
        "qualified_lag_counts": {
            str(lag): sum(row["best_lag"] == lag for row in qualified)
            for lag in sorted({row["best_lag"] for row in qualified})},
        "wrong_supported_lag_rows": [compact(row) for row in wrong],
        "passed": len(wrong) == 0 and (
            len(qualified) > 0 if name in expected else len(qualified) == 0),
    }
qualified_actual = [x for x in actual if supported(x)]
positive = [x for x in qualified_actual if x["best_lag"] > 2]
strong_delta = [x for x in positive if x["delta_same_lag_improves_every_null"]]
withdrawal = [x for x in qualified_actual
              if x["window"][0] <= 98 and x["window"][1] >= 95]
same = lambda x: {k: v for k, v in x.items() if k != "confidence"}
t3 = [same(x) for x in actual if x["confidence"] == .3]
t5 = [same(x) for x in actual if x["confidence"] == .5]
summary = {
    "schema": "r144-hand-offline-common-support-summary-v1",
    "result_sha256": sha("RESULT.json"),
    "all_windows_sha256": sha("ACTUAL_ALL_WINDOWS.json"),
    "control_windows_sha256": sha("CONTROL_WINDOWS.json"),
    "reporting_rule": (
        "Apply only support requirements already in frozen candidate: all five "
        "proposal/null comparisons each require >=.8 frame coverage and >=8 frames; "
        "adjacent-difference support likewise >=.8 of L-1 and >=8 pairs. "
        "No numerical activity, residual or gain threshold is added."),
    "raw_argmin_control_failure_preserved": first["controls"]["missing64..79"],
    "controls_with_required_common_support": control_rows,
    "all_common_support_controls_passed": all(x["passed"] for x in control_rows.values()),
    "actual": {
        "physical_windows": 62, "thresholds": [.3, .5],
        "total_window_threshold_rows": len(actual),
        "common_support_qualified_rows": len(qualified_actual),
        "UNKNOWN_rows": len(actual) - len(qualified_actual),
        "positive_lag_over2_rows": len(positive),
        "positive_lag_and_delta_improves_all_nulls_rows": len(strong_delta),
        "threshold_results_identical": t3 == t5,
        "supported_rows": [compact(x) for x in qualified_actual],
        "withdrawal_overlap_reporting_only": [compact(x) for x in withdrawal],
    },
    "interpretation": [
        "The wrist/nose feature detects a +13..15-frame shift in supported windows overlapping the known withdrawal interval.",
        "Supported raise/contact windows estimate0..1 frames, consistent with the existing near-synchronous review.",
        "The missing-data control creates26 incorrect raw argmins across two thresholds; every one fails the frozen common-support requirement and remains UNKNOWN.",
        "Some earlier/mid-action windows also have positive estimates with low gain; all-window results are retained. Activity/residual reliability is not calibrated.",
        "This is fixed final-video trajectory feasibility, not an online policy or closed-loop benefit test.",
    ],
    "original_policy_modified": False,
    "GPU_started": False,
}
(ROOT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({
    "summary_sha256": sha("SUMMARY.json"),
    "all_common_support_controls_passed": summary["all_common_support_controls_passed"],
    "actual_qualified": len(qualified_actual),
    "withdrawal_rows": len(withdrawal),
    "controls": {k: {a: v[a] for a in ["passed", "qualified_lag_counts"]
                     if a in v} for k, v in control_rows.items()},
}))
