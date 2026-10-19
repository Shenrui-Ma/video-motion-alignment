"""Frozen coarse lag observer, with no diagnostic script's environment effects."""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE_SHA = "c84cca34903c9476adc36fa2af0c9e3507b736031efac5bf361187a2c63de075"
PROTOCOL_SHA = "e84af137304d6b950e3bba078a96d1631c665a7fdcce84ef6c93d7e9551f4a16"
_ROOT = Path(__file__).resolve().parent
_source = (_ROOT / "observer_frozen.py").read_bytes()
_protocol = (_ROOT / "observer_protocol.json").read_bytes()
if hashlib.sha256(_source).hexdigest() != SOURCE_SHA:
    raise RuntimeError("frozen observer source changed")
if hashlib.sha256(_protocol).hexdigest() != PROTOCOL_SHA:
    raise RuntimeError("frozen observer protocol changed")

# The source script sets CUDA_VISIBLE_DEVICES at module scope. Never import it.
# Compile only these unmodified pure functions; no main, imports or assignments.
_names = {"geometry", "phase_mean", "signal", "interp", "scan"}
_functions = [n for n in ast.parse(_source).body
              if isinstance(n, ast.FunctionDef) and n.name in _names]
if {n.name for n in _functions} != _names or len(_functions) != len(_names):
    raise RuntimeError("frozen observer function contract changed")
_namespace = {"np": np}
exec(compile(ast.Module(body=_functions, type_ignores=[]),
             "<frozen gap5 observer functions>", "exec"), _namespace)
signal, scan = _namespace["signal"], _namespace["scan"]
REJECT_RULES = json.loads(_protocol)["reject_rules"]
WINDOW = (50, 65)
VIDEO_SHAPE = (1, 24, 42, 36, 64)


def _array(video):
    if tuple(video.shape) != VIDEO_SHAPE or video.device.type != "cpu":
        raise ValueError("observer requires CPU full-frame H3 reference geometry")
    # Explicit copy makes the analysis arrays independent of all sampler tensors.
    value = video[0].permute(1, 0, 2, 3).reshape(42, -1).numpy().astype(np.float64)
    if not np.isfinite(value).all():
        raise ValueError("nonfinite observer video")
    return value


class FrozenGap5Observer:
    def __init__(self, reference):
        self.reference_signal = signal(_array(reference), "same_phase_gap5")

    def __call__(self, video):
        target = signal(_array(video), "same_phase_gap5")
        result = scan(self.reference_signal, target, WINDOW, REJECT_RULES)
        if len(result["curve"]) != 49 or [r["lag_frames"] for r in result["curve"]] != list(range(-24, 25)):
            raise ValueError("frozen lag search contract changed")
        return result


def next_decision(observation, previous_active):
    """Discrete exploratory thresholds; unknown never means successfully aligned."""
    if not observation["accepted"]:
        return False, "OFF_UNKNOWN"
    lag = observation["best"]["lag_frames"]
    if type(lag) is not int or not -24 <= lag <= 24:
        raise ValueError("accepted lag must be an integer in the frozen search grid")
    if lag >= 4:
        return True, "ON_DELAYED"
    if -2 <= lag <= 2:
        return False, "OFF_ALIGNED"
    if lag == 3:
        return bool(previous_active), "HOLD_LAG3"
    return False, "OFF_ADVANCED"
