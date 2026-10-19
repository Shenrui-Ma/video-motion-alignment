#!/usr/bin/env python3
"""CPU-only factor3 archive verification; never load pickle or contact a server.

Writes only analysis/factor3_validation.json under --root.
Exit 0: pass, 2: evidence pending, 1: invalid evidence.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sys


RUN = "06_seed2_emphasis3"
OLD_RUNS = ("06_seed2_baseline", "06_seed2_emphasis2")
OLD_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-pilot-20261013")
CONDITION_FIELDS = ("input_video", "native_vae_calls", "qwen_presentation",
                    "tokenization_before_vision_expansion", "conditioning_embedding",
                    "token_tags", "target_latent_shapes", "packed_layout", "prompt")
EXPECTED_VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}


def load_helpers(old_root):
    # Importing the sealed script must not create __pycache__ in its directory.
    sys.dont_write_bytecode = True
    path = old_root / "scripts/verify_pair.py"
    spec = importlib.util.spec_from_file_location("sealed_pair_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_graph(graph, helpers):
    result = helpers.normalize_graph(graph)
    for node in result.values():
        if node["class_type"] in {"H3EventAuditReference", "H3EventAuditNoise", "H3EventEmphasis"}:
            node["inputs"].pop("audit_dir", None)
    return result


def validate_hook(hook, completed, old_hook):
    """Incomplete counts are pending; contradictions and malformed final counts fail."""
    errors, missing = [], []
    fixed = {"run_id": RUN, "factor": 3, "expected_num_blocks": 50,
             "formal_planned_sampling_steps": 20, "pixel_interval_inclusive": [39, 44]}
    for key, value in fixed.items():
        if hook.get(key) != value:
            errors.append("hook " + key + " differs from expected")
    if hook.get("status") == "failed" or hook.get("error"):
        errors.append("hook reports failure")
    final = {"expected_sampling_steps": 20, "started_calls": 1000,
             "completed_calls": 1000, "completed_forward_calls": 20,
             "calls_by_block": [20] * 50, "calls_by_forward": [50] * 20,
             "native_override_calls": 1000}
    if completed:
        for key, value in final.items():
            if hook.get(key) != value:
                errors.append("final hook " + key + " differs from expected")
    else:
        missing.append("final hook audit after successful completed formal history")
        if hook.get("expected_sampling_steps") not in (None, 20):
            errors.append("hook sampling schedule is not 20 steps")
    layout = hook.get("validated_layout")
    if not layout:
        (errors if completed else missing).append("validated hook layout")
    else:
        expected = {"seq_len": 87583, "latent_interval_half_open": [12, 14],
                    "pixel_interval_inclusive": [39, 44], "position_bin_coverage_inclusive": [39, 46],
                    "key_interval_half_open": [19217, 21103],
                    "query_interval_half_open": [59293, 61179], "frame_rows": 943,
                    "reference_kind": "video", "reference_index": 1}
        for key, value in expected.items():
            if layout.get(key) != value:
                errors.append("hook layout " + key + " differs from expected")
        if old_hook and layout != old_hook.get("validated_layout"):
            errors.append("complete hook layout differs from archived factor2")
    diag = hook.get("first_attention_diagnostics")
    if not diag:
        (errors if completed else missing).append("first attention diagnostics")
    else:
        expected = {"selected_keys": 1886, "selected_queries": 1886,
                    "appended_event_copies": 2, "added_kv_rows": 3772,
                    "kv_length_after_duplication": 91355, "mask": None,
                    "qkv_shape": [1, 56, 87583, 128], "dtype": "torch.bfloat16",
                    "native_function": "comfy.ldm.modules.attention.attention_pytorch"}
        for key, value in expected.items():
            if key not in diag or diag[key] != value:
                errors.append("attention diagnostic " + key + " differs from expected")
        bias = diag.get("logit_bias_equivalent")
        if not isinstance(bias, (int, float)) or not math.isclose(bias, math.log(3), rel_tol=0, abs_tol=1e-12):
            errors.append("attention logit bias is not ln(3)")
        for key in ("key_slice_stats", "value_slice_stats", "query_slice_stats",
                    "weighted_output_slice_stats", "weighted_vs_native_output_sample"):
            if diag.get(key, {}).get("finite") is not True:
                errors.append("attention diagnostic " + key + " is missing or nonfinite")
        memory = diag.get("memory_estimate", {})
        expected_memory = {"kv_concat_tensors_bytes": 2619330560,
                           "duplicated_kv_rows_bytes": 108150784,
                           "selected_query_output_bytes": 27037696}
        for key, value in expected_memory.items():
            if memory.get(key) != value:
                errors.append("attention memory arithmetic " + key + " differs from expected")
    if old_hook and hook.get("sample_sigmas") != old_hook.get("sample_sigmas"):
        if completed or "sample_sigmas" in hook:
            errors.append("runtime sigma schedule differs from archived factor2")
    return errors, missing


def validate(root, old_root):
    helpers = load_helpers(old_root)
    errors, missing, checks = [], [], {}
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "run_id": RUN,
              "factor": 3, "comparison_archive": str(old_root),
              "comparison_run_ids": list(OLD_RUNS), "technical_outputs_excluded": True}

    def required(relative):
        value = helpers.read_json(root / relative)
        if value is None:
            missing.append(relative)
        return value

    def check(name, equal):
        checks[name] = bool(equal)
        if not equal:
            errors.append("mismatch: " + name)

    # This calls only the sealed verifier's read-only function, never its main/write path.
    old_validation = helpers.validate(old_root)
    result["comparison_archive_validation"] = {
        key: old_validation.get(key) for key in
        ("status", "formal_count_passed", "independently_hashed_tensor_storage_files", "errors", "missing")}
    errors.extend("comparison archive: " + item for item in old_validation.get("errors", []))
    missing.extend("comparison archive: " + item for item in old_validation.get("missing", []))
    old_graphs = {run: helpers.read_json(old_root / "configs" / (run + ".json")) for run in OLD_RUNS}
    old_conditions = {run: helpers.read_json(old_root / "audit" / (run + "_conditioning.json")) for run in OLD_RUNS}
    old_noises = {run: helpers.read_json(old_root / "audit" / (run + "_noise.json")) for run in OLD_RUNS}
    old_hook = helpers.read_json(old_root / "audit/emphasis/06_seed2_emphasis2.json")

    for filename in ("06_anime_eye_insert.mp4", "firefly_neutral_reference.png"):
        source = root / "inputs" / filename
        reference = old_root / "inputs" / filename
        if not source.is_file():
            missing.append(str(source.relative_to(root)))
        elif not reference.is_file():
            missing.append("comparison archive input: " + filename)
        else:
            check("input_file_identical:" + filename, helpers.sha256(source) == helpers.sha256(reference))
            if source.suffix == ".mp4":
                check("source_video_geometry", helpers.probe(source) == EXPECTED_VIDEO)

    graph = required("configs/" + RUN + ".json")
    job = required("logs/" + RUN + "_job.json")
    history = required("logs/" + RUN + "_history.json")
    condition = required("audit/" + RUN + "_conditioning.json")
    noise = required("audit/" + RUN + "_noise.json")
    hook = required("audit/emphasis/" + RUN + ".json")
    completed = False
    if graph:
        sink, output_node = helpers.one_node(graph, "SaveVideo")
        _, ref = helpers.one_node(graph, "H3EventAuditReference")
        _, noise_node = helpers.one_node(graph, "H3EventAuditNoise")
        _, intervention = helpers.one_node(graph, "H3EventEmphasis")
        _, sigmas = helpers.one_node(graph, "ManualSigmas")
        check("graph_run_ids_factor_output_name",
              output_node["filename_prefix"] == RUN and intervention["factor"] == 3
              and all(node["run_id"] == RUN for node in (ref, noise_node, intervention)))
        check("graph_event_window", (intervention["start_frame"], intervention["end_frame"]) == (39, 44))
        check("graph_seed_and_steps", noise_node["noise_seed"] == 2026101312 and len(sigmas["sigmas"].split(",")) == 21)
        check("graph_audit_paths", Path(ref["audit_dir"]).is_absolute()
              and noise_node["audit_dir"] == ref["audit_dir"]
              and Path(intervention["audit_dir"]) == Path(ref["audit_dir"]) / "emphasis")
        for run, old_graph in old_graphs.items():
            if old_graph:
                check("graph_only_factor_paths_run_id_output_differ:" + run,
                      normalize_graph(graph, helpers) == normalize_graph(old_graph, helpers))
            else:
                missing.append("comparison graph: " + run)
        if job:
            check("job_graph_sha256", job.get("graph_sha256") == helpers.sha256(root / "configs" / (RUN + ".json")))
            check("job_run_name", job.get("name") == RUN)
            if job.get("status") in ("error", "failed"):
                errors.append("job reports failure")
            elif job.get("status") != "success":
                missing.append("successful job status")
        if history:
            if "status" not in history and len(history) == 1:
                history = next(iter(history.values()))
            prompt = history.get("prompt", [])
            check("history_graph", len(prompt) >= 3 and prompt[2] == graph)
            if job:
                check("job_history_prompt_id", len(prompt) >= 2 and prompt[1] == job.get("prompt_id"))
            status = history.get("status", {})
            messages = status.get("messages", [])
            if status.get("status_str") in ("error", "failed") or any(m[0] == "execution_error" for m in messages):
                errors.append("history reports failure")
            starts = [m[1]["timestamp"] for m in messages if m[0] == "execution_start"]
            ends = [m[1]["timestamp"] for m in messages if m[0] == "execution_success"]
            completed = status.get("status_str") == "success" and status.get("completed") is True and bool(starts and ends)
            if completed:
                result["execution_seconds"] = (max(ends) - max(starts)) / 1000
                check("positive_execution_duration", result["execution_seconds"] > 0)
                artifacts = history.get("outputs", {}).get(sink, {}).get("images", [])
                videos = [a for a in artifacts if a.get("type") == "output" and a.get("filename", "").endswith(".mp4")]
                check("formal_history_output", len(videos) == 1
                      and videos[0].get("filename") == RUN + "_00001_.mp4" and not videos[0].get("subfolder"))
            else:
                missing.append("successful completed formal history with execution timestamps")
        if condition:
            check("conditioning_run_and_prompt", condition.get("run_id") == RUN and condition.get("prompt") == ref["prompt"])
        if noise:
            check("noise_run_and_pair", noise.get("run_id") == RUN and noise.get("pair_id") == noise_node["pair_id"])

    output = root / "outputs" / (RUN + "_00001_.mp4")
    if output.is_file():
        result["output_file"] = str(output.relative_to(root))
        result["output_sha256"] = helpers.sha256(output)
        result["video_probe"] = helpers.probe(output)
        check("raw_output_geometry", result["video_probe"] == EXPECTED_VIDEO)
    else:
        missing.append(str(output.relative_to(root)))

    storage_cache = {}
    def check_storage(path, wanted):
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            return
        if path not in storage_cache:
            storage_cache[path] = helpers.raw_storages(path)
        check("raw_tensor_storage:" + str(path.relative_to(root)), storage_cache[path] == wanted)

    if condition:
        for run, previous in old_conditions.items():
            if previous:
                for field in CONDITION_FIELDS:
                    check(field + "_identical:" + run, helpers.canonical(condition[field]) == helpers.canonical(previous[field]))
            else:
                missing.append("comparison conditioning: " + run)
        # Identical metadata alone does not prove that the actual saved tensors were collected.
        for call in condition["native_vae_calls"]:
            if any("tensor_file" not in call[key] for key in ("prepared_frames", "latent")):
                errors.append("clean prepared/reference tensors lack archived storage records")
        for presentation in condition["qwen_presentation"]:
            if presentation.get("type") == "video" and "tensor_file" not in presentation["actual_sampled_frames"]:
                errors.append("Qwen sampled video frames lack archived storage record")
        for record in helpers.tensor_records(condition):
            relative = Path(record["tensor_file"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe tensor-file path")
            signature = helpers.signature(record)
            check_storage(root / "audit" / relative, Counter({(signature["sha256"], signature["bytes"]): 1}))
    if noise:
        streams = [helpers.signature(stream) for stream in noise["actual_noise_streams"]]
        check("actual_noise_seed", noise["signature"].get("seed") == 2026101312)
        for run, previous in old_noises.items():
            if previous:
                check("noise_signature_identical:" + run, noise["signature"] == previous["signature"])
                check("actual_noise_streams_identical:" + run,
                      streams == [helpers.signature(stream) for stream in previous["actual_noise_streams"]])
            else:
                missing.append("comparison noise: " + run)
        check_storage(root / "audit" / Path(noise["cache_file"]).name,
                      Counter((stream["sha256"], stream["bytes"]) for stream in streams))
    if hook:
        hook_errors, hook_missing = validate_hook(hook, completed, old_hook)
        errors.extend(hook_errors)
        missing.extend(hook_missing)
        result["hook"] = {key: hook.get(key) for key in ("factor", "status", "expected_sampling_steps",
                          "completed_calls", "completed_forward_calls", "native_override_calls")}

    result.update(status="invalid" if errors else "pending" if missing else "pass",
                  comparison_checks=checks, errors=errors, missing=sorted(set(missing)),
                  independently_hashed_new_tensor_storage_files=len(storage_cache),
                  evidence_limits=[
                      "No torch import or pickle deserialization; saved ZIP tensor storage bytes are independently hashed.",
                      "Unsaved conditioning/token tensors are compared using runtime-recorded SHA256 only.",
                      "Augmented reference equality is inferred from equal clean latents, seed and native runtime; augmented tensors were not directly archived.",
                      "This verifies controls and completed media, not whether the short action was repaired.",
                      "Hook memory fields are tensor-storage arithmetic, not measured peak GPU memory."])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--old-root", type=Path, default=OLD_ROOT)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.old_root)
    except Exception as error:
        result = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid", "run_id": RUN,
                  "errors": [type(error).__name__ + ": " + str(error)], "missing": []}
    destination = args.root / "analysis/factor3_validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The verifier's sole output is this report; do not mutate either experiment's evidence.
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"],
                      "missing_count": len(result["missing"]), "report": str(destination)}))
    raise SystemExit(1 if result["status"] == "invalid" else 2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
