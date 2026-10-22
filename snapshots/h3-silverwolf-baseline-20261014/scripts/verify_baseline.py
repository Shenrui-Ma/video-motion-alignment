#!/usr/bin/env python3
"""Read-only CPU baseline verification; sole output: analysis/baseline_validation.json.

Exit 0 = pass, 2 = pending, 1 = invalid evidence, 3 = valid artifacts with
runtime/numerical differences limiting causal comparison. No torch/pickle/server execution.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import sys


RUN = "06_silverwolf_seed2_baseline"
PARENT_RUN = "06_silverwolf_seed2_emphasis3"
PARENT_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-silverwolf-20261014")
CODE_FILES = ("extensions/H3EventEmphasis/core.py", "extensions/H3EventEmphasis/__init__.py")
NOISE_FILE = "06_anime_eye_insert_s2_noise.pt"
EXPECTED_VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}
NATIVE_PATH = "original_block with original transformer_options and native Attention.forward"


def load_parent(parent_root):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("silverwolf_parent_verifier", parent_root / "scripts/verify_silverwolf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_hook(hook, condition, completed, parent_hook, parent):
    errors, missing = [], []
    expected = {"run_id": RUN, "factor": 1, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "pixel_interval_inclusive": [39, 44],
                "factor_1_path": NATIVE_PATH, "native_override_calls": 0}
    if completed:
        expected.update(expected_sampling_steps=20, started_calls=1000, completed_calls=1000,
                        completed_forward_calls=20, calls_by_block=[20] * 50, calls_by_forward=[50] * 20)
    else:
        missing.append("final factor1 hook after successful formal history")
        if hook.get("expected_sampling_steps") not in (None, 20):
            errors.append("factor1 hook sampling steps differ from 20")
    for key, value in expected.items():
        if hook.get(key) != value:
            errors.append("factor1 hook " + key + " differs from expected")
    if "first_attention_diagnostics" in hook:
        errors.append("factor1 hook unexpectedly recorded an attention override")
    if hook.get("status") == "failed" or hook.get("error"):
        errors.append("factor1 hook reports failure")
    if parent_hook and (completed or "sample_sigmas" in hook) and hook.get("sample_sigmas") != parent_hook.get("sample_sigmas"):
        errors.append("runtime sigma schedule differs from SilverWolf factor3")
    if condition:
        metadata, layout = parent.derive_layout(condition)
        if hook.get("metadata") != metadata:
            errors.append("factor1 hook metadata differs from actual conditioning")
        if hook.get("validated_layout"):
            if hook["validated_layout"] != layout:
                errors.append("factor1 hook layout differs from independently derived dynamic bounds")
        else:
            (errors if completed else missing).append("validated factor1 dynamic layout")
    else:
        missing.append("conditioning required to independently derive factor1 hook bounds")
    return errors, missing


def runtime_evidence(root, job, helpers):
    """Read actual evidence; a copied parent provenance or preferred host is not execution evidence."""
    missing, errors = [], []
    records = [(relative, helpers.read_json(root / relative)) for relative in
               ("remote_configs/runtime_provenance.json", "configs/runtime_provenance.json")]
    records = [(relative, value) for relative, value in records if value is not None]
    provenance = records[0][1] if records else None
    if not provenance:
        missing.append("collected actual runtime_provenance.json")
    selection = helpers.read_json(root / "configs/runtime_selection.json") or {}
    plan = helpers.read_json(root / "configs/plan.json") or {}
    hosts = {value for value in ((provenance or {}).get("host"), selection.get("host"), plan.get("actual_host")) if value}
    if len(hosts) > 1:
        errors.append("conflicting actual host records")
    elif not hosts:
        missing.append("actual runtime host (runtime_selection.host, provenance.host or plan.actual_host)")
    identity = {"host": next(iter(hosts)) if len(hosts) == 1 else None}
    log = root / "logs/comfyui.log"
    if log.is_file():
        text = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text(errors="replace"))
        patterns = {"pytorch": r"pytorch version:\s*(\S+)", "python": r"Python version:\s*(\S+)",
                    "comfyui": r"ComfyUI version:\s*(\S+)", "triton": r"Found triton (\S+)\. Enabling",
                    "gpu_model": r"Device: cuda:\d+ (.+?)\s*:\s*native"}
        for key, pattern in patterns.items():
            values = set(re.findall(pattern, text, re.IGNORECASE))
            if len(values) == 1:
                identity[key] = next(iter(values))
            elif not values:
                missing.append("runtime log version/device evidence: " + key)
            else:
                errors.append("multiple incompatible runtime log values: " + key)
        identity["native_pytorch_attention"] = "Using pytorch attention" in text
        if not identity["native_pytorch_attention"]:
            errors.append("runtime log does not confirm native PyTorch attention")
    else:
        missing.append("logs/comfyui.log")
    command = (job or {}).get("service_identity", {}).get("cmdline")
    if command:
        tokens = shlex.split(command)
        identity["python_path"] = tokens[0]
        core = [token for token in tokens if token.endswith("/ComfyUI/main.py")]
        if len(core) != 1:
            errors.append("job command does not identify exactly one ComfyUI Core")
        else:
            identity["core_main_path"] = core[0]
        if "--models-directory" not in tokens:
            errors.append("job command lacks model directory")
        else:
            identity["models_path"] = tokens[tokens.index("--models-directory") + 1]
        relevant = {"--disable-dynamic-vram", "--disable-cuda-malloc", "--use-pytorch-cross-attention",
                    "--enable-triton-backend", "--highvram", "--lowvram", "--novram", "--cache-none",
                    "--use-sage-attention", "--use-flash-attention"}
        identity["backend_memory_flags"] = sorted(relevant.intersection(tokens))
        if "--use-pytorch-cross-attention" not in tokens or "--enable-triton-backend" not in tokens:
            errors.append("job command lacks required native SDPA/Triton backend flags")
    else:
        missing.append("actual job service command")
    return {"identity": identity, "provenance": provenance,
            "provenance_file": records[0][0] if records else None}, errors, missing


def compare_runtime(current, previous):
    """Return explicit confounds, not a misleading success when hosts/runtimes differ."""
    left, right = current["identity"], previous["identity"]
    return [{"field": key, "baseline": left[key], "factor3": right[key]}
            for key in sorted(left.keys() & right.keys())
            if left[key] is not None and right[key] is not None and left[key] != right[key]]


def comparison_record(current, previous, helpers):
    """Record a content difference without misclassifying numerical drift as failed execution."""
    left, right = helpers.canonical(current), helpers.canonical(previous)
    def summary(value):
        if isinstance(value, dict) and {"sha256", "shape", "dtype"} <= value.keys():
            return value
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        return {"canonical_record_sha256": hashlib.sha256(data).hexdigest()}
    return {"identical": left == right, "baseline": summary(left), "factor3": summary(right)}


def comparison_status(errors, missing, differences):
    artifact = "invalid" if errors else "pending" if missing else "pass"
    return artifact, artifact if artifact != "pass" else "limited" if differences else "pass"


def validate(root, parent_root):
    parent = load_parent(parent_root)
    factor3 = parent.load_parent(parent.PARENT_ROOT)
    helpers = factor3.load_helpers(factor3.OLD_ROOT)
    errors, missing, checks, comparisons = [], [], {}, {}
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "run_id": RUN,
              "factor": 1, "parent_archive": str(parent_root), "parent_run_id": PARENT_RUN}
    def required(relative):
        value = helpers.read_json(root / relative)
        if value is None:
            missing.append(relative)
        return value
    def check(name, equal):
        checks[name] = bool(equal)
        if not equal:
            errors.append("mismatch: " + name)
    def compare(stage, name, current, previous):
        comparisons.setdefault(stage, {})[name] = comparison_record(current, previous, helpers)
    parent_validation = parent.validate(parent_root, parent.PARENT_ROOT)
    result["factor3_archive_validation"] = {key: parent_validation.get(key) for key in ("status", "errors", "missing")}
    errors.extend("factor3 archive: " + message for message in parent_validation.get("errors", []))
    missing.extend("factor3 archive: " + message for message in parent_validation.get("missing", []))
    previous_graph = helpers.read_json(parent_root / "configs" / (PARENT_RUN + ".json"))
    previous_condition = helpers.read_json(parent_root / "audit" / (PARENT_RUN + "_conditioning.json"))
    previous_noise = helpers.read_json(parent_root / "audit" / (PARENT_RUN + "_noise.json"))
    previous_hook = helpers.read_json(parent_root / "audit/emphasis" / (PARENT_RUN + ".json"))
    previous_job = helpers.read_json(parent_root / "logs" / (PARENT_RUN + "_job.json"))
    local_code_hashes = {}
    for relative in CODE_FILES:
        path = root / relative
        old = parent_root / relative
        if path.is_file() and old.is_file():
            local_code_hashes[relative] = helpers.sha256(path)
            check("unchanged_attention_code:" + relative, local_code_hashes[relative] == helpers.sha256(old))
        else:
            missing.append("baseline and factor3 code: " + relative)
    for name in ("06_anime_eye_insert.mp4", "silverwolf_reference.png"):
        path = root / "inputs" / name
        if path.is_file():
            check("input_file_identical:" + name, helpers.sha256(path) == helpers.sha256(parent_root / "inputs" / name))
            if path.suffix == ".mp4":
                check("source_video_geometry", helpers.probe(path) == EXPECTED_VIDEO)
        else:
            missing.append(str(path.relative_to(root)))
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
        check("graph_factor1_run_identity", intervention["factor"] == 1 and output_node["filename_prefix"] == RUN
              and all(node["run_id"] == RUN for node in (ref, noise_node, intervention)))
        check("graph_audit_paths", Path(ref["audit_dir"]).is_absolute() and noise_node["audit_dir"] == ref["audit_dir"]
              and Path(intervention["audit_dir"]) == Path(ref["audit_dir"]) / "emphasis")
        if previous_graph:
            check("graph_only_factor_paths_ids_differ", factor3.normalize_graph(graph, helpers) == factor3.normalize_graph(previous_graph, helpers))
        else:
            missing.append("factor3 formal graph")
        if job:
            check("job_identity_and_graph_hash", job.get("name") == RUN
                  and job.get("graph_sha256") == helpers.sha256(root / "configs" / (RUN + ".json")))
            if job.get("status") in ("error", "failed"):
                errors.append("baseline job reports failure")
            elif job.get("status") != "success":
                missing.append("successful baseline job status")
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
                errors.append("baseline history reports failure")
            starts = [m[1]["timestamp"] for m in messages if m[0] == "execution_start"]
            ends = [m[1]["timestamp"] for m in messages if m[0] == "execution_success"]
            completed = status.get("status_str") == "success" and status.get("completed") is True and bool(starts and ends)
            if completed:
                result["execution_seconds"] = (max(ends) - max(starts)) / 1000
                check("positive_execution_duration", result["execution_seconds"] > 0)
                videos = [a for a in history.get("outputs", {}).get(sink, {}).get("images", [])
                          if a.get("type") == "output" and a.get("filename", "").endswith(".mp4")]
                check("formal_history_output", len(videos) == 1 and videos[0].get("filename") == RUN + "_00001_.mp4"
                      and not videos[0].get("subfolder"))
            else:
                missing.append("successful completed baseline history with timestamps")
        if condition:
            check("conditioning_run_and_prompt", condition.get("run_id") == RUN and condition.get("prompt") == ref["prompt"])
        if noise:
            check("noise_run_and_pair", noise.get("run_id") == RUN and noise.get("pair_id") == noise_node["pair_id"])
    output = root / "outputs" / (RUN + "_00001_.mp4")
    if output.is_file():
        result.update(output_file=str(output.relative_to(root)), output_sha256=helpers.sha256(output), video_probe=helpers.probe(output))
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
        check("raw_storage:" + str(path.relative_to(root)), storage_cache[path] == wanted)
    if condition:
        _, layout = parent.derive_layout(condition)
        result["derived_runtime_layout"] = layout
        packed = condition["packed_layout"]
        check("conditioning_own_dynamic_layout", packed["seq_len"] == layout["seq_len"]
              and packed["segments"] == layout["segments"])
        check("conditioning_own_position_geometry", packed["position_ids"]["shape"] == [layout["seq_len"], 3]
              and packed["position_ids"]["dtype"] == "torch.float64")
        check("decoded_source_video_geometry", condition["input_video"]["shape"] == [141, 736, 1312, 3])
        if previous_condition:
            check("conditioning_prompt_identical", condition["prompt"] == previous_condition["prompt"])
            check("target_latent_shapes_identical", condition["target_latent_shapes"] == previous_condition["target_latent_shapes"])
            image, video = parent.reference_calls(condition)
            previous_image, previous_video = parent.reference_calls(previous_condition)
            compare("input_preprocessing", "decoded_source_video", condition["input_video"], previous_condition["input_video"])
            for name, current_call, previous_call in (("source_video", video, previous_video),
                                                      ("reference_image", image, previous_image)):
                compare("input_preprocessing", name + "_prepared_frames", current_call["prepared_frames"], previous_call["prepared_frames"])
                compare("clean_vae_latents", name, current_call["latent"], previous_call["latent"])
            for field in ("qwen_presentation", "tokenization_before_vision_expansion",
                          "conditioning_embedding", "token_tags", "packed_layout"):
                compare("conditioning", field, condition[field], previous_condition[field])
        else:
            missing.append("factor3 conditioning audit")
        for call in condition["native_vae_calls"]:
            if any("tensor_file" not in call[key] for key in ("prepared_frames", "latent")):
                errors.append("clean reference tensors missing storage records")
        for item in condition["qwen_presentation"]:
            if item.get("type") == "video" and "tensor_file" not in item["actual_sampled_frames"]:
                errors.append("sampled source video missing tensor storage record")
        for record in helpers.tensor_records(condition):
            relative = Path(record["tensor_file"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe tensor-file path")
            signature = helpers.signature(record)
            check_storage(root / "audit" / relative, Counter({(signature["sha256"], signature["bytes"]): 1}))
    cache, parent_cache = root / "audit" / NOISE_FILE, parent_root / "audit" / NOISE_FILE
    if cache.is_file() and parent_cache.is_file():
        check("actual_noise_cache_byte_identical", helpers.sha256(cache) == helpers.sha256(parent_cache))
    else:
        missing.append("baseline and factor3 actual noise cache files")
    if noise:
        streams = [helpers.signature(stream) for stream in noise["actual_noise_streams"]]
        check("noise_seed_and_cache_name", noise["signature"].get("seed") == 2026101312 and Path(noise["cache_file"]).name == NOISE_FILE)
        if previous_noise:
            check("noise_signature_identical", noise["signature"] == previous_noise["signature"])
            check("actual_noise_streams_identical", streams == [helpers.signature(stream) for stream in previous_noise["actual_noise_streams"]])
        else:
            missing.append("factor3 noise audit")
        check_storage(cache, Counter((stream["sha256"], stream["bytes"]) for stream in streams))
    if hook:
        hook_errors, hook_missing = validate_hook(hook, condition, completed, previous_hook, parent)
        errors.extend(hook_errors)
        missing.extend(hook_missing)
        result["hook"] = {key: hook.get(key) for key in ("factor", "status", "completed_calls", "completed_forward_calls", "native_override_calls")}

    current_runtime, runtime_errors, runtime_missing = runtime_evidence(root, job, helpers)
    previous_runtime, previous_errors, previous_missing = runtime_evidence(parent_root, previous_job, helpers)
    errors.extend(runtime_errors + ["factor3 runtime: " + message for message in previous_errors])
    missing.extend(runtime_missing + ["factor3 runtime: " + message for message in previous_missing])
    runtime_mismatches = compare_runtime(current_runtime, previous_runtime)
    current_prov, previous_prov = current_runtime["provenance"], previous_runtime["provenance"]
    if current_prov and previous_prov:
        for relative, local_hash in local_code_hashes.items():
            check("executed_attention_code_identical:" + relative,
                  current_prov.get("code", {}).get(relative) == local_hash == previous_prov.get("code", {}).get(relative))
        for relative in ("scripts/int8_row_chunking.py", "scripts/compatibility_bootstrap.py"):
            actual_hash = current_prov.get("code", {}).get(relative)
            previous_hash = previous_prov.get("code", {}).get(relative)
            if actual_hash is None or previous_hash is None:
                missing.append("executed numerical helper hashes: " + relative)
            else:
                compare("runtime_implementation", relative, actual_hash, previous_hash)
        current_core = current_prov.get("core_sha256", current_prov.get("core_matches"))
        previous_core = previous_prov.get("core_sha256", previous_prov.get("core_matches"))
        if not current_core or not previous_core:
            missing.append("actual Core source comparison/hash evidence")
        else:
            compare("runtime_implementation", "core_source_evidence", current_core, previous_core)
        for name, old_model in previous_prov.get("models", {}).items():
            model = current_prov.get("models", {}).get(name, {})
            old_hash = old_model.get("sha256", old_model.get("prior_full_sha256"))
            actual_hash = model.get("sha256", model.get("prior_full_sha256"))
            check("model_identity:" + name, old_hash is not None and actual_hash == old_hash
                  and model.get("bytes") == old_model.get("bytes")
                  and (model.get("full_hash_recomputed") is True or model.get("size_mtime_match") is True))
    numerical_differences = [{"stage": stage, "field": field}
                             for stage, fields in comparisons.items() for field, record in fields.items()
                             if not record["identical"]]
    limitations = bool(runtime_mismatches or numerical_differences)
    artifact_status, status = comparison_status(errors, missing, limitations)
    result.update(status=status, artifact_validation_status=artifact_status,
                  causal_controls_status="invalid" if errors else "limited" if limitations else "pending" if missing else "pass",
                  errors=errors, missing=sorted(set(missing)), checks=checks,
                  runtime_comparison={"baseline": current_runtime, "factor3": previous_runtime, "mismatches": runtime_mismatches},
                  numerical_comparison=comparisons, numerical_differences=numerical_differences,
                  independently_hashed_new_tensor_storage_files=len(storage_cache),
                  evidence_limits=[
                      "Runtime/host/version or preprocessing/VAE/conditioning differences limit causal attribution, without alone invalidating a successful generated baseline.",
                      "Raw source/reference files, prompt/graph, actual AV noise, weights and factor1 attention code/path remain strict controls; mismatches are invalid evidence.",
                      "Input decoding/prepared-frame differences are reported separately from clean VAE latent and conditioning/token/layout differences.",
                      "Factor1 is checked by unchanged attention-extension source hashes, zero override calls, no override diagnostics and the original-block audit path.",
                      "Saved tensor ZIP storages are independently hashed without torch/pickle execution; unsaved conditioning/token tensors use recorded hashes.",
                      "Model identity may reuse prior full hashes with current size/mtime checks; the verifier does not rehash remote model files.",
                      "A passing pair validates controls for this example/seed; it does not establish general efficacy or a clean speed comparison."])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--parent-root", type=Path, default=PARENT_ROOT)
    args = parser.parse_args()
    try:
        result = validate(args.root, args.parent_root)
    except Exception as error:
        result = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid", "run_id": RUN,
                  "errors": [type(error).__name__ + ": " + str(error)], "missing": []}
    output = args.root / "analysis/baseline_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"],
                      "missing_count": len(result["missing"]), "report": str(output)}))
    raise SystemExit({"pass": 0, "invalid": 1, "pending": 2, "limited": 3}[result["status"]])


if __name__ == "__main__":
    main()
