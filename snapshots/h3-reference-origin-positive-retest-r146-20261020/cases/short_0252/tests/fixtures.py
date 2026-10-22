import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

import torch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("alignment", ROOT / "extensions/H3TemporalRouter/alignment.py")
alignment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(alignment)


def model_definitions(canonical=False):
    source = (ROOT / "design/H3_model.py").read_text()
    if hashlib.sha256(source.encode()).hexdigest() != "0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe":
        raise ValueError("bound model source changed")
    if canonical:
        source = source.replace("cursor += max(float(rt), sum(_video_t_spans(vt)))", "cursor += 0.0")
    names = {"_axis_from_sqrt_area", "_frame_grid", "_video_t_spans", "_video_t_grid",
             "_ref_t_span", "_audio_grid", "_video_grid", "PackedLayout", "rope_rotation_table"}
    nodes = [n for n in ast.parse(source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if {n.name for n in nodes} != names:
        raise ValueError("bound model definitions incomplete")
    module = ast.Module(body=nodes, type_ignores=[])
    env = {"torch": torch, "math": math, "FRAME_PER_TOKEN": (1, 4, 4, 4, 4), "FRAME_RESCALE": 5.0 / 3.0}
    exec(compile(module, "bound_H3_definitions", "exec"), env)
    return env


MODEL = model_definitions()
CANONICAL = model_definitions(True)
ACTUAL = json.loads((ROOT / "design/R122_actual_native_router.json").read_text())


def fixture(small=False):
    metadata = copy.deepcopy(ACTUAL["metadata"])
    if small:
        metadata.update(text_len=7, context_shape=[1, 7, 5120])
        metadata["refs"][0].update(latent_t=3, latent_h=4, latent_w=6, latent_shape=[1, 24, 3, 4, 6], frame_rows=6)
    r = metadata["refs"][0]
    args = (metadata["text_len"], r["latent_t"], r["latent_h"], r["latent_w"], 5 if small else 178)
    return metadata, MODEL["PackedLayout"](*args, refs=metadata["refs"]), args


