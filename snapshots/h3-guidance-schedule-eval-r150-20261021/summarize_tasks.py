"""Descriptive counts from completed reviews; no new motion measurements."""
from statistics import mean

from common import ROOT, read, write, bound, require

OLD = ROOT.with_name("h3-guidance-schedule-eval-r149-20261020")
ARMS = ("early", "late", "split", "global_weak")
PRESERVATION = {"short_0085", "short_0274"}
MISSING_ACTION = {"firefly06"}


def interval_error(events, role):
    if not events or any(not isinstance(e.get(role), list) or
                         not isinstance(e.get("source"), list) for e in events):
        return None
    return mean(abs(sum(e[role]) / 2 - sum(e["source"]) / 2) for e in events)


def classify(case, arm, review):
    sid = case["source_id"]
    result = {"core_edit_passed": review["task_verdict"] == "PASS_CORE_EDIT"}
    events = review["events"]
    group = case.get("_initial_group") or (
        "preservation" if sid in PRESERVATION else
        "missing_action" if sid in MISSING_ACTION else "timing_offset")
    require(group != "pending_matched_native", "Matched Native must be classified first")
    if group == "preservation":
        observed = review.get("preservation_observations", [])
        require([x["id"] for x in observed] == [e["id"] for e in case["events"]],
                "Preservation observations must cover every frozen phase")
        result.update(group="preservation",
                      preserved=result["core_edit_passed"] and all(
                          x["new_phase_present_in_same_range"] is True for x in observed),
                      exact_lag_measured=False)
    elif group == "missing_action":
        first = next(e for e in events if e["id"] == "early_eye_insert")
        result.update(group="missing_action",
                      first_short_action_present=isinstance(first.get(arm), list),
                      missing_action_restored=result["core_edit_passed"] and
                      first.get("native") is None and isinstance(first.get(arm), list))
    else:
        if sid == "05_real_megumi_v":
            windows = review["historical_window_diagnostics"]["windows"]
            primary = next(x for x in windows if x["window"] == [50, 65])
            original = primary.get("native", {}).get("0.3")
            value = (primary.get(arm) or {}).get("0.3")
            native_error = abs(original) if original is not None else None
            new_error = abs(value) if value is not None else None
            metric = "absolute_arm_direction_lag_at_frozen_50_65_confidence_0.3"
        else:
            native_error, new_error = interval_error(events, "native"), interval_error(events, arm)
            metric = "mean_absolute_event_interval_midpoint_difference"
        result.update(group="timing_offset", metric=metric, units="frames",
                      native_error=native_error, new_error=new_error,
                      all_frozen_measurements_available=native_error is not None and new_error is not None,
                      error_reduced_with_core_edit=result["core_edit_passed"] and
                      native_error is not None and new_error is not None and new_error < native_error)
    return result


def collect():
    cases = [(OLD, c) for c in read(OLD / "EVALUATION_MANIFEST.json")["cases"]]
    cases += [(ROOT, c) for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]]
    require(len(cases) == 10, "Ten actual tasks required")
    group_totals = dict(timing_offset=0, preservation=0, missing_action=0,
                        pending_matched_native=0)
    grouping_evidence = []
    for base, case in cases:
        sid = case["source_id"]
        group = ("preservation" if sid in PRESERVATION else
                 "missing_action" if sid in MISSING_ACTION else "timing_offset")
        if sid == "sam07":
            native_path = base / "review" / sid / "native/REVIEW.json"
            group = "pending_matched_native"
            if native_path.exists() and read(native_path).get("review_completed"):
                native = read(native_path)
                group = native.get("initial_timing_category")
                require(group in {"timing_offset", "preservation"},
                        "Sam07 requires an explicit category from its actual matched Native")
                presentation = read(native_path.with_name("PRESENTATION.json"))
                require(native["actual_video"] == presentation["new_video"],
                        "Sam07 grouping uses a different Native video")
                grouping_evidence.append(bound(native_path))
        case["_initial_group"] = group
        group_totals[group] += 1
    rows, counts = [], {}
    for arm in ARMS:
        counts[arm] = dict(reviewed=0, core_edit_passed=0, timing_offset_reviewed=0,
                           error_reduced_with_core_edit=0, preservation_reviewed=0,
                           preserved=0, missing_action_reviewed=0, missing_action_restored=0)
        for base, case in cases:
            path = base / "review" / case["source_id"] / arm / "REVIEW.json"
            if not path.exists() or not read(path).get("review_completed"):
                continue
            review = read(path)
            presentation = read(path.with_name("PRESENTATION.json"))
            require(review["actual_video"] == presentation["new_video"], "Review media differs")
            assessment = classify(case, arm, review)
            row = dict(source_id=case["source_id"], role=arm, review=bound(path),
                       presentation=bound(path.with_name("PRESENTATION.json")), **assessment)
            rows.append(row)
            count = counts[arm]
            count["reviewed"] += 1
            count["core_edit_passed"] += int(assessment["core_edit_passed"])
            group = assessment["group"]
            count[group + "_reviewed"] += 1
            key = {"timing_offset": "error_reduced_with_core_edit",
                   "preservation": "preserved", "missing_action": "missing_action_restored"}[group]
            count[key] += int(assessment[key])
    result = {
        "schema": "r150-descriptive-task-outcomes-v1", "tasks": 10, "independent_sources": 9,
        "group_totals": group_totals, "matched_native_grouping_evidence": grouping_evidence,
        "counts": counts, "rows": rows,
        "meaning": "Counts separate core editing, reduced existing timing error conditional on core editing, "
                   "preservation of initially near-synchronous phases, and recovery of the missing short action.",
        "timing_rule": "Compare existing interval-midpoint mean absolute error with matched Native; "
                       "Sam05 uses the frozen arm-direction lag. Require every frozen measurement. "
                       "Missing actions are never assigned zero error. No MF averaging or new measurement.",
        "status": "complete" if len(rows) == 40 else "partial"}
    write(ROOT / "audit/TASK_OUTCOME_SUMMARY.json", result)
    return result


def main():
    print(collect()["counts"])


if __name__ == "__main__":
    main()
