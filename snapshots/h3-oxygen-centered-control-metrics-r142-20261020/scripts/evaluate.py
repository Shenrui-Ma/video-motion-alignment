"""Validate full98 manual evidence, then compute the R138 descriptive interval metrics."""
import argparse
from common import *


def difference(a, b):
    return [a[0]-b[1], a[1]-b[0]]


def absolute(a):
    return [0 if a[0] <= 0 <= a[1] else min(map(abs, a)), max(map(abs, a))]


def mean_bounds(rows):
    return [sum(r[k] for r in rows)/len(rows) for k in (0, 1)] if rows else None


def midpoint(a):
    return sum(a)/2


def summarize(events, role):
    pairs = [(e[role+"_frames"], e["source_frames"]) for e in events]
    comparable = [(a,b) for a,b in pairs if a is not None]
    errors = [absolute(difference(a,b)) for a,b in comparable]
    phases = []
    for (a,s), (b,t) in zip(pairs, pairs[1:]):
        if a is not None and b is not None:
            phases.append((difference(b,a), difference(t,s)))
    bounds = mean_bounds(errors)
    return dict(comparable_events=len(comparable), comparable_phases=len(phases),
        mean_absolute_event_error_frames_bounds=bounds,
        mean_absolute_event_error_ms_bounds=[x*1000/24 for x in bounds] if bounds else None,
        midpoint_mean_absolute_event_error_frames=sum(abs(midpoint(a)-midpoint(b)) for a,b in comparable)/len(comparable) if comparable else None,
        mean_absolute_phase_duration_error_frames_bounds=mean_bounds([absolute(difference(a,b)) for a,b in phases]),
        midpoint_mean_absolute_phase_duration_error_frames=sum(abs(midpoint(a)-midpoint(b)) for a,b in phases)/len(phases) if phases else None)


def validate_review(review, events):
    require(review["all_valid_frames_inspected"] is True and review["examined_frames"] == list(range(98)),
            "review must explicitly cover every valid frame 0..97")
    task = review["task_acceptance"]
    require(task["status"] in ("PASS_CORE_EDIT", "FAIL_CORE_EDIT", "UNCERTAIN"), "task outcome required")
    keys = ("elderly_woman_identity", "child_cabin_and_mask_retained", "action_sequence_retained",
            "framing_retained", "source_man_identity_copy_observed")
    require(all(type(task[k]) is bool for k in keys) and task["notes"].strip(), "task evidence incomplete")
    if task["status"] == "PASS_CORE_EDIT":
        require(all(task[k] for k in keys[:-1]) and not task[keys[-1]], "inconsistent task pass")
    static=review["static_pose"]
    require(static["frame_range_inclusive"]==[4,19] and static["all_range_frames_inspected"] is True
            and static["evidence_scope"]=="final_video_only","static final-video review required")
    require([r["frame"] for r in static["keyframe_observations"]]==[4,10,19]
            and all(r["source_native_originalauto_centeredauto_notes"].strip() for r in static["keyframe_observations"]),
            "predeclared static keyframe evidence missing")
    relation=static["centeredauto_relative_to_originalauto"]
    require(relation in ("IMPROVED","SIMILAR","WORSE","UNCERTAIN") and static["notes"].strip(),"static pose result")
    require(static["worsened_static_pose_preservation"] is
            (True if relation=="WORSE" else None if relation=="UNCERTAIN" else False),"static pose result inconsistent")
    require([e["id"] for e in review["events"]] == [e["id"] for e in events], "predeclared events differ")
    result = []
    for prior, row in zip(events, review["events"]):
        frames, status = row["centeredauto_frames"], row["centeredauto_status"]
        require(row["notes"].strip(), "event evidence notes required")
        require(status in ("COMPARABLE_VISIBLE", "MISSING", "OCCLUDED", "UNCOMPARABLE"), "event status")
        if status == "COMPARABLE_VISIBLE":
            require(isinstance(frames,list) and len(frames)==2 and all(type(v)is int for v in frames)
                    and 0 <= frames[0] <= frames[1] < 98, "event interval outside full98")
        else:
            require(frames is None, "missing/uncomparable event must remain null")
        result.append({**prior, **row})
    require(review["conclusion"].strip(), "review conclusion required")
    return result


def evaluate(path):
    actual()
    review = read(path)
    require(review["collection"] == bound(ROOT/"incoming/actual/COLLECTION.json"), "review belongs to other output")
    ledger_path = ROOT/"showcase/full98/FRAME_LEDGER.json"
    ledger = read(ledger_path)
    require(ledger["collection"] == review["collection"], "frame ledger belongs to other output")
    require([i for row in ledger["pages"] for i in row["physical_frame_indices"]] == list(range(98)), "full98 page coverage")
    for row in ledger["pages"]:
        require(sha(ledger_path.parent/row["file"]) == row["sha256"], "review page changed")
    events = validate_review(review, read(ROOT/"configs/EVALUATION_PLAN.json")["events"])
    result = dict(schema="r142-final-video-evaluation-v1", status="VISUAL_REVIEWED_MF_SEPARATE",
        review=bound(path), collection=review["collection"], task_acceptance=review["task_acceptance"],
        static_pose=review["static_pose"],
        centered_guard_status="Additional hypothesis; final static-pose preservation and motion timing assessed together.",
        events=events, timing_summaries={role:summarize(events,role) for role in ("native","fixed","originalauto","centeredauto")},
        event_semantics=read(ROOT/"configs/EVALUATION_PLAN.json")["third_event_semantics"],
        frames=list(range(98)), fps=24, same_source_increment=0, conclusion=review["conclusion"])
    save(ROOT/"audit/FINAL_VIDEO_EVALUATION.json",result)
    return bound(ROOT/"audit/FINAL_VIDEO_EVALUATION.json")


if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--review",type=Path,required=True);a=p.parse_args()
    print(json.dumps(evaluate(a.review)))
