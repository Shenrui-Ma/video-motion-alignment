"""CPU evidence gate for three schedule-only jobs on one persistent exact service."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import torch
from r132_contract import read, sha, require, registry, science, latent_shapes, routing_layout, SOURCES
from execution_gate import atomic, persist_gate
from capture_checks import inspect_capture, signature


def verify_job(run, root=ROOT):
    root = Path(root)
    torch.set_num_threads(1)
    jobs, _ = registry(root)
    row = jobs[run]
    case = row["case"]
    s = science(root)
    runtime = read(root / "configs/runtime.json")
    owner = read(root / "processes/service.json")
    graph = read(root / "configs/graphs" / (run + ".json"))
    history = read(root / "logs" / (run + "_history.json"))
    job = read(root / "logs" / (run + "_job.json"))
    require(history["status"]["completed"] and history["status"]["status_str"] == "success" and
            history["prompt"][2] == graph and history["prompt"][1] == job["prompt_id"] and
            job["status"] == "success" and job["service_pid"] == owner["pid"] and
            job["service_identity"] == owner["identity"] and job["graph_sha256"] == row["graph_sha256"],
            "actual graph/history/service mismatch")
    require(owner["gpu_uuid"] == runtime["gpu_uuid"] and owner["port"] == runtime["port"],
            "service GPU/port mismatch")
    condition = read(root / "audit" / (run + "_conditioning.json"))
    parent = read(root / "design/conditioning.json")
    clean = lambda c: {k: v for k, v in c.items() if k not in ("run_id", "pair_snapshot")}
    require(clean(condition) == clean(parent) and condition["pair_snapshot"]["verified"] and
            condition["pair_snapshot"]["source_run_id"] == s["historical_shared_run"],
            "original exact conditions differ")
    cache = read(root / "audit" / ("CACHED_CONDITION_RUNTIME_" + run + ".json"))
    require(cache["run_id"] == run and cache["actual_tensors_exact"] and cache["packed_layout_exact"] and
            cache["reference_encoder_calls"] == cache["text_encoder_calls"] == 0,
            "actual condition cache reuse failed")
    grid = torch.tensor([float(x) for x in graph["9"]["inputs"]["sigmas"].split(",")],
                        dtype=torch.float32).tolist()
    router_path = root / "audit/router" / (run + ".json")
    router = read(router_path)
    steps = case["steps_zero_based"]
    expected = {"run_id": run, "mode": "mass_preserve", "alpha": case["alpha"], "radius": 0, "time_offset": 0,
                "pixel_interval_inclusive": case["physical_query_window"],
                "block_interval_half_open": [0, 50], "step_set_zero_based": steps,
                "schedule": case["arm"], "phase_displacement": 0, "fresh_patch_state": True,
                "started_calls": 1000, "completed_calls": 1000, "native_override_calls": 1000,
                "completed_forward_calls": 20, "routed_calls": len(steps)*50, "calls_by_forward": [50] * 20,
                "calls_by_block": [20] * 50, "routed_by_block": [len(steps)] * 50,
                "routed_by_forward": [50 if i in steps else 0 for i in range(20)],
                "sample_sigmas": grid, "expected_sampling_steps": 20}
    require(all(router.get(k) == v for k, v in expected.items()), "actual schedule/count mismatch")
    require("reference_origin" not in router and "combined_fixed_phase" not in router,
            "phase branch unexpectedly executed")
    require(all(x.get("sampled_finite", True) for x in router["forward_summaries"]), "nonfinite router")
    route = routing_layout(case)
    require(all(router["validated_layout"][k] == route[k] for k in
                ("latent_interval_half_open", "position_bin_coverage_inclusive", "pixel_interval_inclusive")),
            "original physical query/key bins changed")
    m, snapshots, _ = inspect_capture(root / "audit/x0" / run, run, grid, row["seed"], case)
    timing = read(root / "audit/x0" / run / "timing.json")
    require(timing["passed"] and timing["run_id"] == run and
            [x["step_zero_based"] for x in timing["callback_steps"]] == list(range(20)) and
            timing["sampler_wall_seconds"] > 0, "sampler timing incomplete")
    n = read(root / "audit" / (run + "_noise.json"))
    noise_file = root / "audit" / (s["noise_pair_id"] + "_noise.pt")
    require(sha(noise_file) == s["parent_noise_sha256"], "actual AV noise file changed")
    saved = torch.load(noise_file, map_location="cpu", weights_only=True)
    actual = [{k: signature(t)[k] for k in ("shape", "dtype", "sha256")} for t in saved["tensors"]]
    require(saved["hashes"] == actual == n["actual_noise_streams"] and
            saved["signature"] == n["signature"] and n["signature"]["seed"] == case["seed"],
            "actual AV noise tensor changed")
    images = history["outputs"]["14"]["images"]
    require(len(images) == 1 and images[0]["type"] == "output", "one output required")
    rel = Path(images[0].get("subfolder", "")) / images[0]["filename"]
    require(not rel.is_absolute() and ".." not in rel.parts, "unsafe output path")
    video = root / "output" / rel
    require(video.is_file() and not video.is_symlink() and video.stat().st_size > 0, "video absent/empty")
    props = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames",
        "-of", "json", str(video)], text=True))["streams"][0]
    require((props["width"], props["height"], int(props["nb_read_frames"]), props["avg_frame_rate"]) ==
            (1312, 736, case["geometry"]["frames"], "24/1"), "output geometry changed")
    bound = [root / "configs/graphs" / (run + ".json"), root / "logs" / (run + "_history.json"),
             root / "logs" / (run + "_job.json"), router_path,
             root / "audit" / (run + "_conditioning.json"), root / "audit" / (run + "_noise.json"),
             root / "audit/x0" / run / "manifest.json", root / "audit/x0" / run / "timing.json"]
    return {"schema": "r149-schedule-job-gate-v1", "passed": True, "run_id": run, "role": case["arm"],
            "service_owner": owner, "producer_seal_sha256": sha(root / "deploy_manifest.json"),
            "video": {"file": str(video), "sha256": sha(video), "properties": props},
            "valid_frames": case["valid_frame_count"], "evaluation_crop_xywh": case["evaluation_crop_xywh"],
            "NFE": 20, "Euler_updates": 20, "routed_blocks": len(steps)*50, "alpha": case["alpha"], "phase_displacement": 0,
            "actual_routed_steps_zero_based": steps, "physical_query_window": case["physical_query_window"],
            "sigma_selected": case["sigma_selected"], "sum_abs_delta_sigma": case["sum_abs_delta_sigma"],
            "job_wall_seconds": job["observed_unix"] - job["submitted_unix"],
            "sampler_timing": timing, "main_dit_blocks_dispatch_wall_seconds": router["forward_wall_seconds"],
            "dispatch_timing_scope": router["timing_scope"], "final_latent": snapshots[-1],
            "all_latent_snapshots": snapshots, "noise_sha256": s["parent_noise_sha256"],
            "binding_artifacts": {str(p.relative_to(root)): sha(p) for p in bound},
            "created_unix": time.time()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run")
    args = p.parse_args()
    destination = ROOT / "analysis/postrun" / SOURCES[0]
    destination.mkdir(exist_ok=True)
    if args.run:
        path = destination / (args.run + "_GATE.json")
        persist_gate(path, verify_job(args.run))
    else:
        jobs, order = registry(ROOT)
        runs = {jobs[r]["arm"]: read(destination / (r + "_GATE.json")) for r in order}
        owner = read(ROOT / "processes/service.json")
        require(all(v["passed"] and v["service_owner"] == owner for v in runs.values()), "batch owner mismatch")
        require(all(sha(ROOT / p) == v["sha256"] for p, v in
                    read(ROOT / "deploy_manifest.json")["files"].items()), "producer seal changed")
        path = destination / "SCHEDULE_RUNTIME_GATE.json"
        persist_gate(path, {"schema": "r149-fixed-schedule-segment-gate-v1", "segment_id": "sam_global_weak_host41", "migration_manifest_sha256": sha(ROOT / "configs/MIGRATION_MANIFEST.json"), "passed": True,
                           "source_id": SOURCES[0], "runs": runs, "service_owner": owner,
                           "producer_seal_sha256": sha(ROOT / "deploy_manifest.json"),
                           "runtime_profile_sha256": sha(ROOT / "configs/runtime.json"),
                           "same_persistent_service": True, "phase_displacement": 0,
                           "historical_mid_reused": True, "created_unix": time.time()})
    print(json.dumps({"gate": str(path), "sha256": sha(path), "passed": True}))


if __name__ == "__main__":
    main()
