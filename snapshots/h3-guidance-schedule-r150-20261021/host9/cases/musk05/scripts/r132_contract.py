"""R149 fixed same-bin schedule-only contract. Kept under the legacy import name."""
import copy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEDULES = {'fixed': [6, 7, 8, 9, 10, 11, 12, 13, 14], 'early': [0, 1, 2, 3, 4, 5, 6, 7, 8], 'late': [11, 12, 13, 14, 15, 16, 17, 18, 19], 'split': [0, 1, 2, 3, 15, 16, 17, 18, 19], 'global_weak': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]}


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def science(root=ROOT):
    return read(Path(root) / "configs/scientific_contract.json")


RUN_ID = science()["case_order"][0]
SOURCES = tuple(science()["source_ids"])


def geometry(case):
    return case["geometry"]


def latent_shapes(case):
    return dict(zip(("video", "audio"), map(tuple, case["target_latent_shapes"])))


def routing_layout(case):
    total = case["target_latent_shapes"][0][2]
    spans = [(1, 4, 4, 4, 4)[i % 5] for i in range(total)]
    start, end = case["physical_query_window"]
    selected = [i for i in range(total) if sum(spans[:i]) <= end and sum(spans[:i+1]) > start]
    lo, hi = selected[0], selected[-1] + 1
    return {"latent_interval_half_open": [lo, hi],
            "position_bin_coverage_inclusive": [sum(spans[:lo]), sum(spans[:hi])-1],
            "pixel_interval_inclusive": [start, end], "total_latent_bins": total,
            "frame_rows": 943}


def expected_graph(run, root=ROOT):
    root = Path(root)
    s = science(root)
    c = next(c for c in s["cases"] if c["run_id"] == run)
    remote = read(root / "configs/runtime.json")["remote_root"]
    g = copy.deepcopy(read(root / "design/parent_cached_graph.json"))
    g["5"]["inputs"].update(cache_manifest=remote + "/configs/CONDITION_CACHE.json",
                            audit_dir=remote + "/audit", run_id=run)
    g["6"]["inputs"].update(audit_dir=remote + "/audit", run_id=run, pair_id=s["noise_pair_id"])
    g["50"]["class_type"] = "H3FixedSchedule"
    g["50"]["inputs"].update(enabled=True, mode="mass_preserve", alpha=c["alpha"],
        radius=0, time_offset=0, start_frame=c["physical_query_window"][0],
        end_frame=c["physical_query_window"][1], block_start=0, block_end=50,
        step_start=0, step_end=20, run_id=run, audit_dir=remote + "/audit/router",
        schedule=c["arm"])
    g["51"]["inputs"].update(source_audit_dir=remote + "/audit",
        source_run_id=s["historical_shared_run"], run_id=run)
    g["52"]["inputs"].update(run_id=run, output_dir=remote + "/audit/x0")
    g["14"]["inputs"]["filename_prefix"] = run
    return g


def registry(root=ROOT):
    root = Path(root)
    s = science(root)
    order = [c["run_id"] for c in s["cases"]]
    require(len(order) == len(set(order)) == len(SCHEDULES) and s["case_order"] == order and
            [c["arm"] for c in s["cases"]] == list(SCHEDULES), "registered ordered unique arms required")
    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")
    require(s["online_observer"] is False and s["NFE_per_job"] == 20 and
            s["phase_displacement"] == 0 and s["arms"] == list(SCHEDULES), "schedule-only scope changed")
    require(sha(root / "design/parent_cached_graph.json") == s["parent_cached_graph_sha256"],
            "frozen R148 cached graph changed")
    require(sha(root / "design/conditioning.json") == s["conditioning_sha256"], "condition changed")
    cache = read(root / "configs/CONDITION_CACHE.json")
    jobs = {}
    for c in s["cases"]:
        require(c["steps_zero_based"] == SCHEDULES[c["arm"]] and
                len(c["steps_zero_based"]) == len(SCHEDULES[c["arm"]]), "registered step set differs")
        expected = {'musk05': (2026101311, 141, [50, 65]), 'firefly06': (2026101312, 141, [39, 44]), 'sam07': (2026101311, 141, [54, 69])}[c["source_id"]]
        expected_window = [0, c["valid_frame_count"]-1] if c["arm"] == "global_weak" else expected[2]
        require(c["alpha"] == (.25 if c["arm"] == "global_weak" else 1.0), "arm alpha changed")
        require((c["seed"], c["geometry"]["frames"], c["physical_query_window"]) == (*expected[:2], expected_window) and
                c["geometry"]["width"] == 1312 and c["geometry"]["height"] == 736 and
                c["geometry"]["fps"] == 24, "source seed/geometry/physical window changed")
        require(sha(root / c["parent_graph"]) == c["parent_graph_sha256"], "historical graph changed")
        parent = read(root / c["parent_graph"])
        require(parent["5"]["inputs"]["prompt"] == c["prompt"] ==
                (root / "configs/prompts" / (c["source_id"] + ".txt")).read_text(), "prompt changed")
        require(parent["6"]["inputs"]["noise_seed"] == c["seed"], "seed changed")
        require(cache["prompt_sha256"] == hashlib.sha256(c["prompt"].encode()).hexdigest() and
                cache["source_video_sha256"] == c["video_sha256"] and
                cache["shared_run_id"] == s["historical_shared_run"], "cache binding changed")
        graph_path = root / "configs/graphs" / (c["run_id"] + ".json")
        require(read(graph_path) == expected_graph(c["run_id"], root), "graph has unregistered changes")
        jobs[c["run_id"]] = {"case": c, "source_id": c["source_id"], "seed": c["seed"],
                             "arm": c["arm"], "graph_sha256": sha(graph_path)}
    for relative, digest in read(root / "configs/numerical_reuse.json").items():
        require(sha(root / relative) == digest, "original numerical implementation changed: " + relative)
    return jobs, order


def validate_job(run, root=ROOT):
    root = Path(root)
    jobs, _ = registry(root)
    require(run in jobs, "unregistered run")
    for name, digest in read(root / "configs/input_hashes.json").items():
        path = root / "inputs" / name
        require(Path(name).name == name and not path.is_symlink() and sha(path) == digest,
                "source bytes differ")
    return jobs[run]


def audit_dir(value):
    path = Path(value)
    require(path == Path(read(ROOT / "configs/runtime.json")["remote_root"]) / "audit",
            "audit path differs")
    return path


def prepare_loader_inputs(run, root=ROOT):
    root = Path(root)
    row = validate_job(run, root)
    s = science(root)
    source = Path(s["parent_noise_file"])
    require(sha(source) == s["parent_noise_sha256"], "original AV noise differs")
    target = root / "audit" / (s["noise_pair_id"] + "_noise.pt")
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        try: os.link(source, target)
        except OSError as error:
            import errno, shutil
            if error.errno != errno.EXDEV: raise
            shutil.copy2(source, target)
    require(not target.is_symlink() and sha(target) == s["parent_noise_sha256"], "noise differs")
    return row


def validate_router(mode, alpha, radius, time_offset, start_frame, end_frame,
                    block_start, block_end, step_start, step_end, run_id, audit_path, schedule):
    row = validate_job(run_id)
    require(Path(audit_path) == Path(read(ROOT / "configs/runtime.json")["remote_root"]) /
            "audit/router", "router path differs")
    require((mode, alpha, radius, time_offset, start_frame, end_frame, block_start,
             block_end, step_start, step_end, schedule) ==
            ("mass_preserve", row["case"]["alpha"], 0, 0, *row["case"]["physical_query_window"],
             0, 50, 0, 20, row["arm"]), "fixed schedule scope differs")
