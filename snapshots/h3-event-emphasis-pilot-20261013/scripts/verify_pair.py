#!/usr/bin/env python3
"""CPU-only, read-only evidence verification for the fixed two-run experiment.

No torch import, pickle execution, server access, or write to an old experiment.
Exit 0 = complete/pass, 2 = pending archive, 1 = invalid evidence.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

RUNS = ("06_seed2_baseline", "06_seed2_emphasis2")
BENCHMARK = "06_seed2_emphasis2_benchmark2"
DTYPES = {"torch.float32": 4, "torch.float64": 8, "torch.float16": 2,
          "torch.bfloat16": 2, "torch.int64": 8, "torch.int32": 4,
          "torch.int16": 2, "torch.int8": 1, "torch.uint8": 1, "torch.bool": 1}
EXPECTED_VIDEO = {"frames": 141, "fps": "24", "width": 1312, "height": 736}


def digest_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def sha256(path):
    with Path(path).open("rb") as stream:
        return digest_stream(stream)


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else None


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def probe(path):
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe not installed/on PATH")
    result = subprocess.run([executable, "-v", "error", "-count_frames", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames",
                             "-of", "json", str(path)], check=True, text=True,
                            capture_output=True, timeout=180)
    streams = json.loads(result.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError("expected a single selected video stream")
    item = streams[0]
    return {"frames": int(item["nb_read_frames"]), "fps": str(Fraction(item["avg_frame_rate"])),
            "width": item["width"], "height": item["height"]}


def signature(tensor):
    if not isinstance(tensor, dict) or not re.fullmatch(r"[0-9a-f]{64}", tensor.get("sha256", "")):
        raise ValueError("invalid tensor SHA256 record")
    shape, dtype = tensor.get("shape"), tensor.get("dtype")
    if (not isinstance(shape, list) or not shape or dtype not in DTYPES
            or any(type(n) is not int or n < 1 for n in shape)):
        raise ValueError("invalid tensor shape/dtype")
    size = DTYPES[dtype]
    for n in shape:
        size *= n
    return {"sha256": tensor["sha256"], "shape": shape, "dtype": dtype, "bytes": size}


def canonical(value):
    """Compare tensor content identity while ignoring storage-path naming."""
    if isinstance(value, dict):
        if "sha256" in value and "shape" in value and "dtype" in value:
            return signature(value)
        return {key: canonical(child) for key, child in value.items()}
    if isinstance(value, list):
        return [canonical(child) for child in value]
    return value


def tensor_records(value):
    if isinstance(value, dict):
        if "tensor_file" in value:
            yield value
        for child in value.values():
            yield from tensor_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from tensor_records(child)


def raw_storages(path):
    """Hash ZIP data storages; NEVER deserialize torch.save data.pkl."""
    result = Counter()
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if re.search(r"/data/\d+$", entry.filename):
                with archive.open(entry) as stream:
                    result[(digest_stream(stream), entry.file_size)] += 1
    if not result:
        raise ValueError("archive has no tensor data storages: " + str(path))
    return result


def normalize_graph(graph):
    result = {}
    for key, node in graph.items():
        values = dict(node["inputs"])
        if node["class_type"] in {"H3EventAuditReference", "H3EventAuditNoise", "H3EventEmphasis"}:
            values.pop("run_id", None)
        if node["class_type"] == "H3EventEmphasis":
            values.pop("factor", None)
        if node["class_type"] == "SaveVideo":
            values.pop("filename_prefix", None)
        result[key] = {"class_type": node["class_type"], "inputs": values}
    return result


def one_node(graph, kind):
    nodes = [(key, node["inputs"]) for key, node in graph.items() if node["class_type"] == kind]
    if len(nodes) != 1:
        raise ValueError("expected one " + kind)
    return nodes[0]


def validate_hook(hook, run_id, factor, plan):
    problems = []
    expected = {"run_id": run_id, "factor": factor, "expected_num_blocks": 50,
                "formal_planned_sampling_steps": 20, "expected_sampling_steps": 20,
                "started_calls": 1000, "completed_calls": 1000,
                "completed_forward_calls": 20, "calls_by_block": [20] * 50,
                "calls_by_forward": [50] * 20, "native_override_calls": 1000 if factor == 2 else 0,
                "pixel_interval_inclusive": [39, 44]}
    for key, value in expected.items():
        if hook.get(key) != value:
            problems.append("hook " + key + " differs from expected")
    if hook.get("status") == "failed" or hook.get("error"):
        problems.append("hook reports failure")
    layout = hook.get("validated_layout", {})
    inter = plan["intervention"]
    layout_expected = {"seq_len": inter["expected_native_seq_len"],
                       "key_interval_half_open": inter["expected_absolute_reference_keys_half_open"],
                       "query_interval_half_open": inter["expected_absolute_target_queries_half_open"],
                       "latent_interval_half_open": [12, 14], "pixel_interval_inclusive": [39, 44],
                       "position_bin_coverage_inclusive": [39, 46], "frame_rows": 943,
                       "reference_kind": "video"}
    for key, value in layout_expected.items():
        if layout.get(key) != value:
            problems.append("hook layout " + key + " differs from preregistration")
    return problems


def validate(root):
    root = Path(root)
    errors, missing, rows = [], [], []
    plan = read_json(root / "configs/preregistered_plan.json")
    if not plan:
        return {"status": "pending", "errors": [], "missing": ["configs/preregistered_plan.json"]}
    if plan["execution"]["formal_jobs"] != list(RUNS):
        errors.append("preregistered formal job list differs from frozen two jobs")
    source = root / "inputs/06_anime_eye_insert.mp4"
    if source.is_file():
        if probe(source) != EXPECTED_VIDEO:
            errors.append("source geometry/FPS/frame count differs")
    else:
        missing.append(str(source.relative_to(root)))
    signatures, graphs, storage_cache = {}, {}, {}

    def check_storage(path, wanted, run_errors, run_missing):
        if not path.is_file():
            run_missing.append(str(path.relative_to(root)))
            return
        if path not in storage_cache:
            storage_cache[path] = raw_storages(path)
        if storage_cache[path] != wanted:
            run_errors.append("independent raw tensor storage mismatch: " + str(path.relative_to(root)))

    for run_id, factor in zip(RUNS, (1, 2)):
        row = {"run_id": run_id, "factor": factor, "status": "pending", "errors": [], "missing": []}
        rows.append(row)
        err, miss = row["errors"], row["missing"]
        try:
            def required(relative):
                value = read_json(root / relative)
                if value is None:
                    miss.append(relative)
                return value
            graph = required("configs/" + run_id + ".json")
            job = required("logs/" + run_id + "_job.json")
            history = required("logs/" + run_id + "_history.json")
            condition = required("audit/" + run_id + "_conditioning.json")
            noise = required("audit/" + run_id + "_noise.json")
            hook = required("audit/emphasis/" + run_id + ".json")
            if graph:
                graphs[run_id] = graph
                sink, out = one_node(graph, "SaveVideo")
                _, ref = one_node(graph, "H3EventAuditReference")
                _, noi = one_node(graph, "H3EventAuditNoise")
                _, intervention = one_node(graph, "H3EventEmphasis")
                _, sigmas = one_node(graph, "ManualSigmas")
                if (out["filename_prefix"] != run_id or intervention["factor"] != factor
                        or any(x["run_id"] != run_id for x in (ref, noi, intervention))):
                    err.append("graph run IDs/factor/output prefix invalid")
                if (ref["length"], ref["width"], ref["height"], ref["semantic_fps"], ref["phase_frames"]) != (141, 1312, 736, 2, 0):
                    err.append("graph source recipe differs from preregistration")
                if noi["noise_seed"] != 2026101312 or len(sigmas["sigmas"].split(",")) != 21:
                    err.append("graph seed/steps differs from preregistration")
                if job and job.get("graph_sha256") != sha256(root / "configs" / (run_id + ".json")):
                    err.append("job graph SHA256 mismatch")
                if history:
                    if "status" not in history and len(history) == 1:
                        history = next(iter(history.values()))
                    prompt = history.get("prompt", [])
                    if len(prompt) < 3 or prompt[2] != graph:
                        err.append("history graph mismatch")
                    if job and (len(prompt) < 2 or prompt[1] != job.get("prompt_id")):
                        err.append("job/history prompt ID mismatch")
                    status = history.get("status", {})
                    messages = status.get("messages", [])
                    if status.get("status_str") in ("error", "failed") or any(m[0] == "execution_error" for m in messages):
                        err.append("history reports failure")
                    starts = [m[1]["timestamp"] for m in messages if m[0] == "execution_start"]
                    ends = [m[1]["timestamp"] for m in messages if m[0] == "execution_success"]
                    if status.get("status_str") != "success" or status.get("completed") is not True or not starts or not ends:
                        miss.append("successful completed history with execution timestamps")
                    else:
                        row["execution_seconds"] = (max(ends) - max(starts)) / 1000
                    artifacts = history.get("outputs", {}).get(sink, {}).get("images", [])
                    expected = run_id + "_00001_.mp4"
                    vids = [a for a in artifacts if a.get("type") == "output" and a.get("filename", "").endswith(".mp4")]
                    if len(vids) != 1 or vids[0].get("filename") != expected or vids[0].get("subfolder", ""):
                        err.append("primary history artifact is not exact expected formal output")
                if condition and (condition.get("prompt") != ref["prompt"] or condition.get("run_id") != run_id):
                    err.append("conditioning prompt/run ID mismatch")
                if noise and (noise.get("run_id") != run_id or noise.get("pair_id") != noi["pair_id"]):
                    err.append("noise run/pair identity mismatch")
            output = root / "outputs" / (run_id + "_00001_.mp4")
            if output.is_file():
                row["video_probe"] = probe(output)
                row["output_file"] = str(output.relative_to(root))
                row["output_sha256"] = sha256(output)
                if row["video_probe"] != EXPECTED_VIDEO:
                    err.append("output geometry/FPS/frame count differs")
            else:
                miss.append(str(output.relative_to(root)))
            if condition:
                fields = ("input_video", "native_vae_calls", "qwen_presentation", "tokenization_before_vision_expansion",
                          "conditioning_embedding", "token_tags", "target_latent_shapes", "packed_layout", "prompt")
                signatures[run_id] = {key: canonical(condition[key]) for key in fields}
                if condition["input_video"]["shape"] != [141, 736, 1312, 3]:
                    err.append("input decoded tensor shape invalid")
                if len(condition["native_vae_calls"]) != 2:
                    err.append("expected one clean image reference and one clean video reference")
                video_calls = [call for call in condition["native_vae_calls"] if call["prepared_frames"]["shape"][0] != 1]
                image_calls = [call for call in condition["native_vae_calls"] if call["prepared_frames"]["shape"][0] == 1]
                if (len(video_calls) != 1 or video_calls[0]["prepared_frames"]["shape"] != [141, 736, 1312, 3]
                        or video_calls[0]["latent"]["shape"] != [1, 24, 42, 46, 82]):
                    err.append("clean video prepared/latent geometry invalid")
                if (len(image_calls) != 1 or image_calls[0]["prepared_frames"]["shape"] != [1, 992, 992, 3]
                        or image_calls[0]["latent"]["shape"] != [1, 24, 1, 62, 62]):
                    err.append("clean reference image geometry invalid")
                for call in condition["native_vae_calls"]:
                    if any("tensor_file" not in call[key] for key in ("prepared_frames", "latent")):
                        err.append("clean prepared/reference tensors require archived storage files")
                qwen_video = [p for p in condition["qwen_presentation"] if p.get("type") == "video"]
                qwen_image = [p for p in condition["qwen_presentation"] if p.get("type") == "image"]
                if (len(qwen_video) != 1 or len(qwen_image) != 1
                        or qwen_video[0].get("sampling", {}).get("sample_indices") != list(range(0, 141, 12))
                        or qwen_video[0]["actual_sampled_frames"]["shape"] != [12, 736, 1312, 3]):
                    err.append("Qwen presentation frame selection/geometry invalid")
                elif "tensor_file" not in qwen_video[0]["actual_sampled_frames"]:
                    err.append("sampled Qwen video frames require archived storage")
                if condition["target_latent_shapes"] != [[1, 24, 42, 46, 82], [1, 32, 2, 235]]:
                    err.append("target latent shape invalid")
                for record in tensor_records(condition):
                    relative = Path(record["tensor_file"])
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("unsafe tensor-file path")
                    sig = signature(record)
                    check_storage(root / "audit" / relative, Counter({(sig["sha256"], sig["bytes"]): 1}), err, miss)
            if noise:
                streams = [signature(s) for s in noise["actual_noise_streams"]]
                wanted_shapes = [[1, 24, 42, 46, 82], [1, 32, 2, 235]]
                if (noise["signature"].get("seed") != 2026101312 or noise["signature"].get("nested") is not True
                        or [s["shape"] for s in streams] != wanted_shapes
                        or noise["signature"].get("shapes") != wanted_shapes
                        or noise["signature"].get("dtypes") != [s["dtype"] for s in streams]):
                    err.append("actual cached AV noise signature invalid")
                check_storage(root / "audit" / Path(noise["cache_file"]).name,
                              Counter((s["sha256"], s["bytes"]) for s in streams), err, miss)
                signatures.setdefault(run_id, {}).update(noise_signature=noise["signature"], actual_noise_streams=streams)
            if hook:
                # A partial sampling audit is pending, never a completed factor-control proof.
                if not history or not row.get("execution_seconds"):
                    miss.append("final hook audit after completed formal history")
                    if hook.get("status") == "failed":
                        err.append("hook reports failure")
                else:
                    err.extend(validate_hook(hook, run_id, factor, plan))
                row["hook"] = {key: hook.get(key) for key in ("factor", "status", "completed_calls", "completed_forward_calls", "native_override_calls")}
        except Exception as exc:
            err.append(type(exc).__name__ + ": " + str(exc))
        row["missing"] = sorted(set(miss))
        row["status"] = "invalid" if err else "pending" if miss else "pass"
    pair_checks = {}
    if all(name in graphs for name in RUNS):
        pair_checks["graphs_equal_except_factor_run_id_output_name"] = normalize_graph(graphs[RUNS[0]]) == normalize_graph(graphs[RUNS[1]])
    else:
        missing.append("both formal graphs")
    if all(name in signatures for name in RUNS):
        keys = set(signatures[RUNS[0]]) | set(signatures[RUNS[1]])
        for key in sorted(keys):
            if any(key not in signatures[name] for name in RUNS):
                missing.append("both runtime audit records: " + key)
            else:
                pair_checks[key + "_identical"] = signatures[RUNS[0]][key] == signatures[RUNS[1]][key]
    else:
        missing.append("both runtime conditioning/noise records")
    errors.extend("paired mismatch: " + key for key, equal in pair_checks.items() if not equal)
    for row in rows:
        errors.extend(row["run_id"] + ": " + e for e in row["errors"])
        missing.extend(row["run_id"] + ": " + e for e in row["missing"])
    return {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "invalid" if errors else "pending" if missing else "pass",
            "formal_run_ids": list(RUNS), "technical_output_excluded": BENCHMARK,
            "formal_count_passed": sum(row["status"] == "pass" for row in rows), "runs": rows,
            "pair_checks": pair_checks, "errors": errors, "missing": sorted(set(missing)),
            "independently_hashed_tensor_storage_files": len(storage_cache),
            "evidence_limits": ["Conditioning embedding and unsaved token tensors are compared by runtime-recorded SHA256, not independently rehashed blobs.",
                                "Clean reference and saved Qwen video tensors and AV noise are independently storage-hashed without pickle execution.",
                                "Augmented reference equality is inferred from identical clean latents, sampler seed and deterministic native implementation; augmented tensors were not directly archived or hashed.",
                                "A passing archive validates controls, not whether the short action was repaired."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = validate(args.root)
    path = args.root / "analysis/archive_tools_validation.json"
    previous = read_json(path) or {}
    previous["archive_validation"] = result
    write_json(path, previous)
    print(json.dumps({"status": result["status"], "formal_count_passed": result.get("formal_count_passed", 0),
                      "errors": result["errors"], "missing_count": len(result["missing"]), "report": str(path)}))
    raise SystemExit(1 if result["status"] == "invalid" else 2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
