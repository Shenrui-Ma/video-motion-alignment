"""Bind one actual generation, then admit its exact local output bundle."""
import argparse
from common import *


def check_started(s):
    c = CONTRACT
    owner = s["service"]
    require(s["protocol_sha256"] == c["protocol"]["sha256"], "started protocol differs")
    require(owner["identity"]["start_ticks"] and owner["pid"] > 0, "missing exact owner")
    runtime = read(c["runtime"]["file"])
    require(owner["gpu_uuid"] == runtime["gpu_uuid"] and owner["port"] == runtime["port"]
            and owner["identity"]["uid"] == runtime["uid"], "started runtime differs")
    cmd = owner["identity"]["cmdline"]
    require(c["producer_remote"] in (" ".join(cmd) if isinstance(cmd, list) else cmd),
            "owner command outside producer")
    return owner


def bind(started):
    validate_static()
    owner = check_started(read(started))
    save(ROOT / "audit/EXECUTION_BINDING.json",
         dict(run_id=CONTRACT["run_id"], STARTED=bound(started), owner=owner))


def verify(d):
    c = CONTRACT
    e = read(d / "EXPORT.json")
    require(e["run_id"] == c["run_id"] and e["producer_root"] == c["producer_remote"], "export source")
    require(e["exporter_sha256"] == sha(ROOT / "scripts/export_bundle.py"), "exporter differs")
    required = {"STARTED.json","ROOT_EXIT_RECEIPT.json","COMPLETE_REVIEW_HOLD.json",
                "ONLINE_RUNTIME_GATE.json","graph.json","history.json","job.json",
                "centeredauto.mp4","counterfactual.compact.json"}
    require(set(e["files"]) == required, "export evidence inventory differs")
    require(e["original_audit"]["file"] == str(Path(c["producer_remote"])/"audit/counterfactual"/(c["run_id"]+".json"))
            and len(e["original_audit"]["sha256"]) == 64, "original audit provenance")
    for name, digest in e["files"].items():
        require(Path(name).name == name and sha(d / name) == digest, "export file changed")
    started = read(d / "STARTED.json")
    owner = check_started(started)
    binding = read(ROOT / "audit/EXECUTION_BINDING.json")
    require(binding["run_id"] == c["run_id"] and binding["owner"] == owner
            and binding["STARTED"]["sha256"] == sha(d / "STARTED.json"), "unbound actual generation")
    g = read(d / "ONLINE_RUNTIME_GATE.json")
    done = read(d / "COMPLETE_REVIEW_HOLD.json")
    release = read(d / "ROOT_EXIT_RECEIPT.json")
    require(done["passed"] is True and done["run_id"] == c["run_id"]
            and done["no_followup_submission"] is True
            and done["gate_sha256"] == sha(d / "ONLINE_RUNTIME_GATE.json"), "completion binding")
    require(g["passed"] is True and g["status"] == "pass" and g["cleanup_verified"] is True
            and g["valid_frames"] == 98 and g["verified_runs"] == [c["run_id"]], "runtime gate")
    require(g["producer_manifest_sha256"] == c["producer_seal"]["sha256"]
            and g["protocol_sha256"] == c["protocol"]["sha256"], "producer seal/protocol")
    require(g["service_record"] == release["service"] == owner and release["passed"] is True, "mixed owners")
    require(all(release["service_cleanup"][k] is True for k in ("process_absent", "own_compute_absent")),
            "main release")
    require(all(release["observer_children"][k] is True for k in
                ("all_exact_generations_absent", "all_registered_CUDA_pids_absent")), "child release")
    graph, history, job = [read(d / f"{name}.json") for name in ("graph", "history", "job")]
    require(sha(d / "graph.json") == c["graph"]["sha256"] and graph["5"]["inputs"]["prompt"] == c["case"]["prompt"], "graph")
    require(history["status"]["completed"] is True and history["status"]["status_str"] == "success"
            and history["prompt"][2] == graph and history["prompt"][1] == job["prompt_id"], "history")
    require(job["status"] == "success" and job["name"] == c["run_id"]
            and job["graph_sha256"] == c["graph"]["sha256"] and job["service_pid"] == owner["pid"]
            and job["service_identity"] == owner["identity"], "job owner")
    outputs = history["outputs"]["14"]["images"]
    require(len(outputs) == 1 and outputs[0]["type"] == "output", "single video required")
    output = Path(c["producer_remote"]) / "output" / outputs[0].get("subfolder", "") / outputs[0]["filename"]
    require(".." not in output.parts and str(output) == g["video"]["file"]
            and sha(d / "centeredauto.mp4") == g["video"]["sha256"], "exact actual video")
    require(len(g["cases"]) == 1, "single actual case required")
    case = g["cases"][0]
    require(case["run"] == c["run_id"] and case["arm"] == "visible_only", "actual role")
    noise = read(c["noise"]["file"])
    inputs = case["independent_parent_inputs"]
    require(inputs["actual_initial_AV_noise_exact"] is True
            and inputs["noise_file_sha256"] == noise["source_sha256"], "actual AV noise differs")
    a = read(d / "counterfactual.compact.json")
    cf = a["counterfactual"]
    mask = cf["full_physical_indices"]
    require(mask == sorted(set(mask)) and all(type(i) is int and 1 <= i < 20 for i in mask), "ON mask")
    nfe = 20 + len(mask)
    require(a["status"] == "complete" and cf["seed"] == 2026101703
            and cf["actual_model_nfe"] == case["NFE"] == g["efficiency"]["NFE"] == nfe
            and cf["actual_euler_updates"] == cf["callback_count"] == case["updates"] == 20, "cost")
    require(a["completed_forward_calls"] == nfe and a["completed_calls"] == 50*nfe
            and a["routed_calls"] == 50*len(mask) and a["calls_by_forward"] == [50]*nfe, "block count")
    require(case["mask"] == mask and case["first_on"] == (mask[0] if mask else None), "gate mask")
    for key in ("steps", "measurements"):
        require([v["physical_index"] for v in cf[key]] == list(range(20)), "20 actual " + key)
    require(len(cf["branches"]) == nfe and [v["nfe_index"] for v in cf["branches"]] == list(range(nfe)), "branches")
    require(all(s["decision"]["chosen_full"] == (s["physical_index"] in mask) for s in cf["steps"]), "decisions")
    require(all(isinstance(m["centered_eligibility"], dict) for m in cf["measurements"]), "centered records")
    require([v["index"] for v in g["raw_filtered_pose_binding"]] == list(range(20))
            and [v["index"] for v in g["efficiency"]["per_step"]] == list(range(20)), "pose/timing coverage")
    first = mask[0] if mask else 19
    require([v["physical_index"] for v in case["independent_native_prefix"]] == list(range(first+1)),
            "historical prefix diagnostic coverage")
    renderer = load_helper("r120_render_pair")
    renderer.check_time(renderer.media_info(d / "centeredauto.mp4", "/opt/homebrew/bin/ffprobe"), 107, 1312, 736)
    return dict(ON_indices=mask, NFE=nfe, Euler_updates=20, observations=20)


def intake(bundle):
    validate_static()
    bundle = Path(bundle).resolve()
    cost = verify(bundle)
    dest = ROOT / "incoming/actual"
    require(not dest.exists(), "actual intake already exists")
    dest.mkdir()
    for name in [*read(bundle / "EXPORT.json")["files"], "EXPORT.json"]:
        link(bundle / name, dest / name)
    save(dest / "COLLECTION.json", dict(run_id=CONTRACT["run_id"], cost=cost,
         files={p.name: sha(p) for p in dest.iterdir()}, GPU_started=False))
    videos = {k: {x: v[x] for x in ("file", "sha256")} for k, v in CONTRACT["historical"].items()}
    videos["centeredauto"] = bound(dest / "centeredauto.mp4")
    save(ROOT / "prepared/MF_INPUTS.json", dict(benchmark="IVEBench", source_id="short_0252",
         actual_role="centeredauto", full_videos=videos, valid_frames=98, total_frames=107,
         evaluation_indices=list(range(98)), evaluation_fps=24, crop_xywh=[16,8,1280,720],
         collection=bound(dest / "COLLECTION.json"), new_tracking_roles=["centeredauto"], GPU_started=False))
    return cost


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    b = sub.add_parser("bind"); b.add_argument("--started", type=Path, required=True)
    i = sub.add_parser("intake"); i.add_argument("--bundle", type=Path, required=True)
    a = p.parse_args()
    result = validate_static() and {"passed": True} if a.command == "check" else (
        bind(a.started) if a.command == "bind" else intake(a.bundle))
    print(json.dumps(result))
