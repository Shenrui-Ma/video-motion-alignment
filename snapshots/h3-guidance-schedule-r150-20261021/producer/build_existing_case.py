"""Reuse the completed R149 schedule implementation with exact R148 case inputs."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
R149 = PROJECT.parent / "h3-guidance-schedule-r149-20261020"
TEMPLATE = R149 / "cases/short_0358"
RUNTIME = R149 / "final_global_host41/cases/short_0358"
R148 = PROJECT.parent / "h3-timing-phase-combined-r148-20261020"
EVAL = PROJECT.parent / "h3-timing-phase-combined-eval-r148-20261020"
SCHEDULES = {"early": list(range(9)), "late": list(range(11, 20)),
             "split": list(range(4)) + list(range(15, 20)), "global_weak": list(range(20))}


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=["long_0039", "long_0059"])
    args = parser.parse_args()
    source = args.case
    root = PROJECT / "cases" / source
    history = R148 / "cases" / source
    assert not root.exists(), "Prepared cases must remain intact"
    root.mkdir(parents=True)

    def write(rel, value):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def cp(p, rel):
        out = root / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)

    template_seal = read(TEMPLATE / "deploy_manifest.json")
    for name, rec in template_seal["files"].items():
        assert sha(TEMPLATE / name) == rec["sha256"], name
        if name.startswith(("configs/graphs/", "configs/prompts/", "design/", "inputs/")):
            continue
        if name in ("audit/INHERITANCE.json", "configs/runtime_device_rebind.json"):
            continue
        cp(TEMPLATE / name, name)
    for folder in ("logs", "processes", "output", "input", "audit/router", "audit/x0"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for name in ("configs/gpu_quarantine.json", "configs/readonly_peer.json"):
        cp(RUNTIME / name, name)

    original = read(history / "configs/scientific_contract.json")
    parent_case = original["cases"][0]
    old_graph = history / "configs/graphs" / (parent_case["run_id"] + ".json")
    for name in ("design/parent_native_graph.json", "design/conditioning.json",
                 "design/HISTORICAL_FIXED.json", "design/R122_actual_native_router.json",
                 "design/H3_model.py", "design/R17_core.py", "configs/CONDITION_CACHE.json",
                 "configs/input_hashes.json"):
        cp(history / name, name)
    cp(old_graph, "design/parent_cached_graph.json")
    cp(history / "inputs" / parent_case["video"], "inputs/" + parent_case["video"])
    (root / "configs/prompts").mkdir(exist_ok=True)
    (root / "configs/prompts" / (source + ".txt")).write_text(parent_case["prompt"])
    fixed = read(root / "design/HISTORICAL_FIXED.json")["router_node_50"]["inputs"]
    assert (fixed["step_start"], fixed["step_end"], fixed["alpha"],
            fixed["radius"], fixed["time_offset"]) == (6, 15, 1., 0, 0)
    window = [fixed["start_frame"], fixed["end_frame"]]
    remote = "/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/" + source
    runtime = read(RUNTIME / "configs/runtime.json")
    runtime.update(remote_root=remote, port=8650 if source == "long_0039" else 8651,
                   profile="r150_" + source + "_schedule_only",
                   profile_scope="Four R149 schedule arms; exact historical inputs and noise; phase0")
    write("configs/runtime.json", runtime)

    science = read(TEMPLATE / "configs/scientific_contract.json")
    science["schema"] = "r150-fixed-schedule-extension-v1"
    science["cases"] = []
    grid = [float(x) for x in read(old_graph)["9"]["inputs"]["sigmas"].split(",")]
    for arm, steps in SCHEDULES.items():
        c = copy.deepcopy(parent_case)
        c.update(run_id=f"r150_{source}_seed{c['seed']}_{arm}", arm=arm,
                 physical_query_window=[0, c["valid_frame_count"] - 1] if arm == "global_weak" else window,
                 steps_zero_based=steps, phase_displacement=0, alpha=.25 if arm == "global_weak" else 1.)
        c["sigma_selected"] = [{"step": s, "sigma": grid[s], "sigma_next": grid[s+1]} for s in steps]
        c["sum_abs_delta_sigma"] = sum(abs(grid[s] - grid[s+1]) for s in steps)
        science["cases"].append(c)
    science.update(case_order=[c["run_id"] for c in science["cases"]], source_ids=[source],
                   arms=list(SCHEDULES), historical_runtime=original["historical_runtime"],
                   parent_cached_graph_sha256=sha(old_graph),
                   parent_r148_seal_sha256=sha(history / "deploy_manifest.json"))
    for key in ("conditioning_sha256", "historical_shared_run", "noise_pair_id",
                "parent_noise_file", "parent_noise_sha256"):
        science[key] = original[key]
    write("configs/scientific_contract.json", science)
    write("configs/queue.json", {"jobs": science["case_order"], "finalize": True})

    contract = root / "scripts/r132_contract.py"
    text = contract.read_text()
    old = '"short_0358": (2026101701, 107, [0, 104])}'
    new = '"short_0358": (2026101701, 107, [0, 104]),\n' + \
          '                    "long_0039": (2026101701, 107, [0, 105]),\n' + \
          '                    "long_0059": (2026101701, 158, [0, 143])}'
    assert old in text
    contract.write_text(text.replace(old, new))
    runner = root / "audit/root_run_batch.py"
    runner.write_text(runner.read_text().replace("analysis/postrun/short_0358/", f"analysis/postrun/{source}/"))
    cp(TEMPLATE / "producer/check_fresh_paths.py", "producer/check_fresh_paths.py")
    fresh = root / "producer/check_fresh_paths.py"
    fresh.write_text(fresh.read_text().replace("analysis/postrun/short_0358/", f"analysis/postrun/{source}/"))
    cp(TEMPLATE / "producer/watch_queue.py", "producer/watch_queue.py")

    test = root / "tests/test_short0358_recipe.py"
    text = test.read_text().replace("(0, 104, 6, 15)", f"({window[0]}, {window[1]}, 6, 15)")
    text = text.replace('[0, 104]', str(window)).replace('c["valid_frame_count"], 105',
                        f'c["valid_frame_count"], {parent_case["valid_frame_count"]}')
    text = text.replace('graph["52"]["inputs"]["length"], 107',
                        f'graph["52"]["inputs"]["length"], {parent_case["geometry"]["frames"]}')
    text = text.replace("5439f8f84b471b7d53e431b886c730fc7e78492b159ce7658e08a2bad046b310",
                        science["parent_noise_sha256"])
    test.unlink()
    (root / "tests/test_historical_recipe.py").write_text(text)

    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("r132_contract", contract)
    module = importlib.util.module_from_spec(spec)
    sys.modules["r132_contract"] = module
    spec.loader.exec_module(module)
    for c in science["cases"]:
        write("configs/graphs/" + c["run_id"] + ".json", module.expected_graph(c["run_id"], root))
    module.registry(root)
    evaluation = next(c for c in read(EVAL / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == source)
    review_file = EVAL / "review" / source / "REVIEW.json"
    review = read(review_file)
    write("design/HISTORICAL_TIMING.json", {
        "source": str(review_file), "source_sha256": sha(review_file), "events": review["events"],
        "official_MF": evaluation["official_MF"], "timing": evaluation["timing"],
        "prompt_format": "Historical prompt retained exactly for schedule comparison",
        "prompt_sha256": evaluation["prompt_sha256"], "task_verdict": review["task_verdict"]})
    write("audit/INHERITANCE.json", {
        "schema": "r150-historical-schedule-inheritance-v1", "source_id": source,
        "parent_root": str(history), "parent_seal_sha256": sha(history / "deploy_manifest.json"),
        "runtime_template": str(TEMPLATE), "template_seal_sha256": sha(TEMPLATE / "deploy_manifest.json"),
        "unchanged_numerical_files": read(root / "configs/numerical_reuse.json"),
        "method": "Same R149 RouterState/EventBlockPatch and selected steps; phase0",
        "previous_fixed_steps_reused": list(range(6, 15)),
        "requires_predecessor_release": "Actual prior R149 MF or preceding R150 video service release",
        "created_unix": time.time()})
    from execution_gate import seal
    sealed = seal(root)
    receipt = {"case": str(root), "source_id": source, "remote_root": remote,
               "seal_sha256": sha(root / "deploy_manifest.json"),
               "sealed_files": len(sealed["files"]), "jobs": science["case_order"]}
    write("producer/BUILD_RECEIPT.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
