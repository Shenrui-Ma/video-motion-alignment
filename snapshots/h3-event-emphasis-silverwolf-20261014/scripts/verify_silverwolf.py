#!/usr/bin/env python3
"""Read-only CPU evidence verification; writes only analysis/silverwolf_validation.json.

No torch/pickle execution, server access, or old-archive modification.
Exit 0 = pass, 2 = pending evidence, 1 = invalid evidence.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys


RUN = "06_silverwolf_seed2_emphasis3"
PARENT_RUN = "06_seed2_emphasis3"
PARENT_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-factor3-20261014")
REFERENCE_SHA256 = "c9d80713eafde0f1a2519fcaba4cd5ba363adff16cf0eed254d3485a162c8d4c"
OLD_APPEARANCE = "Preserve her recognizable silver-white hair with pale teal ends, headband and wing-shaped hair ornament, and black-and-white sleeveless dress."
NEW_APPEARANCE = "Preserve her recognizable silver-gray hair, blue-purple goggles on her head, black-and-purple cropped jacket, white-and-black cropped top, black shorts, gloves, and technology-themed belt accessories."
EXPECTED_VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}
TARGET_SHAPES = [[1, 24, 42, 46, 82], [1, 32, 2, 235]]
NOISE_FILE = "06_anime_eye_insert_s2_noise.pt"


def load_parent(parent_root):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("parent_factor3_verifier", parent_root / "scripts/verify_factor3.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_calls(condition):
    calls = condition["native_vae_calls"]
    if len(calls) != 2:
        raise ValueError("expected exactly one clean image and one clean video VAE call")
    image, video = calls
    if image["prepared_frames"]["shape"][0] != 1 or video["prepared_frames"]["shape"] != [141, 736, 1312, 3]:
        raise ValueError("unexpected clean image/video reference order or video geometry")
    if video["latent"]["shape"] != TARGET_SHAPES[0]:
        raise ValueError("reference video latent geometry changed")
    return image, video


def derive_layout(condition):
    """Independently derive bounds from this run's text and clean VAE geometry."""
    image, _ = reference_calls(condition)
    shape = image["latent"]["shape"]
    if (len(shape) != 5 or shape[:3] != [1, 24, 1]
            or any(type(n) is not int or n < 2 or n % 2 for n in shape[3:])):
        raise ValueError("invalid clean image latent geometry for 2x2 patching")
    image_h, image_w = shape[3:]
    if image["prepared_frames"]["shape"] != [1, image_h * 16, image_w * 16, 3]:
        raise ValueError("clean image prepared/latent spatial geometry disagrees")
    context = condition["conditioning_embedding"]["shape"]
    if len(context) != 3 or context[0] != 1 or context[2] != 5120 or type(context[1]) is not int or context[1] < 1:
        raise ValueError("invalid conditioning embedding geometry")
    if condition["target_latent_shapes"] != TARGET_SHAPES:
        raise ValueError("target video/audio latent geometry changed")
    text_len, image_rows, frame_rows = context[1], image_h * image_w // 4, 943
    image_start = text_len
    reference_start = image_start + image_rows
    reference_stop = reference_start + 42 * frame_rows
    target_start = reference_stop + 235 * 2
    seq_len = target_start + 42 * frame_rows
    segments = [[0, text_len, "text"], [image_start, reference_start, "ref_img"],
                [reference_start, reference_stop, "ref_img"], [reference_stop, target_start, "audio"],
                [target_start, seq_len, "video"]]
    metadata = {"text_len": text_len, "context_shape": context, "refs": [
        {"kind": "image", "index": 0, "latent_t": 1, "latent_h": image_h, "latent_w": image_w,
         "latent_shape": shape, "frame_rows": image_rows, "ref_audio_t": 0},
        {"kind": "video", "index": 1, "latent_t": 42, "latent_h": 46, "latent_w": 82,
         "latent_shape": TARGET_SHAPES[0], "frame_rows": frame_rows, "ref_audio_t": 0}]}
    layout = {"seq_len": seq_len, "segments": segments, "signature": [text_len, 42, 46, 82, 235],
              "reference_index": 1, "reference_kind": "video",
              "reference_video_segment": [reference_start, reference_stop],
              "reference_image_segments": [[image_start, reference_start]],
              "target_video_segment": [target_start, seq_len],
              "latent_interval_half_open": [12, 14], "pixel_interval_inclusive": [39, 44],
              "position_bin_coverage_inclusive": [39, 46],
              "key_interval_half_open": [reference_start + 12 * frame_rows, reference_start + 14 * frame_rows],
              "query_interval_half_open": [target_start + 12 * frame_rows, target_start + 14 * frame_rows],
              "key_first_time_coordinate": float(text_len + 66),
              "query_first_time_coordinate": float(text_len + 301), "frame_rows": frame_rows}
    return metadata, layout


def validate_hook(hook, condition, completed, parent_hook):
    errors, missing = [], []
    expected = {"run_id": RUN, "factor": 3, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "pixel_interval_inclusive": [39, 44]}
    if completed:
        expected.update(expected_sampling_steps=20, started_calls=1000, completed_calls=1000,
                        completed_forward_calls=20, calls_by_block=[20] * 50,
                        calls_by_forward=[50] * 20, native_override_calls=1000)
    else:
        missing.append("final hook after successful formal history")
        if hook.get("expected_sampling_steps") not in (None, 20):
            errors.append("hook sampling steps differ from 20")
    for key, value in expected.items():
        if hook.get(key) != value:
            errors.append("hook " + key + " differs from expected")
    if hook.get("status") == "failed" or hook.get("error"):
        errors.append("hook reports failure")
    if parent_hook and (completed or "sample_sigmas" in hook) and hook.get("sample_sigmas") != parent_hook.get("sample_sigmas"):
        errors.append("runtime sigma schedule differs from parent factor3")
    if not condition:
        missing.append("conditioning required to independently derive hook bounds")
        return errors, missing, None
    metadata, layout = derive_layout(condition)
    if hook.get("metadata") != metadata:
        errors.append("hook reference metadata differs from new clean conditioning tensors")
    actual_layout = hook.get("validated_layout")
    if actual_layout:
        if actual_layout != layout:
            errors.append("hook dynamic layout/event bounds disagree with independently derived layout")
    else:
        (errors if completed else missing).append("validated dynamic hook layout")
    diag = hook.get("first_attention_diagnostics")
    if not diag:
        (errors if completed else missing).append("first attention diagnostics")
        return errors, missing, layout
    n, m = layout["seq_len"], 1886
    expected_diag = {"selected_keys": m, "selected_queries": m, "appended_event_copies": 2,
                     "added_kv_rows": 2 * m, "kv_length_after_duplication": n + 2 * m,
                     "qkv_shape": [1, 56, n, 128], "dtype": "torch.bfloat16", "mask": None,
                     "native_function": "comfy.ldm.modules.attention.attention_pytorch"}
    for key, value in expected_diag.items():
        if key not in diag or diag[key] != value:
            errors.append("attention diagnostic " + key + " differs from dynamic expectation")
    bias = diag.get("logit_bias_equivalent")
    if not isinstance(bias, (int, float)) or not math.isclose(bias, math.log(3), rel_tol=0, abs_tol=1e-12):
        errors.append("attention bias is not ln(3)")
    for key in ("key_slice_stats", "value_slice_stats", "query_slice_stats",
                "weighted_output_slice_stats", "weighted_vs_native_output_sample"):
        if diag.get(key, {}).get("finite") is not True:
            errors.append("missing/nonfinite attention diagnostic: " + key)
    effect = diag.get("weighted_vs_native_output_sample", {})
    for key in ("max_absolute_difference", "rms_difference"):
        value = effect.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            errors.append("attention effect is missing, nonfinite or zero: " + key)
    row_bytes = 56 * 128 * 2
    memory = {"kv_concat_tensors_bytes": 2 * (n + 2 * m) * row_bytes,
              "duplicated_kv_rows_bytes": 4 * m * row_bytes,
              "selected_query_output_bytes": m * row_bytes}
    for key, value in memory.items():
        if diag.get("memory_estimate", {}).get(key) != value:
            errors.append("dynamic attention storage arithmetic mismatch: " + key)
    return errors, missing, layout


def validate(root, parent_root):
    parent = load_parent(parent_root)
    helpers = parent.load_helpers(parent.OLD_ROOT)
    errors, missing, checks, observations = [], [], {}, {}
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "run_id": RUN,
              "parent_archive": str(parent_root), "parent_run_id": PARENT_RUN}
    def required(relative):
        value = helpers.read_json(root / relative)
        if value is None:
            missing.append(relative)
        return value
    def check(name, equal):
        checks[name] = bool(equal)
        if not equal:
            errors.append("mismatch: " + name)
    parent_validation = parent.validate(parent_root, parent.OLD_ROOT)
    result["parent_archive_validation"] = {key: parent_validation.get(key) for key in ("status", "errors", "missing")}
    errors.extend("parent archive: " + message for message in parent_validation.get("errors", []))
    missing.extend("parent archive: " + message for message in parent_validation.get("missing", []))
    parent_graph = helpers.read_json(parent_root / "configs" / (PARENT_RUN + ".json"))
    parent_condition = helpers.read_json(parent_root / "audit" / (PARENT_RUN + "_conditioning.json"))
    parent_noise = helpers.read_json(parent_root / "audit" / (PARENT_RUN + "_noise.json"))
    parent_hook = helpers.read_json(parent_root / "audit/emphasis" / (PARENT_RUN + ".json"))
    source = root / "inputs/06_anime_eye_insert.mp4"
    if source.is_file():
        check("source_file_identical", helpers.sha256(source) == helpers.sha256(parent_root / "inputs/06_anime_eye_insert.mp4"))
        check("source_video_geometry", helpers.probe(source) == EXPECTED_VIDEO)
    else:
        missing.append(str(source.relative_to(root)))
    reference = root / "inputs/silverwolf_reference.png"
    if reference.is_file():
        check("selected_silverwolf_reference_sha256", helpers.sha256(reference) == REFERENCE_SHA256)
        with reference.open("rb") as stream:
            header = stream.read(24)
        check("silverwolf_reference_dimensions", header[:8] == b"\x89PNG\r\n\x1a\n"
              and len(header) == 24 and struct.unpack(">II", header[16:24]) == (1296, 2016))
    else:
        missing.append(str(reference.relative_to(root)))
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
        image_id, image_node = helpers.one_node(graph, "LoadImage")
        check("formal_graph_identity", output_node["filename_prefix"] == RUN and intervention["factor"] == 3
              and all(node["run_id"] == RUN for node in (ref, noise_node, intervention)))
        check("graph_reference_filename", image_node["image"] == "silverwolf_reference.png")
        check("event_and_noise_seed", (intervention["start_frame"], intervention["end_frame"]) == (39, 44)
              and noise_node["noise_seed"] == 2026101312)
        check("graph_audit_paths", Path(ref["audit_dir"]).is_absolute() and noise_node["audit_dir"] == ref["audit_dir"]
              and Path(intervention["audit_dir"]) == Path(ref["audit_dir"]) / "emphasis")
        if parent_graph:
            ref_id, parent_ref = helpers.one_node(parent_graph, "H3EventAuditReference")
            check("exact_appearance_sentence_only", parent_ref["prompt"].count(OLD_APPEARANCE) == 1
                  and ref["prompt"] == parent_ref["prompt"].replace(OLD_APPEARANCE, NEW_APPEARANCE))
            new_normal = parent.normalize_graph(graph, helpers)
            old_normal = parent.normalize_graph(parent_graph, helpers)
            new_normal[ref_id]["inputs"]["prompt"] = old_normal[ref_id]["inputs"]["prompt"]
            new_normal[image_id]["inputs"]["image"] = old_normal[image_id]["inputs"]["image"]
            check("graph_changes_only_reference_appearance_paths_ids", new_normal == old_normal)
        else:
            missing.append("parent formal graph")
        if job:
            check("job_identity_and_graph_hash", job.get("name") == RUN
                  and job.get("graph_sha256") == helpers.sha256(root / "configs" / (RUN + ".json")))
            if job.get("status") in ("error", "failed"):
                errors.append("job reports failure")
            elif job.get("status") != "success":
                missing.append("successful formal job status")
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
                errors.append("formal history reports failure")
            starts = [m[1]["timestamp"] for m in messages if m[0] == "execution_start"]
            ends = [m[1]["timestamp"] for m in messages if m[0] == "execution_success"]
            completed = status.get("status_str") == "success" and status.get("completed") is True and bool(starts and ends)
            if completed:
                result["execution_seconds"] = (max(ends) - max(starts)) / 1000
                check("positive_execution_duration", result["execution_seconds"] > 0)
                artifacts = history.get("outputs", {}).get(sink, {}).get("images", [])
                videos = [a for a in artifacts if a.get("type") == "output" and a.get("filename", "").endswith(".mp4")]
                check("formal_history_output", len(videos) == 1 and videos[0].get("filename") == RUN + "_00001_.mp4"
                      and not videos[0].get("subfolder"))
            else:
                missing.append("successful completed formal history with timestamps")
        if condition:
            check("conditioning_run_and_prompt", condition.get("run_id") == RUN and condition.get("prompt") == ref["prompt"])
        if noise:
            check("noise_run_and_pair", noise.get("run_id") == RUN and noise.get("pair_id") == noise_node["pair_id"])
    output = root / "outputs" / (RUN + "_00001_.mp4")
    if output.is_file():
        result["output_sha256"] = helpers.sha256(output)
        result["video_probe"] = helpers.probe(output)
        result["output_file"] = str(output.relative_to(root))
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
        metadata, layout = derive_layout(condition)
        packed = condition["packed_layout"]
        check("conditioning_dynamic_packed_layout", packed["seq_len"] == layout["seq_len"] and packed["segments"] == layout["segments"])
        check("position_id_geometry", packed["position_ids"]["shape"] == [layout["seq_len"], 3]
              and packed["position_ids"]["dtype"] == "torch.float64")
        image, video = reference_calls(condition)
        image_presentations = [item for item in condition["qwen_presentation"] if item.get("type") == "image"]
        video_presentations = [item for item in condition["qwen_presentation"] if item.get("type") == "video"]
        check("qwen_reference_counts", len(image_presentations) == 1 and len(video_presentations) == 1)
        if len(image_presentations) == 1:
            check("qwen_image_matches_new_prepared_image", helpers.canonical(image_presentations[0]["data"]["tensor"])
                  == helpers.canonical(image["prepared_frames"]))
        if parent_condition:
            parent_image, parent_video = reference_calls(parent_condition)
            check("decoded_source_video_identical", helpers.canonical(condition["input_video"]) == helpers.canonical(parent_condition["input_video"]))
            check("clean_video_prepared_and_vae_identical", helpers.canonical(video) == helpers.canonical(parent_video))
            check("clean_reference_image_changed", helpers.canonical(image) != helpers.canonical(parent_image))
            observations.update(conditioning_embedding_changed=helpers.canonical(condition["conditioning_embedding"]) != helpers.canonical(parent_condition["conditioning_embedding"]),
                                qwen_presentation_changed=helpers.canonical(condition["qwen_presentation"]) != helpers.canonical(parent_condition["qwen_presentation"]),
                                new_image_latent_shape=image["latent"]["shape"], new_text_len=metadata["text_len"])
            old_video_presentations = [item for item in parent_condition["qwen_presentation"] if item.get("type") == "video"]
            check("qwen_source_video_frames_unchanged", helpers.canonical(video_presentations) == helpers.canonical(old_video_presentations))
        else:
            missing.append("parent conditioning audit")
        for call in condition["native_vae_calls"]:
            if any("tensor_file" not in call[key] for key in ("prepared_frames", "latent")):
                errors.append("clean reference tensors missing storage records")
        for item in video_presentations:
            if "tensor_file" not in item["actual_sampled_frames"]:
                errors.append("Qwen sampled source video missing storage record")
        for record in helpers.tensor_records(condition):
            relative = Path(record["tensor_file"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe tensor-file path")
            signature = helpers.signature(record)
            check_storage(root / "audit" / relative, Counter({(signature["sha256"], signature["bytes"]): 1}))
    cache = root / "audit" / NOISE_FILE
    parent_cache = parent_root / "audit" / NOISE_FILE
    if cache.is_file() and parent_cache.is_file():
        check("actual_noise_cache_file_byte_identical", helpers.sha256(cache) == helpers.sha256(parent_cache))
    else:
        missing.append("new and parent actual noise cache files")
    if noise:
        streams = [helpers.signature(stream) for stream in noise["actual_noise_streams"]]
        check("actual_noise_seed", noise["signature"].get("seed") == 2026101312)
        check("noise_cache_filename", Path(noise["cache_file"]).name == NOISE_FILE)
        if parent_noise:
            check("noise_signature_identical", noise["signature"] == parent_noise["signature"])
            check("actual_noise_streams_identical", streams == [helpers.signature(stream) for stream in parent_noise["actual_noise_streams"]])
        else:
            missing.append("parent noise audit")
        check_storage(cache, Counter((stream["sha256"], stream["bytes"]) for stream in streams))
    if hook:
        hook_errors, hook_missing, layout = validate_hook(hook, condition, completed, parent_hook)
        errors.extend(hook_errors)
        missing.extend(hook_missing)
        result["derived_runtime_layout"] = layout
        result["hook"] = {key: hook.get(key) for key in ("factor", "status", "completed_calls", "completed_forward_calls", "native_override_calls")}
    result.update(status="invalid" if errors else "pending" if missing else "pass", errors=errors,
                  missing=sorted(set(missing)), checks=checks, observations=observations,
                  independently_hashed_new_tensor_storage_files=len(storage_cache),
                  evidence_limits=[
                      "No SilverWolf factor1 control exists: this single rerun cannot attribute event preservation to weighting alone.",
                      "The character reference and its exact appearance sentence changed; image/Qwen/conditioning equality to Firefly is not required.",
                      "Bounds derive from this run's conditioning embedding and clean reference latent geometry, not Firefly's absolute token indices.",
                      "Saved raw tensor ZIP storages are independently hashed without torch or pickle execution; unsaved tensors use runtime-recorded hashes.",
                      "Finite nonzero first-attention output difference verifies a numerical intervention, not event repair or general efficacy.",
                      "Hook memory fields describe tensor storage arithmetic, not measured peak GPU memory."])
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
    output = args.root / "analysis/silverwolf_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "errors": result["errors"],
                      "missing_count": len(result["missing"]), "report": str(output)}))
    raise SystemExit(1 if result["status"] == "invalid" else 2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
