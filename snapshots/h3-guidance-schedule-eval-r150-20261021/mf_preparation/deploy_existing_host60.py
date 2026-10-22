"""Upload only a new sealed batch; reuse the already verified host60 runtime."""
import argparse
import json
import shlex
import subprocess
import time

from deploy_host60_cpu import ROOT, SSH, HOST, PYTHON, BASE, sha, save, remote, sync


def deploy(case):
    started = time.time()
    package = ROOT / "host60_batches" / case
    seal = json.loads((package / "SEAL.json").read_text())
    for rel, digest in seal["files"].items():
        assert sha(package / rel) == digest, rel
    prior = ROOT / "host60_batches/long_0039/audit/CPU_IMPORT_VERIFIED.json"
    proof = json.loads(prior.read_text())
    assert proof["passed"] and proof["CUDA_initialized"] is False
    assert proof["python"] == PYTHON
    files = sorted(seal["files"]) + ["SEAL.json", "ADMIN_DIFF.json",
                                   "ROOT_REVIEW_TEMPLATE.json"]
    listing = package / "audit/CPU_DEPLOY_FILES.txt"
    listing.write_text("\n".join(files) + "\n")
    target = BASE + "/" + case
    remote("from pathlib import Path\nPath(" + repr(target) +
           ").mkdir(parents=True,exist_ok=True)")
    sync(package, target, listing)
    prefix = ("cd " + shlex.quote(target) +
              " && PATH=/home/researcher/es/bin:$PATH CUDA_VISIBLE_DEVICES='' "
              "PYTHONDONTWRITEBYTECODE=1 " + shlex.quote(PYTHON))
    subprocess.run(SSH + [HOST, prefix + " audit/materialize_existing.py && " +
                         prefix + " audit/verify_inputs.py"], check=True,
                   capture_output=True, text=True)
    cpu = json.loads(remote("from pathlib import Path\nprint(Path(" +
                            repr(target + "/audit/TARGET_CPU_VERIFIED.json") +
                            ").read_text())"))
    assert cpu["passed"] and cpu["CUDA_started"] is False
    assert cpu["seal"]["sha256"] == sha(package / "SEAL.json")
    save(package / "audit/TARGET_CPU_VERIFIED.json", cpu)
    result = {
        "passed": True, "case": case, "seal_sha256": sha(package / "SEAL.json"),
        "target_cpu": {"file": str(package / "audit/TARGET_CPU_VERIFIED.json"),
                       "sha256": sha(package / "audit/TARGET_CPU_VERIFIED.json")},
        "prior_runtime_cpu_import": {"file": str(prior), "sha256": sha(prior)},
        "batch_upload_bytes": sum((package / p).stat().st_size for p in files),
        "runtime_reused": True, "model_reloaded": False,
        "started_unix": started, "completed_unix": time.time(),
        "CUDA_started": False, "external_downloads": 0, "packages_installed": 0}
    save(package / "audit/CPU_DEPLOYMENT.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    deploy(p.parse_args().case)
