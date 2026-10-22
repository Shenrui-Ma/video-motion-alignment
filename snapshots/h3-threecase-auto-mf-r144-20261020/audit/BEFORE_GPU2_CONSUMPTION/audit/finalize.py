"""Freeze all three actual automatic bindings, without authorizing GPU execution."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import bound, read, save, sha, validate_case


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gpu", required=True)
    a = p.parse_args()
    assert not (ROOT / "SEAL.json").exists()
    assert a.gpu.startswith("GPU-")
    protected = read(ROOT / "configs/EXISTING_SERVICES.json")["processes"]
    assert all(a.gpu != item["gpu_uuid"] for item in protected)
    runtime = read(ROOT / "configs/RUNTIME.json")
    runtime.update(gpu=a.gpu, peer_roots=[], status="ACTUAL_AUTOMATIC_BOUND_NOT_AUTHORIZED")
    plan = read(ROOT / "configs/PLAN.json")
    assert plan["jobs"] == [{"case": x, "role": "automatic"} for x in plan["groups"]]
    assert len(plan["jobs"]) == plan["unique_targets"] == plan["source_cache_count"] == 3
    for name in plan["groups"]:
        m = validate_case(ROOT / "cases" / name, "automatic", True)
        assert len(m["targets"]) == 1 and m["source_cache"]
        for key in ("actual_runtime_gate", "actual_producer_release"):
            ref = m["targets"][0][key]
            assert sha(ref["file"]) == ref["sha256"]
        from bind_automatic import check_gate
        proof = next(x for x in read(ROOT / "audit/SOURCE_CACHE_VERIFIED.json")["cases"]
                     if x["case"] == name)
        target = m["targets"][0]
        video = check_gate(read(target["actual_runtime_gate"]["file"]),
                           read(target["actual_producer_release"]["file"]), name, proof["geometry"])
        assert target["full_sha256"] == video["sha256"]
    save(ROOT / "configs/RUNTIME.json", runtime)
    plan["status"] = "ACTUAL_AUTOMATIC_BOUND_NOT_AUTHORIZED"
    save(ROOT / "configs/PLAN.json", plan)
    files = {}
    for top in ("scripts", "configs", "cases", "tests"):
        for path in sorted((ROOT / top).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                files[str(path.relative_to(ROOT))] = sha(path)
    for path in sorted((ROOT / "audit").glob("*.py")):
        files[str(path.relative_to(ROOT))] = sha(path)
    for name in ("SOURCE_CACHE_VERIFIED.json", "REMOTE_REUSE_PLAN.json", "CPU_CHECK.json",
                 "REMOTE_SMALL_FILE_CHECK.json", "REUSE_PROVENANCE.json"):
        path = ROOT / "audit" / name
        files[str(path.relative_to(ROOT))] = sha(path)
    for rel, digest in read(ROOT / "configs/ive_NUMERIC.json")["files"].items():
        assert sha(ROOT / "runtime/ive" / rel) == digest
        files["runtime/ive/" + rel] = digest
    save(ROOT / "SEAL.json", {"schema": "r144-official-mf-package-v1",
                                 "final_inputs_bound": True, "GPU_execution_authorized": False, "files": files})
    reuse = read(ROOT / "audit/REMOTE_REUSE_PLAN.json")
    upload = [x for x in files if not x.startswith("runtime/") and x not in reuse]
    upload += ["SEAL.json"]
    (ROOT / "audit/DEPLOY_FILES_AFTER_FINALIZE.txt").write_text("\n".join(upload) + "\n")
    print({"passed": True, "seal": bound(ROOT / "SEAL.json"), "targets": 3,
               "GPU_execution_authorized": False, "GPU_started": False})


if __name__ == "__main__":
    main()
