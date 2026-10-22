"""CPU candidate: retain qualifying evidence before representative selection."""
import importlib.util
from pathlib import Path

path = Path(__file__).parent / "frozen" / "automatic_window_policy.py"
spec = importlib.util.spec_from_file_location("frozen_signed_policy", path)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)


def rank(proposal):
    a, b = proposal["window"]
    return (-proposal["absolute_gain"], b - a + 1, a, proposal["feature"])


class Policy:
    def __init__(self, threshold=.5):
        self.threshold = threshold
        self.previous = []
        self.last_index = -1

    def update(self, index, rows):
        if index != self.last_index + 1:
            raise ValueError("observations must cover consecutive indices beginning at0")
        groups = baseline.components(rows, self.threshold)
        selected = []
        qualifying = []
        for group in groups:
            current = group["members"]
            qualifying.extend(current)
            continuing = [r for r in current
                          if any(baseline.persistent(r, p) for p in self.previous)]
            if continuing:
                selected.append(min(continuing, key=rank))
        result = {
            "index": index,
            "groups": groups,
            "selected": selected,
            "physical_intervals": [r["window"] for r in selected],
            "active": bool(selected),
            "reason": "persistent_signed_error" if selected else
                      ("awaiting_persistence" if qualifying else
                       "no_qualifying_signed_proposal"),
        }
        self.previous = qualifying
        self.last_index = index
        return result
