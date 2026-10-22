#!/usr/bin/env python3
"""CPU-only read-only verification of the same-process Musk factor1/factor3 pair.

Writes only analysis/pair_verification.json and .txt. Exit 0=verified pass,
2=pending evidence, 1=invalid evidence. Never imports torch or loads pickle.
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


RUNS = ("05_musk_s1_baseline", "05_musk_s1_weight3")
BENCHMARK = "05_musk_s1_weight3_benchmark2"
COMMON = "05_musk_shared_conditioning"
PAIR_ID = "05_megumi_musk_s1"
HOST = "192.0.2.1"
GPU = "GPU-REDACTED"
SEED = 2026101311
VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}
SHAPES = [[1, 24, 42, 46, 82], [1, 32, 2, 235]]
# Frozen from the existing prelaunch noise cache; no synthetic tensors generated.
NOISE_FILE_SHA256 = "7422660e9eaa6409f45f6100f061a6e3478a7a4b319b7613e5b820edec0fbbe4"
NOISE_STREAM_SHA256 = ["94f396923114629ab5cd89dbd7d548d75c2b1a99f9d9984d1e8ccd7cc9d07d96",
                       "ddc72075fc55aaefb2afb28875d057e8cd6e38d81fee7f1b4e4203c7b81df4f3"]
HELPER_PATH = Path("/Users/researcher/DevProjects/h3-event-emphasis-pilot-20261013/scripts/verify_pair.py")


def load_helpers():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("sealed_storage_verifier", HELPER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_graph(graph):
    result = json.loads(json.dumps(graph))
    for node in result.values():
        kind, values = node["class_type"], node["inputs"]
        if kind in {"H3EventAuditNoise", "H3EventEmphasis", "H3PairConditionSnapshot"}:
            values.pop("run_id", None)
        if kind == "H3EventEmphasis":
            values.pop("factor", None)
        if kind == "SaveVideo":
            values.pop("filename_prefix", None)
    return result


def derive_layout(common):
    calls = common["native_vae_calls"]
    if len(calls) != 2:
        raise ValueError("expected one image and one video VAE call")
    image, video = calls
    shape = image["latent"]["shape"]
    if (len(shape) != 5 or shape[:3] != [1, 24, 1]
            or any(type(n) is not int or n < 2 or n % 2 for n in shape[3:])):
        raise ValueError("invalid reference image latent geometry")
    ih, iw = shape[3:]
    if image["prepared_frames"]["shape"] != [1, ih * 16, iw * 16, 3]:
        raise ValueError("reference image prepared/latent geometry mismatch")
    if video["prepared_frames"]["shape"] != [141, 736, 1312, 3] or video["latent"]["shape"] != SHAPES[0]:
        raise ValueError("source video prepared/latent geometry mismatch")
    context = common["conditioning_embedding"]["shape"]
    if len(context) != 3 or context[0] != 1 or context[2] != 5120 or type(context[1]) is not int or context[1] < 1:
        raise ValueError("invalid shared conditioning shape")
    if common["target_latent_shapes"] != SHAPES:
        raise ValueError("target latent geometry mismatch")
    text, image_rows, frame_rows = context[1], ih * iw // 4, 943
    ref_start = text + image_rows
    ref_stop = ref_start + 42 * frame_rows
    target_start = ref_stop + 470
    seq_len = target_start + 42 * frame_rows
    segments = [[0, text, "text"], [text, ref_start, "ref_img"], [ref_start, ref_stop, "ref_img"],
                [ref_stop, target_start, "audio"], [target_start, seq_len, "video"]]
    spans = [1, 4, 4, 4, 4] * 8 + [1, 4]
    selected, cursor = [], 0
    for index, span in enumerate(spans):
        if cursor <= 65 and cursor + span > 50:
            selected.append(index)
        cursor += span
    lo, hi = selected[0], selected[-1] + 1
    coverage = [sum(spans[:lo]), sum(spans[:hi]) - 1]
    if (lo, hi, coverage) != (14, 20, [47, 67]):
        raise ValueError("event temporal bin derivation differs from preregistration")
    prefix = coverage[0] * (5.0 / 3.0)
    metadata = {"text_len": text, "context_shape": context, "refs": [
        {"kind": "image", "index": 0, "latent_t": 1, "latent_h": ih, "latent_w": iw,
         "latent_shape": shape, "frame_rows": image_rows, "ref_audio_t": 0},
        {"kind": "video", "index": 1, "latent_t": 42, "latent_h": 46, "latent_w": 82,
         "latent_shape": SHAPES[0], "frame_rows": frame_rows, "ref_audio_t": 0}]}
    layout = {"seq_len": seq_len, "segments": segments, "signature": [text, 42, 46, 82, 235],
              "reference_index": 1, "reference_kind": "video", "reference_video_segment": [ref_start, ref_stop],
              "reference_image_segments": [[text, ref_start]], "target_video_segment": [target_start, seq_len],
              "latent_interval_half_open": [lo, hi], "pixel_interval_inclusive": [50, 65],
              "position_bin_coverage_inclusive": coverage,
              "key_interval_half_open": [ref_start + lo * frame_rows, ref_start + hi * frame_rows],
              "query_interval_half_open": [target_start + lo * frame_rows, target_start + hi * frame_rows],
              "key_first_time_coordinate": float(text + 1) + prefix,
              "query_first_time_coordinate": float(text + 236) + prefix, "frame_rows": frame_rows}
    return metadata, layout


def validate_hook(hook, run, factor, steps, completed, metadata, layout):
    errors, missing = [], []
    expected = {"run_id": run, "factor": factor, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "pixel_interval_inclusive": [50, 65]}
    if completed:
        expected.update(expected_sampling_steps=steps, started_calls=50 * steps, completed_calls=50 * steps,
                        completed_forward_calls=steps, calls_by_block=[steps] * 50,
                        calls_by_forward=[50] * steps, native_override_calls=0 if factor == 1 else 50 * steps)
    else:
        missing.append("final hook after completed history")
        if hook.get("expected_sampling_steps") not in (None, steps):
            errors.append("unexpected sampling step count")
    for key, value in expected.items():
        if hook.get(key) != value:
            errors.append("hook " + key + " differs from expected")
    if hook.get("status") == "failed" or hook.get("error"):
        errors.append("hook reports failure")
    if metadata is None:
        missing.append("shared conditioning needed for dynamic hook validation")
        return errors, missing
    if hook.get("metadata") != metadata:
        errors.append("hook metadata differs from shared conditioning")
    if hook.get("validated_layout"):
        if hook["validated_layout"] != layout:
            errors.append("hook layout differs from independently derived event bounds")
    else:
        (errors if completed else missing).append("validated hook layout")
    if factor == 1:
        if hook.get("native_override_calls") != 0 or "first_attention_diagnostics" in hook:
            errors.append("factor1 must never invoke attention override")
        if hook.get("factor_1_path") != "original_block with original transformer_options and native Attention.forward":
            errors.append("factor1 original-block path identity is missing")
    else:
        diagnostic = hook.get("first_attention_diagnostics")
        if not diagnostic:
            (errors if completed else missing).append("factor3 attention diagnostics")
            return errors, missing
        n, m = layout["seq_len"], 5658
        values = {"selected_keys": m, "selected_queries": m, "appended_event_copies": 2,
                  "added_kv_rows": 2 * m, "kv_length_after_duplication": n + 2 * m,
                  "qkv_shape": [1, 56, n, 128], "dtype": "torch.bfloat16", "mask": None,
                  "native_function": "comfy.ldm.modules.attention.attention_pytorch"}
        for key, value in values.items():
            if key not in diagnostic or diagnostic[key] != value:
                errors.append("factor3 diagnostic mismatch: " + key)
        bias = diagnostic.get("logit_bias_equivalent")
        if not isinstance(bias, (int, float)) or not math.isclose(bias, math.log(3), rel_tol=0, abs_tol=1e-12):
            errors.append("factor3 bias is not ln(3)")
        for key in ("key_slice_stats", "value_slice_stats", "query_slice_stats",
                    "weighted_output_slice_stats", "weighted_vs_native_output_sample"):
            if diagnostic.get(key, {}).get("finite") is not True:
                errors.append("missing/nonfinite factor3 diagnostic: " + key)
        effect = diagnostic.get("weighted_vs_native_output_sample", {})
        if not isinstance(effect.get("rms_difference"), (int, float)) or not math.isfinite(effect["rms_difference"]) or effect["rms_difference"] <= 0:
            errors.append("factor3 first-call numerical effect is not finite and nonzero")
    return errors, missing


def validate(root):
    h = load_helpers()
    errors, missing, checks, storage_cache = [], [], {}, {}
    def read(relative):
        value = h.read_json(root / relative)
        if value is None:
            missing.append(relative)
        return value
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            errors.append(name)
    def storage(relative, wanted):
        path = root / "audit" / relative
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            return
        if path not in storage_cache:
            storage_cache[path] = h.raw_storages(path)
        check("raw tensor storage: " + str(relative), storage_cache[path] == wanted)

    plan = read("configs/plan.json")
    selection = read("configs/runtime_selection.json")
    if plan:
        expected = {"actual_host": HOST, "gpu_uuid": GPU, "formal_jobs": list(RUNS), "factors": [1, 3],
                    "technical_benchmark": BENCHMARK, "seed": SEED, "source_event_full_frames": [50, 65],
                    "expected_latent_interval_half_open": [14, 20], "expected_position_bin_coverage": [47, 67],
                    "expected_selected_reference_keys": 5658, "expected_selected_target_queries": 5658}
        for key, value in expected.items():
            check("plan: " + key, plan.get(key) == value)
    if selection:
        check("runtime selection host/GPU", selection.get("host") == HOST and selection.get("gpu_uuid") == GPU)
    source_meta, ref_meta = read("inputs/source_metadata.json"), read("inputs/reference_provenance.json")
    for filename, expected_hash in (("05_real_megumi_v.mp4", (source_meta or {}).get("output_sha256")),
                                    ("elon_musk_royal_society.jpg", (ref_meta or {}).get("sha256"))):
        path = root / "inputs" / filename
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
        elif expected_hash:
            check("input file hash: " + filename, h.sha256(path) == expected_hash)
            if path.suffix == ".mp4":
                check("source video geometry", h.probe(path) == VIDEO)
    common_path = "audit/" + COMMON + "_conditioning.json"
    common = read(common_path)
    metadata = layout = None
    if common:
        check("shared conditioning identity", common.get("schema") == "h3-event-audit-v1" and common.get("run_id") == COMMON)
        metadata, layout = derive_layout(common)
        check("shared input geometry", common["input_video"]["shape"] == [141, 736, 1312, 3])
        packed = common["packed_layout"]
        check("shared packed layout", packed["seq_len"] == layout["seq_len"] and packed["segments"] == layout["segments"])
        check("shared position geometry", packed["position_ids"]["shape"] == [layout["seq_len"], 3])
        for call in common["native_vae_calls"]:
            check("clean reference storage records: " + str(call["latent"]["shape"]), all("tensor_file" in call[key] for key in ("prepared_frames", "latent")))
        for record in h.tensor_records(common):
            relative = Path(record["tensor_file"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe shared tensor storage path")
            signature = h.signature(record)
            storage(relative, Counter({(signature["sha256"], signature["bytes"]): 1}))
    noise_path = root / "audit" / (PAIR_ID + "_noise.pt")
    if noise_path.is_file():
        check("shared actual noise cache byte hash", h.sha256(noise_path) == NOISE_FILE_SHA256)
    else:
        missing.append(str(noise_path.relative_to(root)))

    rows, graphs, jobs, actual_snapshots, noise_signatures, hooks = {}, {}, {}, {}, {}, {}
    for run, factor, steps in ((BENCHMARK, 3, 2), (RUNS[0], 1, 20), (RUNS[1], 3, 20)):
        row_errors_start, row_missing_start = len(errors), len(missing)
        row = {"run_id": run, "factor": factor, "steps": steps, "kind": "technical" if run == BENCHMARK else "formal"}
        rows[run] = row
        graph = read("configs/" + run + ".json")
        job = read("logs/" + run + "_job.json")
        history = read("logs/" + run + "_history.json")
        condition = read("audit/" + run + "_conditioning.json")
        noise = read("audit/" + run + "_noise.json")
        hook = read("audit/emphasis/" + run + ".json")
        completed = False
        if graph:
            graphs[run] = graph
            sink, save = h.one_node(graph, "SaveVideo")
            ref_id, ref = h.one_node(graph, "H3EventAuditReference")
            _, noi = h.one_node(graph, "H3EventAuditNoise")
            hook_id, intervention = h.one_node(graph, "H3EventEmphasis")
            snapshot_id, snapshot = h.one_node(graph, "H3PairConditionSnapshot")
            _, sigmas = h.one_node(graph, "ManualSigmas")
            check(run + ": graph identities", ref["run_id"] == COMMON and snapshot["source_run_id"] == COMMON
                  and all(node["run_id"] == run for node in (noi, intervention, snapshot)) and save["filename_prefix"] == run)
            check(run + ": factor/event/noise", intervention["factor"] == factor
                  and [intervention["start_frame"], intervention["end_frame"]] == [50, 65]
                  and noi["noise_seed"] == SEED and noi["pair_id"] == PAIR_ID)
            check(run + ": conditioning cache wiring", ref_id == "5" and snapshot_id == "51"
                  and snapshot["positive"] == ["5", 0] and snapshot["target"] == ["5", 1]
                  and intervention["positive"] == ["51", 0] and graph["7"]["inputs"]["conditioning"] == ["51", 0]
                  and graph["10"]["inputs"]["latent_image"] == ["51", 1])
            check(run + ": recipe", (ref["length"], ref["width"], ref["height"], ref["semantic_fps"], ref["phase_frames"]) == (141, 1312, 736, 2, 0)
                  and len(sigmas["sigmas"].split(",")) == steps + 1 and graph["8"]["inputs"]["sampler_name"] == "euler"
                  and graph["41"]["inputs"]["shift_video"] == 12 and graph["41"]["inputs"]["shift_audio"] == 3)
            if common:
                check(run + ": shared prompt", common["prompt"] == ref["prompt"])
            if job:
                jobs[run] = job
                check(run + ": job identity/hash", job.get("name") == run and job.get("graph_sha256") == h.sha256(root / "configs" / (run + ".json")))
                if job.get("status") in ("error", "failed"):
                    errors.append(run + ": failed job")
                elif job.get("status") != "success":
                    missing.append(run + ": successful job status")
            if history:
                if "status" not in history and len(history) == 1:
                    history = next(iter(history.values()))
                prompt, status = history.get("prompt", []), history.get("status", {})
                check(run + ": history graph", len(prompt) >= 3 and prompt[2] == graph)
                if job:
                    check(run + ": prompt ID", len(prompt) >= 2 and prompt[1] == job.get("prompt_id"))
                messages = status.get("messages", [])
                if status.get("status_str") in ("error", "failed") or any(item[0] == "execution_error" for item in messages):
                    errors.append(run + ": failed history")
                starts = [item[1]["timestamp"] for item in messages if item[0] == "execution_start"]
                ends = [item[1]["timestamp"] for item in messages if item[0] == "execution_success"]
                completed = status.get("status_str") == "success" and status.get("completed") is True and bool(starts and ends)
                if completed:
                    row.update(start_ms=max(starts), end_ms=max(ends), execution_seconds=(max(ends) - max(starts)) / 1000)
                    check(run + ": positive duration", row["execution_seconds"] > 0)
                    cache_events = [item[1] for item in messages if item[0] == "execution_cached"]
                    cached = {str(node) for event in cache_events for node in event.get("nodes", [])}
                    row["cached_nodes"] = sorted(cached)
                    check(run + ": shared node5 cache policy", bool(cache_events) and (("5" not in cached) if run == BENCHMARK else ("5" in cached)))
                    check(run + ": fresh snapshot/intervention", snapshot_id not in cached and hook_id not in cached)
                    artifacts = [item for item in history.get("outputs", {}).get(sink, {}).get("images", [])
                                 if item.get("type") == "output" and item.get("filename", "").endswith(".mp4")]
                    check(run + ": named output", len(artifacts) == 1 and artifacts[0].get("filename") == run + "_00001_.mp4" and not artifacts[0].get("subfolder"))
                else:
                    missing.append(run + ": successful completed history")
        if run in RUNS:
            output = root / "outputs" / (run + "_00001_.mp4")
            if output.is_file():
                row.update(output_file=str(output.relative_to(root)), output_sha256=h.sha256(output), video_probe=h.probe(output))
                check(run + ": formal video geometry", row["video_probe"] == VIDEO)
            else:
                missing.append(str(output.relative_to(root)))
        if condition and common:
            check(run + ": copied shared manifest", h.canonical({key: value for key, value in condition.items() if key not in {"run_id", "pair_snapshot"}})
                  == h.canonical({key: value for key, value in common.items() if key != "run_id"}))
            snapshot = condition.get("pair_snapshot", {})
            check(run + ": snapshot/source identity", condition.get("run_id") == run and snapshot.get("schema") == "h3-pair-condition-snapshot-v1"
                  and snapshot.get("verified") is True and snapshot.get("source_run_id") == COMMON
                  and snapshot.get("source_manifest") == COMMON + "_conditioning.json"
                  and snapshot.get("source_manifest_sha256") == h.sha256(root / common_path))
            actual = snapshot.get("actual", {})
            actual_snapshots[run] = h.canonical(actual)
            for field in ("conditioning_embedding", "token_tags", "target_latent_shapes", "packed_layout"):
                check(run + ": actual snapshot " + field, h.canonical(actual.get(field)) == h.canonical(common[field]))
            references = [{"reference_index": index, "kind": "image" if index == 0 else "video",
                           "source_vae_call_index": index, "clean_latent": h.signature(call["latent"])}
                          for index, call in enumerate(common["native_vae_calls"])]
            check(run + ": actual clean reference snapshots", h.canonical(actual.get("references")) == references)
            check(run + ": snapshot target dtype", actual.get("target_latent_dtypes") == ["torch.float32", "torch.float32"])
        if noise:
            streams = [h.signature(stream) for stream in noise["actual_noise_streams"]]
            signature = noise["signature"]
            check(run + ": actual noise identity", noise.get("run_id") == run and noise.get("pair_id") == PAIR_ID
                  and Path(noise["cache_file"]).name == PAIR_ID + "_noise.pt" and signature.get("seed") == SEED
                  and signature.get("nested") is True and signature.get("shapes") == SHAPES
                  and signature.get("dtypes") == ["torch.float32", "torch.float32"]
                  and [stream["shape"] for stream in streams] == SHAPES
                  and [stream["sha256"] for stream in streams] == NOISE_STREAM_SHA256)
            noise_signatures[run] = {"signature": signature, "streams": streams}
            storage(Path(PAIR_ID + "_noise.pt"), Counter((stream["sha256"], stream["bytes"]) for stream in streams))
        if hook:
            hooks[run] = hook
            bad, absent = validate_hook(hook, run, factor, steps, completed, metadata, layout)
            errors.extend(run + ": " + message for message in bad)
            missing.extend(run + ": " + message for message in absent)
            row["hook"] = {key: hook.get(key) for key in ("factor", "completed_calls", "completed_forward_calls", "native_override_calls", "status")}
        row["status"] = "invalid" if len(errors) > row_errors_start else "pending" if len(missing) > row_missing_start else "pass"

    if all(run in graphs for run in RUNS):
        check("formal graphs differ only run IDs/factor/output name", normalize_graph(graphs[RUNS[0]]) == normalize_graph(graphs[RUNS[1]]))
    if all(run in graphs for run in (*RUNS, BENCHMARK)):
        check("node5 exactly shared across three graphs", graphs[RUNS[0]]["5"] == graphs[RUNS[1]]["5"] == graphs[BENCHMARK]["5"])
    for label, values in (("actual condition snapshots", actual_snapshots), ("actual noise", noise_signatures)):
        if all(run in values for run in (*RUNS, BENCHMARK)):
            check(label + " equal across benchmark and formal pair", values[RUNS[0]] == values[RUNS[1]] == values[BENCHMARK])
    if all(run in hooks for run in RUNS):
        check("formal runtime sigma schedules identical", hooks[RUNS[0]].get("sample_sigmas") == hooks[RUNS[1]].get("sample_sigmas"))
    if all("start_ms" in rows[run] for run in (*RUNS, BENCHMARK)):
        check("serial benchmark then formal timelines", rows[BENCHMARK]["end_ms"] <= rows[RUNS[0]]["start_ms"]
              and rows[RUNS[0]]["end_ms"] <= rows[RUNS[1]]["start_ms"])

    runtime = read("remote_configs/runtime_provenance.json")
    known_models = read("configs/model_hashes_host41.json")
    if runtime:
        check("actual runtime host", runtime.get("actual_host", runtime.get("host")) == HOST)
        core = runtime.get("core_matches", {})
        check("actual Core matches frozen hashes", bool(core) and all(value is True for value in core.values()))
        for relative in ("extensions/H3EventEmphasis/core.py", "extensions/H3EventEmphasis/__init__.py",
                         "extensions/H3PairAudit/__init__.py", "extensions/H3EventAudit/__init__.py",
                         "scripts/backend_dispatch_audit.py", "scripts/compatibility_bootstrap.py", "scripts/service.py"):
            path = root / relative
            if path.is_file():
                check("executed code hash: " + relative, runtime.get("code", {}).get(relative) == h.sha256(path))
            else:
                missing.append(relative)
        if known_models:
            for name, expected in known_models.items():
                model = runtime.get("models", {}).get(name, {})
                check("executed model SHA: " + name, model.get("sha256", model.get("prior_full_sha256")) == expected["sha256"]
                      and model.get("bytes") == expected["bytes"] and model.get("size_mtime_match") is True)
        for filename in ("05_real_megumi_v.mp4", "elon_musk_royal_society.jpg"):
            path = root / "inputs" / filename
            if path.is_file():
                check("runtime input SHA: " + filename, runtime.get("inputs", {}).get(filename, {}).get("sha256") == h.sha256(path))
    service_pid = None
    if all(run in jobs for run in (*RUNS, BENCHMARK)):
        first = jobs[BENCHMARK]
        service_pid = first.get("service_pid")
        check("one service identity across benchmark/formal pair", service_pid is not None
              and all(jobs[run].get("service_pid") == service_pid and jobs[run].get("service_identity") == first.get("service_identity") for run in RUNS))
        service = read("processes/remote/service_" + str(service_pid) + ".json")
        if service:
            check("same bound GPU/service", service.get("pid") == service_pid and service.get("gpu_uuid") == GPU
                  and service.get("identity") == first.get("service_identity") and service.get("cache_none") is False)
            tokens = shlex.split(first["service_identity"]["cmdline"])
            if selection:
                check("runtime executable/Core", tokens[0] == selection["python"] and str(Path(selection["core"]) / "main.py") in tokens)
            check("native attention selected", "--use-pytorch-cross-attention" in tokens and "--cache-none" not in tokens)
    log = root / "logs/comfyui.log"
    runtime_log = {}
    if log.is_file():
        text = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text(errors="replace"))
        versions = sorted(set(re.findall(r"pytorch version:\s*(\S+)", text, re.IGNORECASE)))
        runtime_log = {"pytorch_versions": versions, "native_pytorch_attention_log": "Using pytorch attention" in text}
        check("single native PyTorch runtime log", len(versions) == 1 and runtime_log["native_pytorch_attention_log"])
    else:
        missing.append("logs/comfyui.log")
    traces = []
    for path in sorted((root / "logs").glob("*dispatch*.json")):
        trace = h.read_json(path)
        if trace and trace.get("schema") == "h3-backend-dispatch-audit-v1":
            traces.append((path, trace))
    dispatch = {"attribution": "Shared service process, including benchmark and both formal arms; no per-arm counter attribution."}
    if not traces:
        missing.append("logs/*dispatch*.json with actual successful backend-export calls")
    elif service_pid is None:
        missing.append("all job service identities needed to bind dispatch trace")
    else:
        matching = [(path, trace) for path, trace in traces if trace.get("pid") == service_pid]
        check("dispatch trace service PID", bool(matching))
        if matching:
            path, trace = max(matching, key=lambda item: sum(op.get("successful_calls", 0) for op in item[1].get("operations", {}).values()))
            operations = trace.get("operations", {})
            observed = {name: {key: entry.get(key) for key in ("attempted_calls", "successful_calls", "failed_calls", "first_call")}
                        for name, entry in operations.items() if entry.get("successful_calls", 0) > 0}
            check("actual backend execution observed", bool(observed)
                  and all(operations[name].get("registry_resolves_wrapper") is True for name in observed))
            check("dispatch logging healthy", not trace.get("logging_errors"))
            for name, entry in operations.items():
                counts = [entry.get(key, 0) for key in ("attempted_calls", "successful_calls", "failed_calls")]
                check("dispatch counts valid: " + name, all(type(count) is int and count >= 0 for count in counts)
                      and counts[0] >= counts[1] + counts[2])
            dispatch.update(file=str(path.relative_to(root)), pid=service_pid, observed_exports=observed,
                            count_semantics=trace.get("count_semantics"), count_freshness=trace.get("count_freshness"))
    return {"created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "invalid" if errors else "pending" if missing else "pass",
            "formal_run_ids": list(RUNS), "benchmark_excluded_from_quality": BENCHMARK,
            "formal_count_passed": sum(rows[run]["status"] == "pass" for run in RUNS),
            "runs": rows, "checks": checks, "errors": errors, "missing": sorted(set(missing)),
            "derived_layout": layout, "runtime_log": runtime_log, "backend_dispatch": dispatch,
            "independently_hashed_storage_files": len(storage_cache),
            "noise_cache_sha256_expected": NOISE_FILE_SHA256,
            "evidence_limits": [
                "A passing archive verifies this pair's controls and completed media, not motion preservation or general efficacy.",
                "The two-step benchmark is technical warmup and shared-conditioning construction, excluded from formal quality comparisons.",
                "Dispatch counters prove successful registered exports in the shared process; they include benchmark work and nested delegation, not disjoint layers or per-arm counts.",
                "Snapshot hashes cover actual embedding, token tags, clean reference latents and position IDs; target tensors are checked by shape/dtype and cached object reuse, not a separate target-content hash.",
                "Saved ZIP storages are independently hashed without pickle execution; unsaved tensors rely on runtime hash records and verified snapshot code.",
                "Manual event bins cover47–67 even though the requested source interval is50–65; all spatial content in these bins is emphasized."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = validate(args.root)
    except Exception as error:
        result = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid",
                  "errors": [type(error).__name__ + ": " + str(error)], "missing": []}
    directory = args.root / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pair_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    report = ["Musk same-host factor1/factor3 pair verification", "Status: " + result["status"],
              "Formal videos: " + ", ".join(RUNS), "Technical benchmark excluded: " + BENCHMARK,
              "Errors: " + str(len(result["errors"])), *["  " + item for item in result["errors"]],
              "Pending evidence: " + str(len(result["missing"])), *["  " + item for item in result["missing"]],
              "", *result.get("evidence_limits", [])]
    (directory / "pair_verification.txt").write_text("\n".join(report) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"], "missing_count": len(result["missing"]),
                      "report": str(directory / "pair_verification.json")}))
    raise SystemExit(0 if result["status"] == "pass" else 2 if result["status"] == "pending" else 1)


if __name__ == "__main__":
    main()
