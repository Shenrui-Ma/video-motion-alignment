"""Summarize frozen visual-event intervals without hiding early/late errors."""
import argparse
import json
from pathlib import Path

from prepare import ROOT, bind, read


def compare_interval(reference, generated):
    if generated is None:
        return {"status": "absent_or_not_comparable"}
    if len(reference) != 2 or len(generated) != 2:
        raise ValueError("Intervals require inclusive start/end frames.")
    r0, r1 = reference
    g0, g1 = generated
    if r0 > r1 or g0 > g1:
        raise ValueError("Reversed event interval.")
    shift = (g0 + g1 - r0 - r1) / 2
    return {
        "status": "measured",
        "signed_midpoint_error_frames": shift,
        "absolute_midpoint_error_frames": abs(shift),
        "signed_error_interval_frames": [g0 - r1, g1 - r0],
        "intervals_overlap": max(r0, g0) <= min(r1, g1),
    }


def summarize(case_id):
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == case_id)
    annotations_path = ROOT / "reviews" / case_id / "EVENT_ANNOTATIONS.json"
    annotations = read(annotations_path)
    expected_ids = [event["id"] for event in case["events"]]
    if not expected_ids:
        raise ValueError("This case uses the frozen pose evaluation, not discrete-event intervals.")
    if [event["id"] for event in annotations["events"]] != expected_ids:
        raise ValueError("Events differ from the frozen source definitions.")
    forward_record = case["forward_events"]
    if bind(Path(forward_record["file"]))["sha256"] != forward_record["sha256"]:
        raise ValueError("Frozen forward annotation changed.")
    forward = {event["id"]: event["new_interval"]
               for event in read(Path(forward_record["file"]))["events"]}
    rows = []
    for source_event, annotation in zip(case["events"], annotations["events"]):
        if annotation["source"] != source_event["source"]:
            raise ValueError("Source event interval changed.")
        if (annotation["native"] != source_event["native"] or
                annotation["forward"] != forward[source_event["id"]]):
            raise ValueError("Historical control annotation changed.")
        row = {"id": source_event["id"], "source": source_event["source"], "conditions": {}}
        for role in ("native", "forward", "reverse", "combined"):
            interval = annotation[role]
            if interval is not None and not 0 <= interval[0] <= interval[1] < case["geometry"]["valid_frames"]:
                raise ValueError(f"Event outside valid video frames: {role}")
            row["conditions"][role] = {"interval": interval,
                                       **compare_interval(source_event["source"], interval)}
        rows.append(row)
    aggregates = {}
    for role in ("native", "forward", "reverse", "combined"):
        measured = [row["conditions"][role] for row in rows
                    if row["conditions"][role]["status"] == "measured"]
        aggregates[role] = {
            "measured_events": len(measured), "total_events": len(rows),
            "mean_absolute_midpoint_error_frames": (
                sum(m["absolute_midpoint_error_frames"] for m in measured) / len(measured)
                if measured else None),
            "overlapping_events": sum(m["intervals_overlap"] for m in measured),
        }
    complete = all(a["measured_events"] == a["total_events"] for a in aggregates.values())
    interaction = None
    if complete:
        e = {role: val["mean_absolute_midpoint_error_frames"]
             for role, val in aggregates.items()}
        interaction = e["combined"] - e["forward"] - e["reverse"] + e["native"]
    destination = ROOT / "reviews" / case_id / "EVENT_METRICS.json"
    destination.write_text(json.dumps({
        "source_id": case_id, "annotation": bind(annotations_path),
        "fps": case["geometry"]["fps"], "events": rows, "aggregates": aggregates,
        "absolute_error_factorial_interaction": interaction,
        "interpretation": "Positive midpoint error denotes delay. Intervals preserve visual annotation uncertainty.",
    }, ensure_ascii=False, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    summarize(parser.parse_args().case)
