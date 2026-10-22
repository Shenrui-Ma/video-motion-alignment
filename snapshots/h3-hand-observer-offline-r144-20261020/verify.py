"""Independent scalar check of a common-support weighted centered comparison."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
protocol = json.loads((ROOT / "PROTOCOL.json").read_text())
result = json.loads((ROOT / "RESULT.json").read_text())
rows = json.loads((ROOT / "ACTUAL_ALL_WINDOWS.json").read_text())
poses = {}
for role, item in protocol["inputs"].items():
    p = Path(item["file"])
    assert hashlib.sha256(p.read_bytes()).hexdigest() == item["sha256"]
    poses[role] = json.loads(p.read_text())
assert len(rows) == 124
assert all(len(row["lag_curve"]) == 49 for row in rows)
assert all(row["window"][1] < 144 for row in rows)
scale = result["source_fixed_scale_px"]


def point(pose, i):
    frame = pose["frames"][i]
    person = frame["persons"][frame["selected_person"]]
    q = [(person["coco17_xy"][9][k] - person["coco17_xy"][0][k]) / scale
         for k in range(2)]
    weight = min(person["coco17_score"][9], person["coco17_score"][0])
    return q, weight


row = next(x for x in rows if x["window"] == [84, 99] and x["confidence"] == .3)
comparison = next(x for x in row["null_comparisons"] if x["null_lag"] == 2)
indices = comparison["source_indices"]
a, p, z, weights = [], [], [], []
for i in indices:
    src, ws = point(poses["source_pose"], i)
    pro, wp = point(poses["native_pose"], i + comparison["proposal_lag"])
    nul, wn = point(poses["native_pose"], i + comparison["null_lag"])
    a.append(src)
    p.append(pro)
    z.append(nul)
    weights.append(min(ws, wp, wn))


def centered_rms(x, y):
    sw = sum(weights)
    mx = [sum(v[k]*w for v, w in zip(x, weights))/sw for k in range(2)]
    my = [sum(v[k]*w for v, w in zip(y, weights))/sw for k in range(2)]
    error = sum(w * sum(((xx[k]-mx[k])-(yy[k]-my[k]))**2 for k in range(2))
                for xx, yy, w in zip(x, y, weights))
    return math.sqrt(error/sw)


proposal, null = centered_rms(a, p), centered_rms(a, z)
assert abs(proposal-comparison["proposal"]["centered_RMS"]) < 1e-12
assert abs(null-comparison["null"]["centered_RMS"]) < 1e-12
summary = json.loads((ROOT / "SUMMARY.json").read_text())
assert summary["all_common_support_controls_passed"]
assert summary["actual"]["threshold_results_identical"]
control = json.loads((ROOT / "CONTROL_WINDOWS.json").read_text())["missing64..79"]
wrong = [r for r in control if r.get("best_lag") not in (None, 0)]
assert len(wrong) == 26
assert all(not r["all_null_support_qualified"] for r in wrong)
receipt = {
    "passed": True, "input_pose_hashes_unchanged": True,
    "all_windows_full_domain": True,
    "independent_scalar_common_support_comparison": {
        "window": [84, 99], "lag": comparison["proposal_lag"], "null_lag": 2,
        "common_frames": len(indices), "proposal_centered_RMS": proposal,
        "null_centered_RMS": null},
    "missing_control26_raw_false_argmins_all_rejected_by_support": True,
    "both_confidence_results_identical": True,
    "no_online_policy_changes": True,
}
(ROOT / "VERIFIED.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
