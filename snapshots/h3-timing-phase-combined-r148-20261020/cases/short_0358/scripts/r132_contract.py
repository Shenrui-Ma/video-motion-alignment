"""R146 exact historical conditions; one additional reference-origin output."""
import copy
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    return dict(zip(("video","audio"),map(tuple,case["target_latent_shapes"])))


def routing_layout(case):
    total=case["target_latent_shapes"][0][2]
    spans=[(1,4,4,4,4)[i%5] for i in range(total)]
    end=case['valid_frame_count']-1;hi=next(i+1 for i in range(total) if sum(spans[:i+1])>end)
    return {'latent_interval_half_open':[0,hi], 'position_bin_coverage_inclusive':[0,sum(spans[:hi])-1],
            'pixel_interval_inclusive':[0,end], 'total_latent_bins':total, 'pure_pad_bins':list(range(hi,total)), 'frame_rows':943}


def expected_graph(root=ROOT):
    root = Path(root)
    s = science(root)
    c = s["cases"][0]
    remote = read(root / "configs/runtime.json")["remote_root"]
    g = copy.deepcopy(read(root / c["parent_graph"]))
    g.pop("2")
    g.pop("22")
    g.pop("23")
    g["5"] = {"class_type": "H3CachedReferenceConditioning", "inputs": {
        "cache_manifest": remote + "/configs/CONDITION_CACHE.json",
        "audit_dir": remote + "/audit", "run_id": c["run_id"]}}
    g["6"]["inputs"].update(audit_dir=remote + "/audit", run_id=c["run_id"],
                            pair_id=s["noise_pair_id"])
    g["50"]["class_type"] = "H3FixedPhaseCombined"
    g["50"]["inputs"].update(enabled=True, mode="mass_preserve", alpha=1.0,
        radius=0, time_offset=0, start_frame=0, end_frame=c["valid_frame_count"] - 1,
        block_start=0, block_end=50, step_start=6, step_end=15,
        run_id=c["run_id"], audit_dir=remote + "/audit/router")
    g["51"]["inputs"].update(source_audit_dir=remote + "/audit",
        source_run_id=s["historical_shared_run"], run_id=c["run_id"])
    g["52"]["inputs"].update(run_id=c["run_id"], output_dir=remote + "/audit/x0")
    g["14"]["inputs"]["filename_prefix"] = c["run_id"]
    return g


def registry(root=ROOT):
    root = Path(root)
    s = science(root)
    c = s["cases"][0]
    order = [c["run_id"]]
    require(len(s["cases"]) == 1 and s["case_order"] == order and
            s["source_ids"] == [c["source_id"]] and s["arms"] == ["fixed_phase"],
            "one additional phase job only")
    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True},
            "queue changed")
    require(s["online_observer"] is False and s["NFE_per_job"] == 20, "fixed20 only")
    require(c["seed"] in (2026101701, 2026101703) and c["geometry"]["width"]==1312 and c["geometry"]["height"]==736 and c["geometry"]["frames"] in (107,158) and c["geometry"]["fps"]==24, "geometry changed")
    require(sha(root / c["parent_graph"]) == c["parent_graph_sha256"], "parent graph changed")
    parent = read(root / c["parent_graph"])
    require(parent["5"]["inputs"]["prompt"] == c["prompt"] ==
            (root / "configs/prompts" / (c["source_id"] + ".txt")).read_text(), "prompt changed")
    require(parent["6"]["inputs"]["noise_seed"] == c["seed"], "actual parent seed changed")
    require(sha(root / "design/conditioning.json") == s["conditioning_sha256"],
            "historical conditioning metadata changed")
    cache = read(root / "configs/CONDITION_CACHE.json")
    require(cache["prompt_sha256"] == hashlib.sha256(c["prompt"].encode()).hexdigest()
            and cache["source_video_sha256"] == c["video_sha256"]
            and cache["shared_run_id"] == s["historical_shared_run"], "cache binding changed")
    graph_path = root / "configs/graphs" / (c["run_id"] + ".json")
    require(read(graph_path) == expected_graph(root), "graph differs outside registered changes")
    for relative, digest in read(root / "configs/numerical_reuse.json").items():
        require(sha(root / relative) == digest, "R132 numerical operator changed: " + relative)
    return {c["run_id"]: {"case": c, "source_id": c["source_id"], "seed": c["seed"],
            "arm": "fixed_phase", "graph_sha256": sha(graph_path)}}, order


def validate_job(run, root=ROOT):
    root = Path(root)
    jobs, _ = registry(root)
    require(run in jobs, "unregistered run")
    for name, digest in read(root / "configs/input_hashes.json").items():
        path = root / "inputs" / name
        require(Path(name).name == name and not path.is_symlink() and sha(path) == digest,
                "input video bytes differ")
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
    require(sha(source) == s["parent_noise_sha256"], "historical AV noise differs")
    target = root / "audit" / (s["noise_pair_id"] + "_noise.pt")
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        os.link(source, target)
    require(not target.is_symlink() and sha(target) == s["parent_noise_sha256"],
            "noise cache differs")
    return row


def validate_router(mode, alpha, radius, time_offset, start_frame, end_frame,
                    block_start, block_end, step_start, step_end, run_id, audit_path):
    row = validate_job(run_id)
    require(Path(audit_path) == Path(read(ROOT / "configs/runtime.json")["remote_root"]) /
            "audit/router", "router path differs")
    require((mode, alpha, radius, time_offset, start_frame, end_frame, block_start,
             block_end, step_start, step_end) == ("mass_preserve", 1.0, 0, 0, 0,
             row["case"]["valid_frame_count"] - 1, 0, 50, 6, 15), "fixed phase scope differs")
