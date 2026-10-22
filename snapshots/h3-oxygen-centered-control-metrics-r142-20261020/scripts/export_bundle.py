"""Run once on a completed producer. CPU only; no network, tensor or model imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path

RUN = "r142_short_0252_seed2026101703_visible_only"


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--producer-root", type=Path, required=True)
    p.add_argument("--attempt", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    root = a.producer_root.resolve()
    assert a.attempt.replace("_", "").isalnum()
    assert not a.out.exists()
    attempt = root / "audit" / a.attempt
    gate = root / "analysis/postrun/ONLINE_RUNTIME_GATE.json"
    completed = read(attempt / "COMPLETE_REVIEW_HOLD.json")
    g = read(gate)
    assert completed["passed"] and completed["run_id"] == RUN
    assert completed["gate_sha256"] == sha(gate) and g["passed"] and g["cleanup_verified"]
    assert g["verified_runs"] == [RUN]
    video = Path(g["video"]["file"]).resolve()
    assert video.is_relative_to(root / "output") and sha(video) == g["video"]["sha256"]
    files = {
        "STARTED.json": attempt / "STARTED.json",
        "ROOT_EXIT_RECEIPT.json": attempt / "ROOT_EXIT_RECEIPT.json",
        "COMPLETE_REVIEW_HOLD.json": attempt / "COMPLETE_REVIEW_HOLD.json",
        "ONLINE_RUNTIME_GATE.json": gate,
        "graph.json": root / "configs/graphs" / (RUN + ".json"),
        "history.json": root / "logs" / (RUN + "_history.json"),
        "job.json": root / "logs" / (RUN + "_job.json"),
        "centeredauto.mp4": video,
    }
    audit_file = root / "audit/counterfactual" / (RUN + ".json")
    audit = read(audit_file)
    c = audit["counterfactual"]
    # Keep every actual decision and centered eligibility summary, without 20 full scans.
    compact = {k: audit[k] for k in
               ("status", "completed_forward_calls", "completed_calls", "routed_calls", "calls_by_forward")}
    compact["counterfactual"] = {k: c[k] for k in
        ("seed", "full_physical_indices", "actual_model_nfe", "actual_euler_updates",
         "callback_count", "branches", "steps", "pair_gates")}
    compact["counterfactual"]["measurements"] = [
        {**{k: m[k] for k in ("physical_index", "request_file", "request_sha256",
                               "response_file", "response_sha256")},
         "centered_eligibility": m["observer"]["centered_eligibility"]}
        for m in c["measurements"]]
    a.out.mkdir(parents=True)
    for name, src in files.items():
        os.link(src, a.out / name)
    compact_path = a.out / "counterfactual.compact.json"
    compact_path.write_text(json.dumps(compact, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    receipt = {
        "schema": "r142-local-export-v1", "run_id": RUN, "attempt": a.attempt,
        "producer_root": str(root), "exporter_sha256": sha(__file__),
        "original_audit": {"file": str(audit_file), "sha256": sha(audit_file)},
        "files": {p.name: sha(p) for p in a.out.iterdir()},
        "tensor_payloads_transferred": False, "GPU_started": False,
    }
    (a.out / "EXPORT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"bundle": str(a.out), "bytes": sum(p.stat().st_size for p in a.out.iterdir())}))


if __name__ == "__main__":
    main()
