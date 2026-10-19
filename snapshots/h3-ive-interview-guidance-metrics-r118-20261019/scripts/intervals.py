"""Deterministic bounds from visual event intervals, not statistical intervals."""
import math


def interval(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("An event must have two finite ordered endpoints")
    lo, hi = value
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value) or lo > hi:
        raise ValueError("Invalid event interval")
    return lo, hi


def distance(x, span):
    lo, hi = span
    return max(lo - x, 0, x - hi)


def farthest(x, span):
    return max(abs(x - span[0]), abs(x - span[1]))


def compare(source, ordinary, alternative):
    """Exact box bounds for |alternative-source|-|ordinary-source|.

    Both errors share the same uncertain source event time. Evaluating the
    breakpoints of these piecewise linear functions avoids treating source
    uncertainty as two independent measurements.
    """
    s, n, g = map(interval, (source, ordinary, alternative))
    points = set(s)
    for x in (*n, *g, sum(n) / 2, sum(g) / 2):
        if s[0] <= x <= s[1]:
            points.add(x)
    lower = min(distance(x, g) - farthest(x, n) for x in points)
    upper = max(farthest(x, g) - distance(x, n) for x in points)
    if upper < 0:
        verdict = "strictly_smaller_within_annotated_intervals"
    elif lower > 0:
        verdict = "strictly_larger_within_annotated_intervals"
    elif upper == 0 and lower < 0:
        verdict = "non_increasing_within_annotated_intervals"
    elif n == g:
        verdict = "identical_visual_brackets_no_resolved_difference"
    else:
        verdict = "ordering_unresolved_within_annotated_intervals"
    return {
        "ordinary_signed_delay_frames": [n[0] - s[1], n[1] - s[0]],
        "alternative_signed_delay_frames": [g[0] - s[1], g[1] - s[0]],
        "absolute_error_change_frames": [lower, upper],
        "verdict": verdict,
    }
