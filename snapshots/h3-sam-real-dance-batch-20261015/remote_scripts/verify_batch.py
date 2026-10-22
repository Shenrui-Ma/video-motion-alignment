#!/usr/bin/env python3
"""Read-only CPU verification of four sequential Sam formal jobs.

Sole outputs: analysis/batch_verification.json and .txt. Exit 0=pass,
2=pending evidence, 1=invalid evidence. No server, GPU, torch or pickle execution.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import re
import shlex
import sys


REFERENCE_VERIFIER = Path("/Users/researcher/DevProjects/h3-musk-bedside-pair-20261014/scripts/verify_pair.py")
PREDECESSOR_ROOT = REFERENCE_VERIFIER.parents[1]
PREDECESSOR_RUNS = ("07_musk_s1_baseline", "07_musk_s1_weight3")
PREDECESSOR_PID = 23421
HOST = "192.0.2.1"
GPU = "GPU-REDACTED"
PORT = 8452
PYTHON = "/home/researcher/miniconda3/envs/comfyui/bin/python"
CORE_MAIN = "/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI/main.py"
REFERENCE_IMAGE = "sam_altman_village_global_20221117_original.jpg"
SEED = 2026101311
VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}
SHAPES = [[1, 24, 42, 46, 82], [1, 32, 2, 235]]
CASES = {
    "05": {"source": "05_real_megumi_v.mp4", "runs": ("05_sam_s1_baseline", "05_sam_s1_weight3"),
           "shared": "05_sam_shared_conditioning", "pair_id": "05_megumi_sam_s1",
           "event": [50, 65], "bins": [14, 20], "coverage": [47, 67],
           "noise_sha256": "7422660e9eaa6409f45f6100f061a6e3478a7a4b319b7613e5b820edec0fbbe4"},
    "07": {"source": "07_real_ary_v.mp4", "runs": ("07_sam_s1_baseline", "07_sam_s1_weight3"),
           "shared": "07_sam_shared_conditioning", "pair_id": "07_ary_sam_s1",
           "event": [54, 69], "bins": [16, 22], "coverage": [52, 72],
           "noise_sha256": "5f9543cbc54f890e1eee8168f5c49ac4722e29f1a9ab15ea3e2e27b3488e4d40"},
}
RUNS = tuple(run for case in CASES.values() for run in case["runs"])
# Independently read from each prelaunch cache. Equal tensor storages do not imply equal ZIP files.
NOISE_STREAM_SHA256 = ["94f396923114629ab5cd89dbd7d548d75c2b1a99f9d9984d1e8ccd7cc9d07d96",
                       "ddc72075fc55aaefb2afb28875d057e8cd6e38d81fee7f1b4e4203c7b81df4f3"]


def load_reference():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("bedside_verifier_helpers", REFERENCE_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def derive_layout(common, case, reference):
    metadata, layout = reference.derive_layout(common)
    spans = ([1, 4, 4, 4, 4] * 9)[:42]
    selected, cursor = [], 0
    for index, width in enumerate(spans):
        if cursor <= case["event"][1] and cursor + width > case["event"][0]:
            selected.append(index)
        cursor += width
    lo, hi = selected[0], selected[-1] + 1
    coverage = [sum(spans[:lo]), sum(spans[:hi]) - 1]
    if [lo, hi] != case["bins"] or coverage != case["coverage"]:
        raise ValueError("independent temporal bins disagree with case registration")
    ref_start, target_start = layout["reference_video_segment"][0], layout["target_video_segment"][0]
    prefix = coverage[0] * (5.0 / 3.0)
    text = metadata["text_len"]
    layout.update(latent_interval_half_open=[lo, hi], pixel_interval_inclusive=case["event"],
                  position_bin_coverage_inclusive=coverage,
                  key_interval_half_open=[ref_start + lo * 943, ref_start + hi * 943],
                  query_interval_half_open=[target_start + lo * 943, target_start + hi * 943],
                  key_first_time_coordinate=float(text + 1) + prefix,
                  query_first_time_coordinate=float(text + 236) + prefix)
    return metadata, layout


def cache_evidence(is_baseline, messages):
    events = [item[1] for item in messages if item[0] == "execution_cached"]
    cached = {str(node) for event in events for node in event.get("nodes", [])}
    return cached, bool(events) and (("5" not in cached) if is_baseline else ("5" in cached))


def successful_history(history):
    if "status" not in history and len(history) == 1:
        history = next(iter(history.values()))
    status = history.get("status", {})
    messages = status.get("messages", [])
    failed = status.get("status_str") in ("error", "failed") or any(item[0] == "execution_error" for item in messages)
    starts = [item[1]["timestamp"] for item in messages if item[0] == "execution_start"]
    ends = [item[1]["timestamp"] for item in messages if item[0] == "execution_success"]
    complete = status.get("status_str") == "success" and status.get("completed") is True and bool(starts and ends)
    return history, messages, failed, complete, (max(starts) if starts else None), (max(ends) if ends else None)


def validate_hook(hook, run, factor, case, complete, metadata, layout):
    errors, missing = [], []
    expected = {"run_id": run, "factor": factor, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "pixel_interval_inclusive": case["event"]}
    if complete:
        expected.update(expected_sampling_steps=20, started_calls=1000, completed_calls=1000,
                        completed_forward_calls=20, calls_by_block=[20] * 50, calls_by_forward=[50] * 20,
                        native_override_calls=0 if factor == 1 else 1000)
    else:
        missing.append("final hook after successful history")
        if hook.get("expected_sampling_steps") not in (None, 20):
            errors.append("unexpected sampling step count")
    for key, value in expected.items():
        if hook.get(key) != value:
            errors.append("hook mismatch: " + key)
    if hook.get("status") == "failed" or hook.get("error"):
        errors.append("hook reports failure")
    if metadata is None:
        missing.append("shared conditioning for dynamic layout validation")
        return errors, missing
    if hook.get("metadata") != metadata:
        errors.append("hook metadata differs from actual shared conditioning")
    if hook.get("validated_layout"):
        if hook["validated_layout"] != layout:
            errors.append("hook dynamic event layout mismatch")
    else:
        (errors if complete else missing).append("validated hook layout")
    if factor == 1:
        if hook.get("native_override_calls") != 0 or "first_attention_diagnostics" in hook:
            errors.append("baseline must have zero attention overrides")
        if hook.get("factor_1_path") != "original_block with original transformer_options and native Attention.forward":
            errors.append("baseline original-block path not established")
    else:
        diagnostic = hook.get("first_attention_diagnostics")
        if not diagnostic:
            (errors if complete else missing).append("weighted attention diagnostics")
            return errors, missing
        n, m = layout["seq_len"], 5658
        fields = {"selected_keys": m, "selected_queries": m, "appended_event_copies": 2,
                  "added_kv_rows": 2 * m, "kv_length_after_duplication": n + 2 * m,
                  "qkv_shape": [1, 56, n, 128], "dtype": "torch.bfloat16", "mask": None,
                  "native_function": "comfy.ldm.modules.attention.attention_pytorch"}
        for key, value in fields.items():
            if key not in diagnostic or diagnostic[key] != value:
                errors.append("weighted attention diagnostic mismatch: " + key)
        bias = diagnostic.get("logit_bias_equivalent")
        if not isinstance(bias, (int, float)) or not math.isclose(bias, math.log(3), rel_tol=0, abs_tol=1e-12):
            errors.append("weighted attention bias is not ln(3)")
        for key in ("key_slice_stats", "value_slice_stats", "query_slice_stats", "weighted_output_slice_stats", "weighted_vs_native_output_sample"):
            if diagnostic.get(key, {}).get("finite") is not True:
                errors.append("missing/nonfinite weighted diagnostic: " + key)
        effect = diagnostic.get("weighted_vs_native_output_sample", {}).get("rms_difference")
        if not isinstance(effect, (int, float)) or not math.isfinite(effect) or effect <= 0:
            errors.append("weighted attention first-call effect not finite/nonzero")
    return errors, missing


def predecessor_gate(h, sam_service_start=None):
    errors, missing, evidence = [], [], {"root": str(PREDECESSOR_ROOT), "formal_jobs": list(PREDECESSOR_RUNS)}
    def previous(relative):
        value = h.read_json(PREDECESSOR_ROOT / relative)
        if value is None:
            missing.append("predecessor " + relative)
        return value
    state = previous("logs/controller_state.json")
    cleanup = previous("processes/remote/cleanup.json")
    if state:
        evidence["controller_state"] = state
        if state.get("status") != "all_queued_jobs_complete" or set(state.get("completed", [])) != set(PREDECESSOR_RUNS):
            missing.append("predecessor both formal jobs completed in controller state")
    end_times = []
    for run in PREDECESSOR_RUNS:
        history = previous("logs/" + run + "_history.json")
        if history:
            _, _, failed, complete, _, end = successful_history(history)
            if failed:
                errors.append("predecessor failed history: " + run)
            elif not complete:
                missing.append("predecessor successful history: " + run)
            else:
                end_times.append(end / 1000)
    cleanup_time = None
    if cleanup:
        evidence["cleanup"] = cleanup
        if cleanup.get("pid") != PREDECESSOR_PID or cleanup.get("process_absent") is not True or cleanup.get("own_compute_absent") is not True:
            missing.append("predecessor service23421 absence and owned-compute release")
        times = [cleanup[key] for key in ("stopped_unix", "observed_unix") if isinstance(cleanup.get(key), (int, float))]
        if times:
            cleanup_time = max(times)
        else:
            missing.append("predecessor timestamped cleanup evidence")
    if sam_service_start is None:
        missing.append("Sam service start time for predecessor ordering proof")
    else:
        evidence["sam_service_started_unix"] = sam_service_start
        if end_times and sam_service_start < max(end_times):
            errors.append("Sam service started before predecessor formal completion")
        if cleanup_time is not None and sam_service_start < cleanup_time:
            errors.append("Sam service started before predecessor cleanup verification")
        if state and isinstance(state.get("observed_unix"), (int, float)) and state.get("status") == "all_queued_jobs_complete" and sam_service_start < state["observed_unix"]:
            errors.append("Sam service started before predecessor completion state")
    evidence.update(status="invalid" if errors else "pending" if missing else "pass", errors=errors, missing=missing)
    return evidence


def validate(root):
    reference = load_reference()
    h = reference.load_helpers()
    errors, missing, checks, storages = [], [], {}, {}
    def read(relative):
        value = h.read_json(root / relative)
        if value is None:
            missing.append(relative)
        return value
    def check(name, equal):
        checks[name] = bool(equal)
        if not equal:
            errors.append(name)
    def storage(relative, wanted):
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe tensor path")
        path = root / "audit" / relative
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            return
        if path not in storages:
            storages[path] = h.raw_storages(path)
        check("raw ZIP storage: " + str(relative), storages[path] == wanted)
    plan, selection, queue = read("configs/plan.json"), read("configs/runtime_selection.json"), read("configs/queue.json")
    if plan:
        check("plan host/GPU/formal jobs", plan.get("actual_host") == HOST and plan.get("gpu_uuid") == GPU
              and plan.get("formal_jobs") == list(RUNS) and plan.get("technical_benchmark") is None and plan.get("factors") == [1, 3])
        registered = {case["case_id"]: case for case in plan.get("cases", [])}
        check("plan exact two cases", set(registered) == set(CASES))
        for key, case in CASES.items():
            expected = {"source": case["source"], "formal_jobs": list(case["runs"]), "seed": SEED,
                        "source_event_full_frames": case["event"], "expected_latent_interval_half_open": case["bins"],
                        "expected_position_bin_coverage": case["coverage"], "expected_selected_reference_keys": 5658,
                        "expected_selected_target_queries": 5658, "noise_cache": case["pair_id"] + "_noise.pt",
                        "shared_node5_run_id": case["shared"]}
            check("plan case " + key, all(registered.get(key, {}).get(field) == value for field, value in expected.items()))
        gate = plan.get("predecessor", {})
        check("plan predecessor gate", gate.get("formal_jobs") == list(PREDECESSOR_RUNS)
              and gate.get("service_pid") == PREDECESSOR_PID and gate.get("must_complete_and_release_before_start") is True)
    if selection:
        check("selected host/GPU/port", selection.get("host") == HOST and selection.get("gpu", selection.get("gpu_index")) == 2 and selection.get("port") == PORT)
    if queue:
        check("exact sequential formal queue", queue.get("jobs") == list(RUNS) and queue.get("sealed") is True and queue.get("formal_runs") == 4)
    ref_meta = read("inputs/reference_provenance.json")
    input_names = [REFERENCE_IMAGE] + [case["source"] for case in CASES.values()]
    input_hashes = {}
    for filename in input_names:
        path = root / "inputs" / filename
        meta = ref_meta if filename == REFERENCE_IMAGE else read("inputs/" + Path(filename).stem + ".json")
        expected_hash = (meta or {}).get("sha256" if filename == REFERENCE_IMAGE else "output_sha256")
        if path.is_file():
            input_hashes[filename] = h.sha256(path)
            if expected_hash:
                check("input file SHA: " + filename, input_hashes[filename] == expected_hash)
            if path.suffix == ".mp4":
                check("input video geometry: " + filename, h.probe(path) == VIDEO)
        else:
            missing.append(str(path.relative_to(root)))

    commons, layouts, metadatas, common_paths = {}, {}, {}, {}
    for key, case in CASES.items():
        common_paths[key] = "audit/" + case["shared"] + "_conditioning.json"
        common = read(common_paths[key])
        if common:
            commons[key] = common
            check(key + ": shared identity", common.get("schema") == "h3-event-audit-v1" and common.get("run_id") == case["shared"])
            metadata, layout = derive_layout(common, case, reference)
            metadatas[key], layouts[key] = metadata, layout
            packed = common["packed_layout"]
            check(key + ": shared packed layout", common["input_video"]["shape"] == [141, 736, 1312, 3]
                  and packed["seq_len"] == layout["seq_len"] and packed["segments"] == layout["segments"]
                  and packed["position_ids"]["shape"] == [layout["seq_len"], 3])
            for call in common["native_vae_calls"]:
                check(key + ": clean storage records " + str(call["latent"]["shape"]), all("tensor_file" in call[field] for field in ("prepared_frames", "latent")))
            for record in h.tensor_records(common):
                signature = h.signature(record)
                storage(Path(record["tensor_file"]), Counter({(signature["sha256"], signature["bytes"]): 1}))
        cache = root / "audit" / (case["pair_id"] + "_noise.pt")
        if cache.is_file():
            check(key + ": case-specific noise container SHA", h.sha256(cache) == case["noise_sha256"])
        else:
            missing.append(str(cache.relative_to(root)))

    rows, graphs, jobs, actuals, noises, hooks = {}, {}, {}, {}, {}, {}
    for key, case in CASES.items():
        common = commons.get(key)
        for index, run in enumerate(case["runs"]):
            factor, before_errors, before_missing = (1 if index == 0 else 3), len(errors), len(missing)
            row = {"run_id": run, "case": key, "factor": factor, "steps": 20}
            rows[run] = row
            graph = read("configs/" + run + ".json")
            job = read("logs/" + run + "_job.json")
            history = read("logs/" + run + "_history.json")
            condition = read("audit/" + run + "_conditioning.json")
            noise = read("audit/" + run + "_noise.json")
            hook = read("audit/emphasis/" + run + ".json")
            complete = False
            if graph:
                graphs[run] = graph
                sink, save = h.one_node(graph, "SaveVideo")
                ref_id, ref = h.one_node(graph, "H3EventAuditReference")
                _, noi = h.one_node(graph, "H3EventAuditNoise")
                hook_id, intervention = h.one_node(graph, "H3EventEmphasis")
                snapshot_id, snapshot = h.one_node(graph, "H3PairConditionSnapshot")
                _, sigmas = h.one_node(graph, "ManualSigmas")
                check(run + ": identities", ref["run_id"] == case["shared"] and snapshot["source_run_id"] == case["shared"]
                      and all(node["run_id"] == run for node in (noi, intervention, snapshot)) and save["filename_prefix"] == run)
                check(run + ": factor/event/noise", intervention["factor"] == factor
                      and [intervention["start_frame"], intervention["end_frame"]] == case["event"]
                      and noi["noise_seed"] == SEED and noi["pair_id"] == case["pair_id"])
                check(run + ": source/reference", graph["22"]["inputs"]["file"] == case["source"] and graph["21"]["inputs"]["image"] == REFERENCE_IMAGE)
                check(run + ": cache wiring", ref_id == "5" and snapshot_id == "51" and snapshot["positive"] == ["5", 0]
                      and snapshot["target"] == ["5", 1] and intervention["positive"] == ["51", 0]
                      and graph["7"]["inputs"]["conditioning"] == ["51", 0] and graph["10"]["inputs"]["latent_image"] == ["51", 1])
                check(run + ": recipe", (ref["length"], ref["width"], ref["height"], ref["semantic_fps"], ref["phase_frames"]) == (141, 1312, 736, 2, 0)
                      and len(sigmas["sigmas"].split(",")) == 21 and graph["8"]["inputs"]["sampler_name"] == "euler"
                      and graph["41"]["inputs"]["shift_video"] == 12 and graph["41"]["inputs"]["shift_audio"] == 3
                      and graph["41"]["inputs"]["model"] == ["1", 0] and intervention["model"] == ["41", 0]
                      and not any("lora" in node["class_type"].lower() for node in graph.values()))
                if common:
                    check(run + ": shared prompt", common["prompt"] == ref["prompt"])
                if job:
                    jobs[run] = job
                    check(run + ": job graph/identity", job.get("name") == run and job.get("graph_sha256") == h.sha256(root / "configs" / (run + ".json")))
                    if job.get("status") in ("error", "failed"):
                        errors.append(run + ": failed job")
                    elif job.get("status") != "success":
                        missing.append(run + ": successful job status")
                if history:
                    history, messages, failed, complete, start, end = successful_history(history)
                    prompt = history.get("prompt", [])
                    check(run + ": history graph", len(prompt) >= 3 and prompt[2] == graph)
                    if job:
                        check(run + ": history prompt ID", len(prompt) >= 2 and prompt[1] == job.get("prompt_id"))
                    if failed:
                        errors.append(run + ": failed history")
                    if complete:
                        row.update(start_ms=start, end_ms=end, execution_seconds=(end - start) / 1000)
                        check(run + ": positive duration", end > start)
                        cached, expected_cache = cache_evidence(index == 0, messages)
                        row["cached_nodes"] = sorted(cached)
                        check(run + ": node5 cache policy", expected_cache)
                        check(run + ": fresh snapshot and hook", snapshot_id not in cached and hook_id not in cached)
                        artifacts = [item for item in history.get("outputs", {}).get(sink, {}).get("images", []) if item.get("type") == "output" and item.get("filename", "").endswith(".mp4")]
                        check(run + ": output artifact", len(artifacts) == 1 and artifacts[0].get("filename") == run + "_00001_.mp4" and not artifacts[0].get("subfolder"))
                    else:
                        missing.append(run + ": successful completed history")
            output = root / "outputs" / (run + "_00001_.mp4")
            if output.is_file():
                row.update(output_file=str(output.relative_to(root)), output_sha256=h.sha256(output), video_probe=h.probe(output))
                check(run + ": video geometry", row["video_probe"] == VIDEO)
            else:
                missing.append(str(output.relative_to(root)))
            if condition and common:
                check(run + ": copied shared manifest", h.canonical({k: v for k, v in condition.items() if k not in {"run_id", "pair_snapshot"}})
                      == h.canonical({k: v for k, v in common.items() if k != "run_id"}))
                snapshot = condition.get("pair_snapshot", {})
                check(run + ": snapshot source proof", condition.get("run_id") == run and snapshot.get("schema") == "h3-pair-condition-snapshot-v1"
                      and snapshot.get("verified") is True and snapshot.get("source_run_id") == case["shared"]
                      and snapshot.get("source_manifest") == case["shared"] + "_conditioning.json"
                      and snapshot.get("source_manifest_sha256") == h.sha256(root / common_paths[key]))
                actual = snapshot.get("actual", {})
                actuals[run] = h.canonical(actual)
                for field in ("conditioning_embedding", "token_tags", "target_latent_shapes", "packed_layout"):
                    check(run + ": actual " + field, h.canonical(actual.get(field)) == h.canonical(common[field]))
                refs = [{"reference_index": i, "kind": "image" if i == 0 else "video", "source_vae_call_index": i,
                         "clean_latent": h.signature(call["latent"])} for i, call in enumerate(common["native_vae_calls"])]
                check(run + ": actual reference latents", h.canonical(actual.get("references")) == refs)
                check(run + ": target dtypes", actual.get("target_latent_dtypes") == ["torch.float32", "torch.float32"])
            if noise:
                streams, signature = [h.signature(item) for item in noise["actual_noise_streams"]], noise["signature"]
                check(run + ": actual noise", noise.get("run_id") == run and noise.get("pair_id") == case["pair_id"]
                      and Path(noise["cache_file"]).name == case["pair_id"] + "_noise.pt" and signature.get("seed") == SEED
                      and signature.get("nested") is True and signature.get("shapes") == SHAPES
                      and signature.get("dtypes") == ["torch.float32", "torch.float32"]
                      and [item["shape"] for item in streams] == SHAPES and [item["sha256"] for item in streams] == NOISE_STREAM_SHA256)
                noises[run] = {"signature": signature, "streams": streams}
                storage(Path(case["pair_id"] + "_noise.pt"), Counter((item["sha256"], item["bytes"]) for item in streams))
            if hook:
                hooks[run] = hook
                bad, absent = validate_hook(hook, run, factor, case, complete, metadatas.get(key), layouts.get(key))
                errors.extend(run + ": " + message for message in bad)
                missing.extend(run + ": " + message for message in absent)
                row["hook"] = {field: hook.get(field) for field in ("factor", "completed_calls", "completed_forward_calls", "native_override_calls", "status")}
            row["status"] = "invalid" if len(errors) > before_errors else "pending" if len(missing) > before_missing else "pass"

    timestamps = {}
    for key, case in CASES.items():
        baseline, weighted = case["runs"]
        if baseline in graphs and weighted in graphs:
            check(key + ": only factor and run identifiers differ", reference.normalize_graph(graphs[baseline]) == reference.normalize_graph(graphs[weighted]))
            check(key + ": exactly shared node5", graphs[baseline]["5"] == graphs[weighted]["5"])
        for label, values in (("actual snapshots", actuals), ("actual noise", noises)):
            if baseline in values and weighted in values:
                check(key + ": paired " + label + " identical", values[baseline] == values[weighted])
        if baseline in hooks and weighted in hooks:
            check(key + ": runtime sigmas identical", hooks[baseline].get("sample_sigmas") == hooks[weighted].get("sample_sigmas"))
        if key in commons:
            mtime = (root / common_paths[key]).stat().st_mtime_ns / 1_000_000
            timestamps[key] = {"manifest_mtime_ms": mtime, "source": "rsync-preserved server filesystem mtime; no embedded creation timestamp"}
            if "start_ms" in rows[baseline]:
                timestamps[key].update(baseline_start_ms=rows[baseline]["start_ms"], baseline_end_ms=rows[baseline]["end_ms"])
                check(key + ": shared manifest created during corresponding baseline", rows[baseline]["start_ms"] <= mtime <= rows[baseline]["end_ms"])
            else:
                missing.append(key + ": baseline history to bracket shared manifest creation")
    if all(run in graphs for run in RUNS):
        check("same Sam identity prompt across four jobs", len({graphs[run]["5"]["inputs"]["prompt"] for run in RUNS}) == 1)
    if all("start_ms" in rows[run] for run in RUNS):
        check("four jobs follow registered serial order", all(rows[a]["end_ms"] <= rows[b]["start_ms"] for a, b in zip(RUNS, RUNS[1:])))

    runtime, known_models, parent = read("remote_configs/runtime_provenance.json"), read("configs/model_hashes_host9.json"), read("configs/parent_runtime_provenance.json")
    if runtime:
        check("actual host .9", runtime.get("actual_host", runtime.get("host")) == HOST)
        core = runtime.get("core_matches", {})
        check("frozen Core hash matches", bool(core) and all(value is True for value in core.values()))
        for relative in ("extensions/H3EventEmphasis/core.py", "extensions/H3EventEmphasis/__init__.py", "extensions/H3PairAudit/__init__.py",
                         "extensions/H3EventAudit/__init__.py", "scripts/backend_dispatch_audit.py", "scripts/compatibility_bootstrap.py",
                         "scripts/int8_row_chunking.py", "scripts/service.py", "scripts/launch_remote.py"):
            path = root / relative
            if path.is_file():
                check("executed code SHA: " + relative, runtime.get("code", {}).get(relative) == h.sha256(path))
            else:
                missing.append(relative)
        if known_models and parent:
            for name, expected in known_models.items():
                model, prior = runtime.get("models", {}).get(name, {}), parent.get("models", {}).get(name, {})
                check("model SHA/current metadata: " + name, model.get("sha256", model.get("prior_full_sha256")) == expected["sha256"]
                      and prior.get("prior_full_sha256", prior.get("sha256")) == expected["sha256"] and prior.get("bytes") is not None
                      and model.get("bytes") == prior["bytes"] and model.get("mtime_ns") == prior.get("mtime_ns") and model.get("size_mtime_match") is True)
        for name, digest in input_hashes.items():
            check("runtime input SHA: " + name, runtime.get("inputs", {}).get(name, {}).get("sha256") == digest)
    service_pid, service_start = None, None
    if all(run in jobs for run in RUNS):
        first = jobs[RUNS[0]]
        service_pid = first.get("service_pid")
        check("same process/runtime identity for four jobs", service_pid is not None
              and all(jobs[run].get("service_pid") == service_pid and jobs[run].get("service_identity") == first.get("service_identity") for run in RUNS))
        service = read("processes/remote/service_" + str(service_pid) + ".json")
        if service:
            service_start = service.get("started_unix")
            check("actual bound GPU2/port/service", service.get("pid") == service_pid and service.get("gpu_uuid") == GPU
                  and service.get("port") == PORT and service.get("identity") == first.get("service_identity") and service.get("cache_none") is False)
            tokens = shlex.split(first["service_identity"]["cmdline"])
            check("same frozen Python/Core/native attention", tokens[0] == PYTHON and CORE_MAIN in tokens
                  and "--use-pytorch-cross-attention" in tokens and "--enable-triton-backend" in tokens and "--cache-none" not in tokens)
    elif jobs:
        # An early service record is enough to audit the predecessor gate, never to prove all-four identity.
        first = next(iter(jobs.values()))
        path = root / "processes/remote" / ("service_" + str(first.get("service_pid")) + ".json")
        early = h.read_json(path)
        if early:
            service_start = early.get("started_unix")
    else:
        early = h.read_json(root / "processes/remote/service.json")
        if early:
            service_start = early.get("started_unix")
    gate = predecessor_gate(h, service_start)
    errors.extend(gate["errors"])
    missing.extend(gate["missing"])
    log = root / "logs/comfyui.log"
    runtime_log = {}
    if log.is_file():
        text = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text(errors="replace"))
        versions = sorted(set(re.findall(r"pytorch version:\s*(\S+)", text, re.IGNORECASE)))
        runtime_log = {"pytorch_versions": versions, "native_pytorch_attention": "Using pytorch attention" in text}
        check("single native Torch2.5 runtime", len(versions) == 1 and versions[0].startswith("2.5.") and runtime_log["native_pytorch_attention"])
    else:
        missing.append("logs/comfyui.log")
    traces = [(path, h.read_json(path)) for path in sorted((root / "logs").glob("*dispatch*.json"))]
    traces = [(path, trace) for path, trace in traces if trace and trace.get("schema") == "h3-backend-dispatch-audit-v1"]
    dispatch = {"attribution": "Shared process across four formal jobs; no per-arm or per-case counter attribution."}
    if not traces:
        missing.append("actual backend dispatch trace")
    elif service_pid is None:
        missing.append("all four job identities to bind process dispatch trace")
    else:
        matching = [(path, trace) for path, trace in traces if trace.get("pid") == service_pid]
        check("dispatch process PID", bool(matching))
        if matching:
            path, trace = max(matching, key=lambda item: sum(op.get("successful_calls", 0) for op in item[1].get("operations", {}).values()))
            operations = trace.get("operations", {})
            observed = {name: {field: op.get(field) for field in ("attempted_calls", "successful_calls", "failed_calls", "first_call")}
                        for name, op in operations.items() if op.get("successful_calls", 0) > 0}
            check("actual successful registered backend exports", bool(observed) and all(operations[name].get("registry_resolves_wrapper") is True for name in observed))
            check("dispatch logging healthy", not trace.get("logging_errors"))
            for name, op in operations.items():
                counts = [op.get(field, 0) for field in ("attempted_calls", "successful_calls", "failed_calls")]
                check("dispatch counts: " + name, all(type(count) is int and count >= 0 for count in counts) and counts[0] >= counts[1] + counts[2])
            dispatch.update(file=str(path.relative_to(root)), pid=service_pid, observed_exports=observed,
                            count_semantics=trace.get("count_semantics"), count_freshness=trace.get("count_freshness"))
    return {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid" if errors else "pending" if missing else "pass",
            "formal_run_ids": list(RUNS), "technical_benchmark": None, "runs": rows,
            "formal_count_passed": sum(row["status"] == "pass" for row in rows.values()), "checks": checks,
            "errors": errors, "missing": sorted(set(missing)), "case_layouts": layouts, "shared_manifest_timestamps": timestamps,
            "predecessor_gate": gate, "runtime_log": runtime_log, "backend_dispatch": dispatch,
            "independently_hashed_storage_files": len(storages),
            "case_noise_container_sha256": {key: case["noise_sha256"] for key, case in CASES.items()},
            "evidence_limits": [
                "Controls-only verification; no visual review, extra inference or efficacy claim. Four sequential formal jobs and no technical benchmark.",
                "Every case baseline computes its own shared node5; only that case's weighted run may reuse it. Actual snapshot hashes must match within each pair.",
                "Case05 and07 noise tensor storages happen to match at the same seed/shape, but their ZIP container hashes differ and are verified independently.",
                "Predecessor ordering requires archived successful Musk07 histories, completed controller state, process23421 cleanup/release and Sam service start time.",
                "Shared manifest creation is bracketed by each baseline using rsync-preserved filesystem mtime, not an embedded timestamp.",
                "Dispatch counts demonstrate successful backend exports in the shared process, including nested delegation; they do not identify individual arms or disjoint layers.",
                "Saved ZIP storages are independently hashed without pickle execution. Unsaved embeddings use runtime and snapshot hash records; target content uses cached object reuse plus shape/dtype.",
                "This single seed for each of two related choreography cases does not establish general attention-weighting efficacy."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except Exception as error:
        result = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid", "errors": [type(error).__name__ + ": " + str(error)], "missing": []}
    directory = args.root / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "batch_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = ["Sam same-host four-job batch verification", "Status: " + result["status"], "Formal jobs: " + ", ".join(RUNS),
             "Errors: " + str(len(result["errors"])), *["  " + item for item in result["errors"]],
             "Pending evidence: " + str(len(result["missing"])), *["  " + item for item in result["missing"]], "", *result.get("evidence_limits", [])]
    (directory / "batch_verification.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"], "missing_count": len(result["missing"]), "report": str(directory / "batch_verification.json")}))
    raise SystemExit(0 if result["status"] == "pass" else 2 if result["status"] == "pending" else 1)


if __name__ == "__main__":
    main()
