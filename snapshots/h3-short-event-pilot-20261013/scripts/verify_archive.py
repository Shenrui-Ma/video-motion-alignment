#!/usr/bin/env python3
"""Validate the pilot archive without importing torch or contacting a server.

Runtime manifests describe tensor shape/dtype. SHA256 of each archived
torch.save ZIP storage is independently checked when the blob is available;
pickle metadata is never executed. Missing evidence remains explicitly pending.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

FORMAL = re.compile(r"^(?P<source>.+)_(?P<arm>[ab])_(?P<seed>s[12])$")
DTYPE_BYTES = {"torch.float32": 4, "torch.float64": 8, "torch.float16": 2,
               "torch.bfloat16": 2, "torch.int64": 8, "torch.int32": 4,
               "torch.int16": 2, "torch.int8": 1, "torch.uint8": 1, "torch.bool": 1}


def sha256_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return sha256_stream(stream)


def read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def source_nodes(graph, node_id):
    found = set()
    def visit(current):
        if current in found:
            return
        found.add(current)
        for value in graph[current].get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] in graph and isinstance(value[1], int):
                visit(value[0])
    visit(node_id)
    return found


def primary_sink(graph, run_id):
    candidates = [key for key, node in graph.items() if node.get("class_type") == "SaveVideo"
                  and node.get("inputs", {}).get("filename_prefix") == run_id]
    if len(candidates) != 1:
        raise ValueError("expected exactly one primary SaveVideo named by run_id")
    return candidates[0]


def normalized_main_graph(graph, run_id):
    sink = primary_sink(graph, run_id)
    result = {}
    for key in sorted(source_nodes(graph, sink)):
        node = graph[key]
        inputs = dict(node.get("inputs", {}))
        if node["class_type"] == "H3EventAuditReference":
            inputs.pop("prompt", None)
            inputs.pop("run_id", None)
        elif node["class_type"] == "H3EventAuditNoise":
            inputs.pop("run_id", None)
        if key == sink:
            inputs.pop("filename_prefix", None)
        result[key] = {"class_type": node["class_type"], "inputs": inputs}
    return result


def execution_timing(history):
    """Comfy execution messages use Unix milliseconds, not polling times."""
    if not history:
        return {"success": False, "execution_seconds": None}
    status = history.get("status", {})
    prompt_id = history.get("prompt", [None, None])[1]
    events = [(kind, event) for kind, event in status.get("messages", [])
              if isinstance(event, dict) and isinstance(event.get("timestamp"), (int, float))
              and event.get("prompt_id", prompt_id) == prompt_id]
    starts = [event["timestamp"] for kind, event in events if kind == "execution_start"]
    ends = [event["timestamp"] for kind, event in events if kind == "execution_success"]
    success = status.get("status_str") == "success" and status.get("completed") is True and bool(ends)
    end = max(ends) if ends else None
    valid_starts = [stamp for stamp in starts if end is not None and stamp <= end]
    start = max(valid_starts) if valid_starts else None
    return {"success": success, "start_unix_ms": start, "success_unix_ms": end,
            "execution_seconds": (end - start) / 1000 if start is not None else None,
            "timing_source": "history execution_start/execution_success Unix milliseconds"}


def probe_video(path):
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe unavailable; video geometry cannot be verified")
    result = subprocess.run([executable, "-v", "error", "-count_frames", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,nb_read_frames,codec_name",
                             "-of", "json", str(path)], capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise ValueError("ffprobe failed: " + result.stderr[-500:])
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("expected one selected video stream")
    stream = streams[0]
    return {"width": stream["width"], "height": stream["height"],
            "frames": int(stream["nb_read_frames"]),
            "fps": str(Fraction(stream["avg_frame_rate"])), "codec": stream.get("codec_name")}


def storage_hashes(path):
    """Read raw storages only; never deserialize data.pkl from the archive."""
    with zipfile.ZipFile(path) as archive:
        entries = [entry for entry in archive.infolist() if re.search(r"/data/\d+$", entry.filename)]
        if not entries:
            raise ValueError("torch.save ZIP contains no raw tensor storages")
        result = []
        for entry in entries:
            with archive.open(entry) as stream:
                result.append((sha256_stream(stream), entry.file_size))
        return Counter(result)


def tensor_signature(value):
    if not isinstance(value, dict) or not re.fullmatch(r"[a-f0-9]{64}", value.get("sha256", "")):
        raise ValueError("missing or invalid tensor SHA256")
    shape = value.get("shape")
    dtype = value.get("dtype")
    if not isinstance(shape, list) or not shape or any(type(dim) is not int or dim <= 0 for dim in shape) or dtype not in DTYPE_BYTES:
        raise ValueError("invalid tensor shape/dtype")
    size = DTYPE_BYTES[dtype]
    for dim in shape:
        size *= dim
    return {"sha256": value["sha256"], "shape": shape, "dtype": dtype, "bytes": size}


def recorded_tensor_files(value):
    if isinstance(value, dict):
        if "tensor_file" in value:
            yield value
        for child in value.values():
            yield from recorded_tensor_files(child)
    elif isinstance(value, list):
        for child in value:
            yield from recorded_tensor_files(child)


class Verifier:
    def __init__(self, root, probe=probe_video):
        self.root = Path(root)
        self.probe = probe
        self.hash_cache = {}
        self.probe_cache = {}
        self.storage_cache = {}

    def hash(self, path):
        if path not in self.hash_cache:
            self.hash_cache[path] = file_hash(path)
        return self.hash_cache[path]

    def video(self, path):
        if path not in self.probe_cache:
            self.probe_cache[path] = self.probe(path)
        return self.probe_cache[path]

    def storages(self, path):
        if path not in self.storage_cache:
            self.storage_cache[path] = storage_hashes(path)
        return self.storage_cache[path]

    def tensor_file(self, info, errors, missing):
        signature = tensor_signature(info)
        relative = Path(info["tensor_file"])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append("unsafe tensor_file path")
            return
        path = self.root / "audit" / relative
        if not path.exists():
            missing.append(str(path.relative_to(self.root)))
        elif self.storages(path) != Counter({(signature["sha256"], signature["bytes"]): 1}):
            errors.append("raw storage mismatch: " + str(relative))

    def run(self, run_id, formal=True, source_id=None, kind=None):
        row = {"run_id": run_id, "kind": kind or ("formal" if formal else "benchmark"), "status": "pending",
               "errors": [], "missing": [], "generated": False, "fully_archived": False,
               "execution_seconds": None}
        if source_id is not None:
            row["source_id"] = source_id
        errors, missing = row["errors"], row["missing"]
        config_path = self.root / "configs" / (run_id + ".json")
        graph = read_json(config_path)
        if not graph:
            missing.append(str(config_path.relative_to(self.root)))
            return row
        row["graph_sha256"] = self.hash(config_path)
        sink = primary_sink(graph, run_id)
        references = [n["inputs"] for n in graph.values() if n.get("class_type") == "H3EventAuditReference"]
        noises = [n["inputs"] for n in graph.values() if n.get("class_type") == "H3EventAuditNoise"]
        if len(references) != 1 or len(noises) != 1:
            raise ValueError("expected one audited reference and noise node")
        ref, noise = references[0], noises[0]
        row.update(seed=noise["noise_seed"], pair_id=noise["pair_id"], width=ref["width"],
                   height=ref["height"], expected_frames=107, expected_fps="24")
        if ref["length"] != 107:
            errors.append("graph frame count is not 107")
        if ref["run_id"] != run_id or noise["run_id"] != run_id:
            errors.append("graph run_id mismatch")
        sigmas = next(n["inputs"]["sigmas"] for n in graph.values() if n.get("class_type") == "ManualSigmas")
        row["steps"] = len([s for s in sigmas.split(",") if s.strip()]) - 1
        if formal and row["steps"] != 20:
            errors.append("formal graph must have 20 sampling steps")
        loaded = [n["inputs"]["file"] for n in graph.values() if n.get("class_type") == "LoadVideo"]
        if len(loaded) != 1:
            raise ValueError("expected one LoadVideo source")
        loaded_source_id = Path(loaded[0]).stem
        if source_id is not None and loaded_source_id != source_id:
            errors.append("declared control source_id differs from graph LoadVideo source")
        source_id = source_id or loaded_source_id
        row["source_id"] = source_id
        source_path = self.root / "inputs" / Path(loaded[0]).name
        metadata = read_json(self.root / "inputs" / (source_id + ".json"))
        source_manifest = read_json(self.root / "inputs/source_manifest.json")
        if source_manifest:
            records = [record for record in source_manifest.get("clips", []) if record.get("clip_id") == source_id]
            if len(records) != 1:
                errors.append("source missing/duplicated in source_manifest")
            elif metadata and any(metadata.get(key) != records[0].get(key) for key in
                                  ("source_sha256", "output_sha256", "output_frames", "output_fps", "width", "height")):
                errors.append("per-source metadata differs from source_manifest")
        else:
            missing.append("inputs/source_manifest.json")
        if not metadata:
            missing.append("inputs/" + source_id + ".json")
        elif source_path.exists():
            row["input_mp4_sha256"] = self.hash(source_path)
            if row["input_mp4_sha256"] != metadata.get("output_sha256"):
                errors.append("source input file SHA256 mismatch")
            source_probe = self.video(source_path)
            if source_probe != dict(source_probe, width=ref["width"], height=ref["height"], frames=107, fps="24"):
                errors.append("source video geometry/FPS mismatch")
            original = Path(metadata["source_file"])
            if original.exists():
                if self.hash(original) != metadata.get("source_sha256"):
                    errors.append("original downloaded source SHA256 mismatch")
            else:
                missing.append("original_source:" + str(original))
        else:
            missing.append(str(source_path.relative_to(self.root)))

        job = read_json(self.root / "logs" / (run_id + "_job.json"))
        history = read_json(self.root / "logs" / (run_id + "_history.json"))
        if not job:
            missing.append("logs/" + run_id + "_job.json")
        elif job.get("graph_sha256") != row["graph_sha256"]:
            errors.append("submitted graph file SHA256 mismatch")
        if not history:
            missing.append("logs/" + run_id + "_history.json")
        else:
            if "status" not in history and len(history) == 1:
                history = next(iter(history.values()))
            history_prompt = history.get("prompt", [])
            if len(history_prompt) < 3 or history_prompt[2] != graph:
                errors.append("history graph differs from archived graph")
            if job and (len(history_prompt) < 2 or history_prompt[1] != job.get("prompt_id")):
                errors.append("job/history prompt_id mismatch")
            timing = execution_timing(history)
            row.update(timing)
            if timing["success"] and timing["execution_seconds"] is None:
                missing.append("history execution_start timestamp")
            status = history.get("status", {})
            if status.get("status_str") in {"error", "failed"} or any(m[0] == "execution_error" for m in status.get("messages", [])):
                errors.append("history reports execution failure")
            artifacts = history.get("outputs", {}).get(sink, {}).get("images", [])
            videos = [a for a in artifacts if a.get("type") == "output" and str(a.get("filename", "")).endswith(".mp4")]
            if len(videos) != 1:
                missing.append("unique primary output in history")
            else:
                artifact = videos[0]
                filename = artifact["filename"]
                if not re.fullmatch(re.escape(run_id) + r"_\d+_\.mp4", filename):
                    errors.append("primary output filename is not this exact run; benchmark/other-run contamination")
                relative = Path(artifact.get("subfolder", "")) / filename
                if relative.is_absolute() or ".." in relative.parts:
                    errors.append("unsafe output artifact path")
                else:
                    output_path = self.root / "outputs" / relative
                    row["output_file"] = str(output_path.relative_to(self.root))
                    if not output_path.exists():
                        missing.append(row["output_file"])
                    else:
                        row["output_sha256"] = self.hash(output_path)
                        row["video_probe"] = self.video(output_path)
                        expected = {"width": ref["width"], "height": ref["height"], "frames": 107, "fps": "24"}
                        if any(row["video_probe"].get(k) != v for k, v in expected.items()):
                            errors.append("output video frame count/FPS/dimensions mismatch")
                        row["generated"] = timing["success"] and not errors
            if not timing["success"]:
                missing.append("successful completed history execution")

        condition = read_json(self.root / "audit" / (run_id + "_conditioning.json"))
        actual_noise = read_json(self.root / "audit" / (run_id + "_noise.json"))
        if not condition:
            missing.append("audit/" + run_id + "_conditioning.json")
        else:
            if condition.get("run_id") != run_id or condition.get("prompt") != ref["prompt"]:
                errors.append("conditioning manifest run_id/prompt mismatch")
            tensor_signature(condition["input_video"])
            if condition["input_video"]["shape"] != [107, ref["height"], ref["width"], 3]:
                errors.append("decoded source tensor geometry mismatch")
            row["decoded_source_tensor"] = tensor_signature(condition["input_video"])
            row["dense_references"] = [{key: tensor_signature(call[key]) for key in ("prepared_frames", "latent")}
                                       for call in condition.get("native_vae_calls", [])]
            if not row["dense_references"]:
                errors.append("no dense reference evidence")
            row["qwen_observations"] = [{"sampling": p.get("sampling"),
                                        "frames": tensor_signature(p["actual_sampled_frames"])}
                                       for p in condition.get("qwen_presentation", []) if p.get("type") == "video"]
            for tensor in recorded_tensor_files(condition):
                self.tensor_file(tensor, errors, missing)
        if not actual_noise:
            missing.append("audit/" + run_id + "_noise.json")
        else:
            if actual_noise.get("run_id") != run_id or actual_noise.get("pair_id") != noise["pair_id"]:
                errors.append("noise manifest identity mismatch")
            signature = actual_noise.get("signature", {})
            streams = actual_noise.get("actual_noise_streams", [])
            row["noise_signature"] = signature
            row["noise_streams"] = [tensor_signature(s) for s in streams]
            if signature.get("seed") != noise["noise_seed"] or signature.get("nested") is not True or len(streams) != 2:
                errors.append("noise seed/nested stream count mismatch")
            if signature.get("shapes") != [s["shape"] for s in streams] or signature.get("dtypes") != [s["dtype"] for s in streams]:
                errors.append("noise stream shape/dtype differs from signature")
            expected_shapes = [[1, 24, 32, ref["height"] // 16, ref["width"] // 16], [1, 32, 2, round(107 / 24 * 40)]]
            if signature.get("shapes") != expected_shapes:
                errors.append("noise shapes do not match 107-frame H3 AV geometry")
            if condition and condition.get("target_latent_shapes") != signature.get("shapes"):
                errors.append("target latent/noise shapes differ")
            cache = self.root / "audit" / Path(actual_noise["cache_file"]).name
            if not cache.exists():
                missing.append(str(cache.relative_to(self.root)))
            else:
                expected = Counter((s["sha256"], s["bytes"]) for s in row["noise_streams"])
                if self.storages(cache) != expected:
                    errors.append("cached actual AV noise raw storage SHA256 mismatch")
        row["missing"] = sorted(set(missing))
        if errors:
            row["status"] = "failed_validation"
            row["generated"] = False
        elif row["generated"] and not missing:
            row["status"] = "complete"
            row["fully_archived"] = True
        elif row["generated"]:
            row["status"] = "generated_pending_archive"
        return row


def pair_validation(a, b, graph_a, graph_b):
    errors, missing = [], []
    if normalized_main_graph(graph_a, a["run_id"]) != normalized_main_graph(graph_b, b["run_id"]):
        errors.append("A/B main generation graphs differ beyond prompt/run_id/output filename")
    required = ["noise_signature", "noise_streams", "decoded_source_tensor", "dense_references", "qwen_observations"]
    for key in required:
        if key not in a or key not in b:
            missing.append(key)
        elif a[key] != b[key]:
            errors.append("paired " + key + " mismatch")
    if not a.get("generated") or not b.get("generated"):
        missing.append("both formally generated outputs")
    return {"pair_id": a.get("pair_id"), "arms": [a["run_id"], b["run_id"]],
            "status": "failed_validation" if errors else "pending" if missing else "pass",
            "errors": errors, "missing": missing}


def validate_controls(verifier, primary_rows):
    """Adaptive controls remain separate from primary samples and benchmarks."""
    controls_path = verifier.root / "configs/controls.json"
    config = read_json(controls_path)
    if config is None:
        return [], []
    if not isinstance(config, dict) or not isinstance(config.get("jobs"), list):
        return [], ["controls.json must contain a jobs list"]
    rows, issues = [], []
    used = {row["run_id"] for row in primary_rows}
    for record in config["jobs"]:
        try:
            if not isinstance(record, dict):
                raise ValueError("each control must be an object")
            for key in ("run_id", "source_id", "description", "paired_noise_id"):
                if not isinstance(record.get(key), str) or not record[key].strip():
                    raise ValueError("control needs nonempty " + key)
            for key in ("run_id", "source_id", "paired_noise_id"):
                if not re.fullmatch(r"[A-Za-z0-9_-]+", record[key]):
                    raise ValueError("control identifiers must be plain filename components")
            name = record["run_id"]
            if name in used or "benchmark" in name:
                raise ValueError("control duplicates a primary/control or uses a benchmark name: " + name)
            comparisons = record.get("comparison_to")
            comparisons = [comparisons] if isinstance(comparisons, str) else comparisons
            if not isinstance(comparisons, list) or not comparisons or any(not isinstance(value, str) or not value for value in comparisons):
                raise ValueError("control comparison_to must be a run id or nonempty list of run ids")
            if name in comparisons:
                raise ValueError("control cannot compare to itself")
            used.add(name)
            try:
                row = verifier.run(name, source_id=record["source_id"], kind="adaptive_control")
            except Exception as exc:
                row = {"run_id": name, "source_id": record["source_id"], "kind": "adaptive_control",
                       "status": "failed_validation", "generated": False, "fully_archived": False,
                       "errors": [type(exc).__name__ + ": " + str(exc)], "missing": []}
            row.update(description=record["description"], paired_noise_id=record["paired_noise_id"],
                       comparison_to=comparisons, independent_sample=False)
            if row.get("pair_id") is not None and row["pair_id"] != record["paired_noise_id"]:
                row["errors"].append("control paired_noise_id differs from graph/audit pair_id")
            rows.append(row)
        except ValueError as exc:
            issues.append(str(exc))

    by_id = {row["run_id"]: row for row in primary_rows + rows}
    for row in rows:
        comparisons = []
        for target_id in row["comparison_to"]:
            errors, missing = [], []
            target = by_id.get(target_id)
            if target is None:
                missing.append("comparison run not declared: " + target_id)
            else:
                if target.get("source_id") is not None and target["source_id"] != row["source_id"]:
                    errors.append("comparison uses a different source_id")
                if target.get("pair_id") is not None and target["pair_id"] != row["paired_noise_id"]:
                    errors.append("comparison uses a different paired_noise_id")
                for key in ("noise_signature", "noise_streams", "decoded_source_tensor", "dense_references"):
                    if key not in row or key not in target:
                        missing.append(key)
                    elif row[key] != target[key]:
                        errors.append("control/comparison " + key + " mismatch")
                # Qwen observations intentionally may differ in a semantic-FPS control.
                if not target.get("generated"):
                    missing.append("successful comparison output")
            result = {"run_id": target_id, "status": "failed_validation" if errors else "pending" if missing else "pass",
                      "errors": errors, "missing": missing}
            comparisons.append(result)
            row["errors"].extend(target_id + ": " + error for error in errors)
            row["missing"].extend(target_id + ": " + item for item in missing)
        row["comparisons"] = comparisons
        row["archive_evidence_complete"] = row["fully_archived"]
        if row["errors"]:
            row.update(status="failed_validation", generated=False, fully_archived=False)
        elif any(comparison["status"] != "pass" for comparison in comparisons):
            row["fully_archived"] = False
            if row["generated"]:
                row["status"] = "generated_pending_comparison"
        row["missing"] = sorted(set(row["missing"]))
    return rows, issues


def verify(root, probe=probe_video):
    root = Path(root)
    verifier = Verifier(root, probe)
    queue = read_json(root / "configs/queue.json") or {"jobs": []}
    control_config = read_json(root / "configs/controls.json") or {}
    declared_controls = {record.get("run_id") for record in control_config.get("jobs", []) if isinstance(record, dict)} if isinstance(control_config, dict) and isinstance(control_config.get("jobs", []), list) else set()
    source_manifest = read_json(root / "inputs/source_manifest.json") or {}
    original_primary = {f"{clip['clip_id']}_{arm}_{seed}" for clip in source_manifest.get("clips", [])
                        for arm in ("a", "b") for seed in ("s1", "s2")}
    jobs = [name for name in queue["jobs"] if FORMAL.fullmatch(name)
            and (name not in declared_controls or name in original_primary)]
    issues = []
    if len(jobs) != 12 or len(set(jobs)) != 12:
        issues.append("queue must contain 12 distinct primary A/B x two-seed jobs")
    rows = []
    for name in jobs:
        try:
            rows.append(verifier.run(name))
        except Exception as exc:
            rows.append({"run_id": name, "kind": "formal", "status": "failed_validation", "generated": False,
                         "fully_archived": False, "errors": [type(exc).__name__ + ": " + str(exc)], "missing": []})
    by_id = {r["run_id"]: r for r in rows}
    pairs = []
    for name in jobs:
        match = FORMAL.fullmatch(name)
        if match["arm"] != "a":
            continue
        other = match["source"] + "_b_" + match["seed"]
        if other not in by_id:
            issues.append("missing B arm: " + other)
            continue
        try:
            pairs.append(pair_validation(by_id[name], by_id[other],
                                         read_json(root / "configs" / (name + ".json")),
                                         read_json(root / "configs" / (other + ".json"))))
        except Exception as exc:
            pairs.append({"arms": [name, other], "status": "failed_validation", "errors": [str(exc)], "missing": []})
    benchmarks = []
    for path in sorted((root / "configs").glob("*benchmark*.json")):
        try:
            benchmarks.append(verifier.run(path.stem, formal=False))
        except Exception as exc:
            benchmarks.append({"run_id": path.stem, "status": "failed_validation", "errors": [str(exc)]})
    controls, control_issues = validate_controls(verifier, rows)
    primary_status = "failed_validation" if issues or any(r["errors"] for r in rows) or any(p["errors"] for p in pairs) else (
        "complete" if len(rows) == 12 and all(r["fully_archived"] for r in rows) and all(p["status"] == "pass" for p in pairs) else "incomplete")
    controls_status = "failed_validation" if control_issues or any(r["errors"] for r in controls) else (
        "complete" if all(r["fully_archived"] for r in controls) else "incomplete")
    overall = "failed_validation" if "failed_validation" in (primary_status, controls_status) else (
        "complete" if primary_status == controls_status == "complete" else "incomplete")
    return {"schema": "h3-pilot-archive-validation-v1", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "archive_root": str(root), "status": overall,
            "summary": {"planned_primary": len(rows), "successful_formal_generations": sum(r["generated"] for r in rows),
                        "fully_archived_formal_runs": sum(r["fully_archived"] for r in rows),
                        "valid_pairs": sum(p["status"] == "pass" for p in pairs), "benchmark_runs_excluded": len(benchmarks),
                        "planned_adaptive_controls": len(controls),
                        "successful_adaptive_controls": sum(r["generated"] for r in controls),
                        "fully_archived_adaptive_controls": sum(r["fully_archived"] for r in controls)},
            "issues": issues, "formal_runs": rows, "pairs": pairs, "benchmarks": benchmarks,
            "primary_status": primary_status, "adaptive_controls_status": controls_status,
            "adaptive_controls": controls, "control_issues": control_issues,
            "limitations": ["No automatic scientific/event-quality verdict is inferred from runtime or metadata.",
                            "Tensor shape/dtype are runtime manifest evidence; archived raw ZIP storages are independently SHA256-checked without unpickling.",
                            "Missing local artifacts are pending even when remote generation may have finished.",
                            "Adaptive controls reuse existing sources/noise and are not new independent samples or benchmark runs."]}


def write_reports(root, report):
    analysis = Path(root) / "analysis"
    atomic_json(analysis / "archive_validation.json", report)
    atomic_json(analysis / "experiment_ledger.json", report["formal_runs"])
    columns = ["run_id", "source_id", "pair_id", "seed", "status", "generated", "fully_archived", "steps",
               "execution_seconds", "output_file", "output_sha256", "input_mp4_sha256", "errors", "missing"]
    with (analysis / "experiment_ledger.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in report["formal_runs"]:
            writer.writerow({key: json.dumps(row.get(key, []), ensure_ascii=False) if key in {"errors", "missing"}
                             else row.get(key, "") for key in columns})
    controls = report.get("adaptive_controls", [])
    atomic_json(analysis / "control_ledger.json", controls)
    control_columns = columns + ["description", "paired_noise_id", "comparison_to", "independent_sample", "comparisons"]
    with (analysis / "control_ledger.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=control_columns)
        writer.writeheader()
        for row in controls:
            writer.writerow({key: json.dumps(row.get(key, []), ensure_ascii=False)
                             if key in {"errors", "missing", "comparison_to", "comparisons"}
                             else row.get(key, "") for key in control_columns})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = verify(args.root)
    write_reports(args.root, report)
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False))
    return 2 if report["status"] == "failed_validation" else 0


if __name__ == "__main__":
    raise SystemExit(main())
