"""Single R122-source aligned-clock comparison, with its original AV noise."""
import copy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("long_0039",)
RUN_ID = "r129_long_0039_seed2026101701_aligned"


def read(path): return json.loads(Path(path).read_text())
def require(ok, message):
    if not ok: raise ValueError(message)
def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""): h.update(block)
    return h.hexdigest()


def geometry(case): return {"width": 1312, "height": 736, "frames": 107, "fps": 24}
def latent_shapes(case): return {"video": (1, 24, 32, 46, 82), "audio": (1, 32, 2, 178)}
def routing_layout(case):
    return {"latent_interval_half_open": [0, 32], "position_bin_coverage_inclusive": [0, 106],
            "pixel_interval_inclusive": [0, 105], "total_latent_bins": 32,
            "pure_pad_bins": [], "frame_rows": 943}


def expected_graph(root):
    root = Path(root)
    graph = copy.deepcopy(read(root / "design/R122_native_graph.json"))
    remote = read(root / "configs/runtime.json")["remote_root"]
    old = "/home/researcher/h3_runs/timing_ive_generic_retention_r122_20261020"
    graph = json.loads(json.dumps(graph).replace(old, remote).replace("r122_", "r129_").replace(
        "r129_long_0039_seed2026101701_native", RUN_ID))
    graph["50"]["class_type"] = "H3AlignedMediaClock"
    graph["50"]["inputs"]["enabled"] = True
    return graph


def registry(root=ROOT):
    root = Path(root)
    science = read(root / "configs/scientific_contract.json")
    order = [RUN_ID]
    require(science["case_order"] == order and science["source_ids"] == list(SOURCES) and
            science["arms"] == ["aligned"] and len(science["cases"]) == 1, "single aligned run changed")
    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")
    case = science["cases"][0]
    require((case["run_id"], case["source_id"], case["arm"], case["seed"]) ==
            (RUN_ID, "long_0039", "aligned", 2026101701), "run identity changed")
    require(case["geometry"] == geometry(case) and case["valid_frame_count"] == 106 and
            case["evaluation_crop_xywh"] == [16, 8, 1280, 720] and
            case["evaluation_indices"] == list(range(106)), "timebase changed")
    parent = read(root / "design/R122_native_graph.json")
    require(case["prompt"] == parent["5"]["inputs"]["prompt"] ==
            (root / "configs/prompts/long_0039.txt").read_text(), "R122 prompt changed")
    require(sha(root / "configs/prompts/long_0039.txt") == case["prompt_sha256"], "prompt digest changed")
    require(sha(root / case["parent_graph"]) == case["parent_graph_sha256"], "parent graph changed")
    require(science["evaluation_plan_sha256"] == sha(root / "design/R129_EVALUATION_PLAN.json"), "evaluation plan changed")
    require(science["parent_noise_sha256"] == "149c638af54913020b9c3f49c5625aba8a44efa3e326738834f6be9e87a1f943", "R122 actual noise changed")
    graph_path = root / "configs/graphs" / (RUN_ID + ".json")
    require(read(graph_path) == expected_graph(root), "graph differs outside aligned RoPE/admin changes")
    require(science["alignment"] == {"enabled": True, "target_streams": ["audio", "video"],
            "all_steps": list(range(20)), "all_blocks": list(range(50)), "router_mode": "native",
            "first_six_prediction_equality_required": False}, "alignment scope changed")
    return {RUN_ID: {"case": case, "source_id": "long_0039", "seed": 2026101701,
                    "arm": "aligned", "graph_sha256": sha(graph_path)}}, order


def validate_job(run, root=ROOT):
    root = Path(root)
    jobs, _ = registry(root)
    require(run in jobs, "unknown run")
    for name, digest in read(root / "configs/input_hashes.json").items():
        require(Path(name).name == name, "unsafe input name")
        path = root / "inputs" / name
        require(not path.is_symlink() and sha(path) == digest, "source bytes changed")
    return jobs[run]


def audit_dir(value):
    path = Path(value)
    require(path == Path(read(ROOT / "configs/runtime.json")["remote_root"]) / "audit", "audit directory differs")
    return path


def prepare_loader_inputs(run, root=ROOT):
    root = Path(root)
    row = validate_job(run, root)
    target = root / "input" / row["case"]["video"]
    target.parent.mkdir(exist_ok=True)
    if not target.exists(): os.link(root / "inputs" / row["case"]["video"], target)
    require(not target.is_symlink() and sha(target) == row["case"]["video_sha256"], "loader video changed")
    science = read(root / "configs/scientific_contract.json")
    source = Path(science["parent_noise_file"])
    require(sha(source) == science["parent_noise_sha256"], "parent AV noise bytes changed")
    noise = root / "audit/r129_long_0039_seed2026101701_noise.pt"
    if not noise.exists(): os.link(source, noise)
    require(not noise.is_symlink() and sha(noise) == science["parent_noise_sha256"], "noise cache changed")
    return row


def validate_router(mode, alpha, radius, time_offset, start_frame, end_frame, block_start,
                    block_end, step_start, step_end, run_id, audit_path):
    validate_job(run_id)
    require(Path(audit_path) == Path(read(ROOT / "configs/runtime.json")["remote_root"]) / "audit/router", "router path differs")
    require((mode, alpha, radius, time_offset, start_frame, end_frame, block_start, block_end,
             step_start, step_end) == ("native", 1.0, 0, 0, 0, 105, 0, 50, 6, 15), "Native attention configuration changed")
