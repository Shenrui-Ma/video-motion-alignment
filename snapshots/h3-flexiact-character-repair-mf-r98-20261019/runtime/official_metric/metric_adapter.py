"""Run the pinned FlexiAct metric functions without optional visualization imports.

The original function bodies are loaded unchanged. Configuration and provenance
are supplied by our harness; this is an author-code metric adapter, not the
original command-line entry point.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_functions(relative_path, names, namespace):
    path = ROOT / relative_path
    record = json.loads((ROOT / "METRIC_FUNCTIONS.json").read_text())[relative_path]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError(f"Pinned source changed: {relative_path}")
    source = raw.decode()
    selected = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            segment = ast.get_source_segment(source, node)
            if hashlib.sha256(segment.encode()).hexdigest() != record["functions"][node.name]:
                raise ValueError(f"Pinned function changed: {node.name}")
            selected.append(node)
    if {node.name for node in selected} != set(names):
        raise ValueError("Requested function set is incomplete")
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return {name: namespace[name] for name in names}


def scoring_functions():
    import torch
    return load_functions("vendor/motion_fidelity.py", ["get_similarity_matrix", "get_score"], {"torch": torch})


def tracking_functions():
    import cv2
    import numpy as np
    import torch
    from einops import rearrange
    namespace = {"cv2": cv2, "np": np, "torch": torch, "rearrange": rearrange}
    load_functions("vendor/co-tracker/cotracker/utils/visualizer.py", ["read_video_from_path"], namespace)
    return load_functions("vendor/motion_fidelity.py", ["get_tracklets"], namespace)


def score_tracks(edit_tracks, reference_tracks):
    import torch
    if edit_tracks.ndim != 3 or reference_tracks.ndim != 3:
        raise ValueError("Expected [point, frame, xy] tracklets")
    if edit_tracks.shape != reference_tracks.shape or edit_tracks.shape[-1] != 2:
        raise ValueError("Official unmasked evaluation requires equal tracklet shapes")
    functions = scoring_functions()
    matrix = functions["get_similarity_matrix"](edit_tracks, reference_tracks)
    score = functions["get_score"](matrix)["average_score"]
    # Preserve the author's undefined zero-motion behavior. Report missingness
    # instead of replacing NaN, adding epsilon, or silently dropping tracks.
    finite = bool(torch.isfinite(torch.tensor(score)))
    result = {
        "metric": "FlexiAct author-code Motion Fidelity via adapter",
        "score": score if finite else None,
        "status": "finite" if finite else "undefined_nonfinite_official_score",
        "points": int(edit_tracks.shape[0]),
        "frames": int(edit_tracks.shape[1]),
        "nonfinite_similarity_entries": int((~torch.isfinite(matrix)).sum()),
        "edit_zero_displacements": int(((edit_tracks[:, 1:] - edit_tracks[:, :-1]).norm(dim=-1) == 0).sum()),
        "reference_zero_displacements": int(((reference_tracks[:, 1:] - reference_tracks[:, :-1]).norm(dim=-1) == 0).sum()),
    }
    return result, matrix
