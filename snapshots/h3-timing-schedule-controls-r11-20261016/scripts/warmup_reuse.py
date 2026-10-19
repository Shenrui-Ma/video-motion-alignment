"""Verify archived successful R6 warmup before admitting the single R9 job."""
import hashlib
import json
from pathlib import Path
import re


def validate(root):
    root = Path(root)
    manifest = json.loads((root / "configs/warmup_reuse_manifest.json").read_text())
    for rel, item in manifest["files"].items():
        raw = (root / rel).read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("changed archived warmup evidence: " + rel)
    evidence = root / "audit/r6_warmup"
    gate = json.loads((evidence / "warmup_gate.json").read_text())
    history = json.loads((evidence / "history.json").read_text())
    graph = json.loads((evidence / "graph.json").read_text())
    provenance = json.loads((evidence / "runtime_provenance.json").read_text())
    if gate["job"] != "r6_s05_feedback_bench2" or gate["limit"] != 100.0:
        raise ValueError("wrong parent warmup")
    timing = gate["seconds_per_iteration_seen"]
    if not timing or timing[-1] > 100 or timing[-1] <= 0:
        raise ValueError("warmup timing failed")
    observed = [float(v) for v in re.findall(r"(\d+\.\d+)s/it", (evidence / "comfyui.log").read_text())]
    if timing != observed[-3:]:
        raise ValueError("warmup timing differs from original log")
    if history["status"]["status_str"] != "success" or not history["status"]["completed"]:
        raise ValueError("warmup did not finish successfully")
    if history["prompt"][2] != graph:
        raise ValueError("warmup graph differs from executed graph")
    if any(n["class_type"] in ("H3FeedbackRouter", "H3X0Readout") for n in graph.values()):
        raise ValueError("warmup was not the original plain Full backend check")
    if graph["9"]["inputs"]["sigmas"] != "1, 0.995633187773, 0":
        raise ValueError("wrong warmup sigma sequence")
    if not provenance["core_matches"] or not all(provenance["core_matches"].values()):
        raise ValueError("parent Comfy core did not match")
    models = json.loads((root / "configs/model_hashes_host41.json").read_text())
    for name, item in provenance["models"].items():
        if item["prior_full_sha256"] != models[name]["sha256"]:
            raise ValueError("model differs from warmup: " + name)
    code = ["scripts/compatibility_bootstrap.py", "scripts/int8_row_chunking.py",
            "scripts/backend_dispatch_audit.py", "extensions/H3TemporalRouter/core.py",
            "extensions/H3TemporalRouter/layout.py", "extensions/H3PhaseRoPE/audited_flash.py",
            "extensions/H3EventEmphasis/core.py"]
    for rel in code:
        normalized = (root / rel).read_bytes().replace(
            b"timing_schedule_controls_r11_20261016", b"timing_feedback_r6_20261016")
        if hashlib.sha256(normalized).hexdigest() != provenance["code"][rel]:
            raise ValueError("backend code differs from warmup: " + rel)
    return {"status": "pass", "warmup_job": gate["job"], "seconds_per_iteration": timing[-1],
            "backend_files_checked": code, "new_gpu_warmup": False,
            "limit": "historical backend evidence, not a current-speed or controller-quality claim"}


if __name__ == "__main__":
    print(json.dumps(validate(Path(__file__).resolve().parents[1]), indent=2))
