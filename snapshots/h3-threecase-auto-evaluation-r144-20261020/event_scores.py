"""Summarize visible event intervals; unavailable events remain explicitly unscored."""
import json
from pathlib import Path


def interval(value):
    frames = value.get("frames") if isinstance(value, dict) else value
    if frames is None or len(frames) != 2:
        return None
    lo, hi = map(int, frames)
    if lo < 0 or hi < lo:
        raise ValueError("Invalid event interval")
    return lo, hi


def score(events, role, fps):
    rows = []
    for event in events:
        source = interval(event.get("source", event.get("source_frames")))
        edited = interval(event.get(role, event.get(role + "_frames")))
        if source is None or edited is None:
            rows.append({"event": event.get("id", event["name"]), "status": "unscored"})
            continue
        lo, hi = edited[0] - source[1], edited[1] - source[0]
        midpoint = sum(edited) / 2 - sum(source) / 2
        bounds = [0 if lo <= 0 <= hi else min(abs(lo), abs(hi)), max(abs(lo), abs(hi))]
        rows.append({"event": event.get("id", event["name"]), "status": "scored", "source_frames": source,
                     "edited_frames": edited, "delay_midpoint_frames": midpoint,
                     "delay_interval_frames": [lo, hi], "absolute_error_interval_frames": bounds})
    good = [r for r in rows if r["status"] == "scored"]
    n = len(good)
    mean = sum(abs(r["delay_midpoint_frames"]) for r in good) / n if n else None
    return {"role": role, "total_events": len(rows), "scored_events": n,
            "mean_absolute_event_error_midpoint_frames": mean,
            "mean_absolute_event_error_midpoint_ms": mean * 1000 / fps if mean is not None else None,
            "mean_absolute_event_error_interval_frames": [sum(r["absolute_error_interval_frames"][i] for r in good) / n for i in (0, 1)] if n else None,
            "interval_meaning": "由逐帧人工标注范围传播得到的误差范围", "events": rows}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    plan = json.loads((root / "EVALUATION_PLAN.json").read_text())
    result = {c["source_id"]: {role: score(c["events_selected_before_automatic_output"]["events"], role, c["geometry"]["fps"])
                               for role in ("native", "forced")} for c in plan["cases"]}
    (root / "EXISTING_EVENT_SCORES.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({source: {role: r["mean_absolute_event_error_midpoint_frames"] for role, r in roles.items()} for source, roles in result.items()}))
