"""Describe fixed event intervals with shared-source comparisons; no new labels."""
import argparse
import itertools
from common import ROOT, read, bound, write, require, case_and_schedule


def values(interval):
    require(len(interval) == 2 and all(type(v) is int for v in interval) and
            0 <= interval[0] <= interval[1], "Invalid inclusive interval")
    return range(interval[0], interval[1] + 1)


def extrema(items):
    items = list(items)
    return [min(items), max(items)]


def event_stats(source, fixed, new, fps):
    if new is None:
        return None
    s, f, n = list(values(source)), list(values(fixed)), list(values(new))
    return {"absolute_error_frames": extrema(abs(a - b) for a in n for b in s),
            "paired_change_vs_fixed_ms": extrema((abs(a - b) - abs(c - b)) * 1000 / fps
                                                 for b, c, a in itertools.product(s, f, n))}


def phase_stats(first, second, arm, fps):
    intervals = [e.get(role) for e in (first, second) for role in ("source", "fixed", arm)]
    if any(v is None for v in intervals):
        return None
    s0, f0, n0, s1, f1, n1 = [list(values(v)) for v in intervals]
    require(max(s0) <= min(s1), "Source event order differs")
    sd = {b - a for a in s0 for b in s1}
    fd = {b - a for a in f0 for b in f1}
    nd = {b - a for a in n0 for b in n1}
    return {"source_duration_frames": extrema(sd), "fixed_duration_frames": extrema(fd),
            "new_duration_frames": extrema(nd),
            "new_absolute_duration_error_ms": extrema(abs(n - s) * 1000 / fps for n in nd for s in sd),
            "paired_duration_error_change_ms": extrema((abs(n - s) - abs(f - s)) * 1000 / fps
                                                       for s, f, n in itertools.product(sd, fd, nd))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--schedule", required=True)
    a = p.parse_args()
    _, case, _ = case_and_schedule(a.case, a.schedule)
    folder = ROOT / "review" / a.case / a.schedule
    review = read(folder / "REVIEW.json")
    require(review.get("review_completed") is True, "Full effective-frame review must be complete")
    events = review["events"]
    require([e["id"] for e in events] == [e["id"] for e in case["events"]], "Frozen event list differs")
    for old, new in zip(case["events"], events):
        require(all(old[k] == new[k] for k in ("id", "source", "native", "fixed")),
                "Historical event intervals must not change")
    fps = case["geometry"]["fps"]
    result = {"schema": "r149-event-interval-summary-v1", "review": bound(folder / "REVIEW.json"),
        "source_id": a.case, "schedule": a.schedule, "fps": fps,
        "events": [{"id": e["id"], "new_interval": e[a.schedule],
                    "statistics": event_stats(e["source"], e["fixed"], e[a.schedule], fps)} for e in events],
        "phases": [{"from": x["id"], "to": y["id"], "statistics": phase_stats(x, y, a.schedule, fps)}
                   for x, y in zip(events, events[1:])],
        "meaning": "Descriptive annotation interval bounds; each paired difference shares source time(s)."}
    write(folder / "EVENT_SUMMARY.json", result)
    print(str(folder / "EVENT_SUMMARY.json"))


if __name__ == "__main__":
    main()
