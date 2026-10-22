"""Read-only paired-cohort statistics from a frozen collector snapshot.

No queue/network/evaluator access. Each video has equal weight. Complete means
require both prespecified videos; partial means are kept in separate fields.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
E = HERE.parents[3]
COHORTS = {
    "original_pilots": ("short_0252", "short_0358"),
    "book_handkerchief_extension": ("long_0039", "long_0059"),
}
METRICS = (
    "subject_consistency", "background_consistency", "temporal_flickering",
    "motion_smoothness", "vtss", "overall_semantic_consistency",
    "phrase_semantic_consistency", "semantic_fidelity", "motion_fidelity",
)
ROLES = ("source", "native", "global_weak")
TIMING_NOTE = (
    "Actual recorded sampling time, equally weighted per video. Shared hardware, "
    "different hosts and historical capture scopes are not controlled; no speed benefit is inferred."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def unique(rows, key, label):
    out = {}
    for row in rows:
        identity = row[key]
        require(identity not in out, f"{label}: duplicate {identity}")
        out[identity] = row
    return out


def value(status, score=None, **extra):
    return {"status": status, "score": score, **extra}


def metric(record, key, verified=True):
    item = record.get("metrics", {}).get(key, {})
    if not verified:
        return value("unverified", reason="video is not collector-verified")
    status = item.get("status", "pending")
    if status == "done":
        score = item.get("score")
        if not finite(score) or score == -1:
            return value("invalid", reason="nonfinite score or official error sentinel")
        return value("done", float(score))
    require(item.get("score") is None, f"{key}: non-done metric carries a score")
    return value(status, reason=item.get("reason"))


def difference(left, right):
    if left["status"] == right["status"] == "done":
        return value("done", left["score"] - right["score"])
    status = next((s for s in ("not_applicable", "invalid", "failed", "unverified")
                   if s in (left["status"], right["status"])), "pending")
    return value(status, left_status=left["status"], right_status=right["status"])


def aggregate(items):
    """Never publish an incomplete sample mean under the complete-mean key."""
    done = [item["score"] for item in items if item["status"] == "done"]
    require(all(finite(x) for x in done), "nonfinite aggregate input")
    n, expected = len(done), len(items)
    return {
        "status": "complete" if n == expected and expected else "partial" if n else "unavailable",
        "n_done": n, "n_expected": expected,
        "complete_mean": mean(done) if n == expected and expected else None,
        "partial_mean": mean(done) if 0 < n < expected else None,
        "status_counts": dict(Counter(item["status"] for item in items)),
    }


def interval(item, frame_count):
    if item is None:
        return None
    require(isinstance(item, list) and len(item) == 2 and
            all(type(x) is int for x in item) and 0 <= item[0] <= item[1] < frame_count,
            "invalid event interval")
    return mean(item)


def event_value(frozen, role, annotation=None):
    """Recompute all frozen events, then reduce within one video only."""
    old = unique(frozen["events"], "id", "frozen events")
    require(old, "empty frozen event set")
    count = frozen["valid_frames"]
    events = unique(annotation["events"], "id", "new events") if annotation else old
    require(set(events) == set(old), "frozen event IDs changed or missing")
    offsets, evidence = [], []
    for key, base in old.items():
        src = interval(base["source"], count)
        event = events[key]
        if annotation:
            require(event.get("source_interval") == base["source"], "frozen source interval changed")
            raw = event.get("new_interval")
            present = event.get("event_present") is not False
        else:
            raw = base.get(role)
            present = base.get("status_by_role", {}).get(role, "measured") == "measured"
        mid = interval(raw, count)
        signed = mid - src if mid is not None and present else None
        if annotation and signed is not None:
            require(finite(event.get("signed_offset_frames")) and
                    math.isclose(signed, event["signed_offset_frames"], abs_tol=1e-9),
                    "event signed offset mismatch")
        if signed is not None:
            offsets.append(abs(signed))
        evidence.append({"id": key, "source_interval": base["source"],
                         "interval": raw, "signed_offset_frames": signed})
    complete = len(offsets) == len(old)
    result = mean(offsets) if complete else None
    reported = (annotation.get("mean_absolute_offset_frames") if annotation else
                frozen.get("means", {}).get(role))
    if complete and reported is not None:
        require(finite(reported) and math.isclose(result, reported, abs_tol=1e-9), "event mean mismatch")
    if not complete:
        require(reported is None, "incomplete event set carries a numerical mean")
    return value("done" if complete else "incomplete_events", result,
                 n_events_done=len(offsets), n_events_expected=len(old), events=evidence)


def output_sha(row):
    hashes = {x.get("actual_sha256") for x in row.get("media", []) if x.get("status") == "verified"}
    hashes.discard(None)
    require(len(hashes) == 1, "verified video must have exactly one output SHA")
    return next(iter(hashes))


def validate_controls(task, frozen, manifest):
    require(frozen.get("case_id") == task, "frozen case identity mismatch")
    out = {}
    for role in ROLES:
        job_id = task + "__" + role
        require(job_id in manifest, "missing frozen control " + job_id)
        record = manifest[job_id]
        expected = frozen.get("video_provenance", {}).get(role, {}).get("sha256")
        require(expected and record.get("sha256") == expected, "frozen control SHA mismatch")
        require(record.get("task_id") == task and record.get("method") == role,
                "frozen control identity mismatch")
        require(record.get("fps") == frozen["fps"] and record.get("valid_frames") == frozen["valid_frames"],
                "frozen control geometry mismatch")
        out[role] = record
    return out


def validate_visual(row, frozen, visual):
    annotation = visual.get("annotation")
    if annotation is None:
        return value("pending", reason="visual annotation not available")
    prov = visual.get("provenance")
    require(isinstance(prov, dict), "annotation has no provenance")
    for obj in (annotation, prov):
        require(obj.get("job_id") == row["job_id"] and obj.get("method") == row["method"],
                "visual identity mismatch")
    sha = output_sha(row)
    require(annotation.get("video_sha256") == sha and prov.get("generated_sha256") == sha,
            "visual output SHA mismatch")
    require(annotation.get("task_id") == row["task_id"] and annotation.get("fps") == frozen["fps"],
            "annotation task/fps mismatch")
    require(prov.get("fps") == frozen["fps"] and prov.get("valid_frames") == frozen["valid_frames"],
            "visual geometry mismatch")
    controls = unique(prov["controls"], "id", "visual controls")
    for role in ROLES:
        key = row["task_id"] + "__" + role
        expected = frozen["video_provenance"][role]["sha256"]
        require(controls.get(key, {}).get("sha256") == expected, "visual frozen control SHA mismatch")
    return event_value(frozen, row["method"], annotation)


def timing(record, verified):
    raw = record.get("timing") or {}
    out = {"host": record.get("producer_host") or raw.get("host"), "scope": raw.get("scope"),
           "measurement_basis": raw.get("measurement_basis")}
    for key, alternate in (("sampling_seconds", "sampling_seconds"),
                           ("mean_step_seconds", "mean_sampling_step_seconds")):
        x = raw.get(key, raw.get(alternate))
        out[key] = value("done", float(x)) if verified and finite(x) and x >= 0 else value("pending")
    return out


def summarize(status, official, controls_manifest, frozen, visuals=None, cohorts=None):
    """Pure, importable API. Visual records map job_id to annotation/provenance."""
    visuals = visuals or {}
    cohorts = cohorts or COHORTS
    tasks = [t for ts in cohorts.values() for t in ts]
    require(len(tasks) == len(set(tasks)), "cohorts overlap")
    rows = unique(status["jobs"], "job_id", "collector jobs")
    cases = unique(official.get("cases", []), "job_id", "official metric cases")
    identities = [(r["task_id"], r["method"]) for r in rows.values()]
    require(len(identities) == len(set(identities)), "duplicate task/method")
    by_identity = {(r["task_id"], r["method"]): r for r in rows.values()}
    manifest = unique(controls_manifest["jobs"], "id", "control manifest")
    controls, control_scores = {}, {}
    for task in tasks:
        require(task in frozen, "missing frozen annotation " + task)
        controls[task] = validate_controls(task, frozen[task], manifest)
    for jid, case in cases.items():
        require(jid in rows, "metric case absent from collector")
        row = rows[jid]
        require((case.get("task_id"), case.get("method")) == (row["task_id"], row["method"]),
                "metric/collector identity mismatch")
        if row["task_id"] not in tasks:
            continue
        for role in ROLES:
            rec = case.get("controls", {}).get(role, {})
            require(rec.get("job_id") == row["task_id"] + "__" + role, "metric control identity mismatch")
            key = row["task_id"], role
            signature = {k: metric(rec, k) for k in METRICS}
            if key in control_scores:
                require(signature == control_scores[key]["metrics"], "inconsistent repeated control scores")
            else:
                control_scores[key] = {"metrics": signature, "record": rec}
    output = {"schema": "h3-paired-cohorts-v1", "cohorts": {}, "notes": {
        "means": "Complete means require both prespecified videos. Partial means are separate and retain n/2.",
        "events": "Mean absolute midpoint offset over every frozen event within each video, then equal video weights.",
        "reference_mf": "Method MF minus that task's reference-self MF, paired before averaging.",
        "sampling": TIMING_NOTE, "awq": "Not combined; nine official metrics only.",
    }}
    for cohort_name, task_ids in cohorts.items():
        methods = sorted({r["method"] for r in rows.values() if r["task_id"] in task_ids} | {"native", "global_weak"})
        cohort = {"task_ids": list(task_ids), "n_expected": len(task_ids), "methods": {}}
        for method in methods:
            samples = []
            for task in task_ids:
                row = by_identity.get((task, method))
                is_control = method in ("native", "global_weak")
                verified = is_control or bool(row and row["status"] == "verified")
                rec = control_scores.get((task, method), {}).get("record", {}) if is_control else cases.get(row["job_id"], {}) if row else {}
                weak = control_scores.get((task, "global_weak"), {}).get("record", {})
                source = control_scores.get((task, "source"), {}).get("record", {})
                metrics = {k: metric(rec, k, verified) for k in METRICS}
                if is_control:
                    events = event_value(frozen[task], method)
                    rt = timing(rec if rec.get("timing") else controls[task][method], verified)
                    identity = task + "__" + method
                    collection_status = "frozen_control_verified"
                else:
                    events = (validate_visual(row, frozen[task], visuals.get(row["job_id"], {})) if verified else
                              value("unverified", reason=row["status"] if row else "not_planned"))
                    rt = timing(row or {}, verified)
                    identity = row["job_id"] if row else None
                    collection_status = row["status"] if row else "not_planned"
                weak_event = event_value(frozen[task], "global_weak")
                samples.append({"task_id": task, "job_id": identity, "verified": verified,
                    "collection_status": collection_status, "metrics": metrics,
                    "delta_from_weak": {k: difference(metrics[k], metric(weak, k)) for k in METRICS},
                    "mf_delta_from_reference": difference(metrics["motion_fidelity"], metric(source, "motion_fidelity")),
                    "events": events, "event_delta_from_weak": difference(events, weak_event),
                    "weak_event_mean_absolute_offset_frames": weak_event["score"], "timing": rt})
            cohort["methods"][method] = {"n_verified": sum(s["verified"] for s in samples), "cases": samples,
                "metrics": {k: aggregate([s["metrics"][k] for s in samples]) for k in METRICS},
                "delta_from_weak": {k: aggregate([s["delta_from_weak"][k] for s in samples]) for k in METRICS},
                "mf_delta_from_reference": aggregate([s["mf_delta_from_reference"] for s in samples]),
                "mean_absolute_event_offset_frames": aggregate([s["events"] for s in samples]),
                "event_delta_from_weak": aggregate([s["event_delta_from_weak"] for s in samples]),
                "timing": {k: aggregate([s["timing"][k] for s in samples]) for k in ("sampling_seconds", "mean_step_seconds")}}
        output["cohorts"][cohort_name] = cohort
    return output


def load_and_summarize(latest, experiment=E):
    """Hash every small input; fail if the collector changes during the read."""
    inputs = {}
    def read(path):
        raw = path.read_bytes()
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    status = read(latest / "status.json")
    official = read(latest / "official_metrics.json")
    manifest = read(experiment / "metrics/manifest.json")
    frozen = {task: read(experiment / f"timing/event_offset_completion_20261022/{task}/ANNOTATION.json")
              for tasks in COHORTS.values() for task in tasks}
    visuals = {}
    for row in status["jobs"]:
        if row["status"] != "verified":
            continue
        folder = experiment / "showcases/adaptive_strength_20261023/visual" / row["task_id"] / row["method"]
        if (folder / "ANNOTATION.json").is_file():
            visuals[row["job_id"]] = {"annotation": read(folder / "ANNOTATION.json"),
                                      "provenance": read(folder / "PROVENANCE.json")}
    result = summarize(status, official, manifest, frozen, visuals)
    for path, sha in inputs.items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, "input changed during read: " + path)
    result["inputs_sha256"] = inputs
    result["collector_collected_at_unix"] = status.get("collected_at_unix")
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def csv_rows(report):
    for cohort, group in report["cohorts"].items():
        for method, data in group["methods"].items():
            for kind in ("metrics", "delta_from_weak", "timing"):
                for metric_name, stats in data[kind].items():
                    yield {"cohort": cohort, "method": method, "measure": kind, "metric": metric_name,
                           **{k: stats[k] for k in ("status", "n_done", "n_expected", "complete_mean", "partial_mean")}}
            for kind in ("mf_delta_from_reference", "mean_absolute_event_offset_frames", "event_delta_from_weak"):
                stats = data[kind]
                yield {"cohort": cohort, "method": method, "measure": kind, "metric": kind,
                       **{k: stats[k] for k in ("status", "n_done", "n_expected", "complete_mean", "partial_mean")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latest", type=Path, default=HERE / "latest")
    parser.add_argument("--experiment", type=Path, default=E)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = load_and_summarize(args.latest, args.experiment)
    out = args.output or args.latest / "paired_cohorts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    rows = list(csv_rows(report))
    with (out / "summary.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"output": str(out), "cohorts": {k: v["n_expected"] for k, v in report["cohorts"].items()},
                      "input_files": len(report["inputs_sha256"]), "csv_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
