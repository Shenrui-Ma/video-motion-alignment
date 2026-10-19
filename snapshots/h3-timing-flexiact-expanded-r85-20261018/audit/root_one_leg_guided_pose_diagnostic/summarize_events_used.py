"""Posthoc arm-event measurements; this script does not control generation."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
report = {
    "scope": "Descriptive pose events awaiting confirmation in rendered frames",
    "source_cadence": "Original 8fps frames repeated three times at 24fps; source precision 0.125s",
    "valid_frames": 147,
    "confidence_thresholds": [0.3, 0.5],
    "persistence_output_frames": 6,
    "events": {
        "wrists_above_nose": "Both wrist y coordinates are above nose y",
        "upper_arms_up": "Both shoulder-to-elbow upward unit-vector components exceed 0.7",
    },
    "videos": [],
}
for path in sorted((ROOT / "poses").glob("*.pose.json")):
    data = json.loads(path.read_text())
    assert len(data["frames"]) == 147
    assert data["video"]["fps"] == 24
    rows = []
    events = {}
    for threshold in report["confidence_thresholds"]:
        values = []
        for index, frame in enumerate(data["frames"]):
            assert frame["frame"] == index and abs(frame["time_s"] - index / 24) < 1e-8
            chosen = frame["selected_person"]
            raised = vertical = False
            if chosen is not None:
                person = frame["persons"][chosen]
                xy, scores = person["coco17_xy"], person["coco17_score"]
                valid = min(scores[j] for j in [0, 5, 6, 7, 8, 9, 10]) >= threshold
                upward = []
                for shoulder, elbow in [(5, 7), (6, 8)]:
                    dx = xy[elbow][0] - xy[shoulder][0]
                    dy = xy[elbow][1] - xy[shoulder][1]
                    upward.append(-dy / max(math.hypot(dx, dy), 1e-9))
                raised = valid and max(xy[9][1], xy[10][1]) < xy[0][1]
                vertical = valid and min(upward) > 0.7
            values.append((raised, vertical))
            rows.append([threshold, index, index / 24, int(raised), int(vertical)])
        events[str(threshold)] = {}
        for column, name in enumerate(report["events"]):
            start = next((i for i in range(len(values) - 5)
                          if all(v[column] for v in values[i:i + 6])), None)
            events[str(threshold)][name] = {
                "first_sustained_frame": start,
                "time_s": start / 24 if start is not None else None,
                "status": "detected" if start is not None else "not_detected_within_valid_clip",
            }
    table = ROOT / (path.stem + ".events.csv")
    with table.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["confidence", "frame", "time_s", "wrists_above_nose", "upper_arms_up"])
        writer.writerows(rows)
    report["videos"].append({
        "pose_file": str(path),
        "pose_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "video": data["video"],
        "events": events,
        "table": str(table),
    })
(ROOT / "POSE_EVENT_SUMMARY.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps([{ "file": Path(v["pose_file"]).name, "events": v["events"] }
                  for v in report["videos"]], ensure_ascii=False))
