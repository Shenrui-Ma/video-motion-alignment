"""Deploy exact existing MF assets over DIRECT SSH; never start CUDA or a tracker."""
import argparse
import hashlib
import json
import shlex
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SSH = ["ssh", "-o", "ProxyCommand=none", "-o", "BatchMode=yes"]
HOST = "H3_SERVER"
PYTHON = "/home/researcher/es/envs/comfyui/bin/python"
BASE = "/home/researcher/h3_runs/guidance_schedule_mf_r150_host60_20261021"
SHARED = BASE + "/shared/runtime/ive"
WEIGHT = SHARED + "/weights/baseline_offline.pth"
SOURCE_WEIGHT = "/data5/researcher/h3_runs/ivebench_forced_metrics_r63_20261018/runtime/weights/baseline_offline.pth"
WEIGHT_SHA = "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(1048576), b""):
            h.update(data)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def remote(code):
    result = subprocess.run(SSH + [HOST, "CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 " +
                                  shlex.quote(PYTHON) + " -"], input=code,
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-12000:] + result.stdout[-2000:])
    return result.stdout


def sync(source, target, files):
    subprocess.run(["rsync", "-a", "-e", "ssh -o ProxyCommand=none -o BatchMode=yes",
                    "--files-from=" + str(files), str(source) + "/",
                    HOST + ":" + target + "/"], check=True)


def main(case):
    started = time.time()
    package = ROOT / "host60_batches" / case
    seal = json.loads((package / "SEAL.json").read_text())
    for name, digest in seal["files"].items():
        assert sha(package / name) == digest, name
    runtime = (package / "runtime/ive").resolve()
    # The historical official-source manifest also pins a few inert CPython 3.12
    # cache files. Copy them as evidence; Python 3.11 does not execute these files.
    runtime_files = sorted(str(p.relative_to(runtime)) for p in runtime.rglob("*")
                           if p.is_file() and "weights" not in p.relative_to(runtime).parts)
    runtime_manifest = {name: sha(runtime / name) for name in runtime_files}
    save(ROOT / "HOST60_RUNTIME_FILES.json", runtime_manifest)
    listing = ROOT / "HOST60_RUNTIME_FILES.txt"
    listing.write_text("\n".join(runtime_files) + "\n")
    remote("from pathlib import Path\n" +
           "\n".join("Path(" + repr(p) + ").mkdir(parents=True,exist_ok=True)"
                     for p in [SHARED, SHARED + "/weights", BASE + "/" + case]))
    sync(runtime, SHARED, listing)
    existing = json.loads(remote(
        "import hashlib,json\nfrom pathlib import Path\np=Path(" + repr(WEIGHT) + ")\n"
        "print(json.dumps({'exists':p.is_file(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None}))"))
    transfer = {"reused": existing["sha256"] == WEIGHT_SHA, "bytes_streamed": 0}
    if not transfer["reused"]:
        assert not existing["exists"], "Refuse to replace a different existing checkpoint"
        stream_start = time.time()
        source = subprocess.Popen(SSH + ["H3_SERVER_A", "cat " + shlex.quote(SOURCE_WEIGHT)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        receiver = subprocess.Popen(SSH + [HOST, "umask 077; cat > " + shlex.quote(WEIGHT + ".partial")],
                                    stdin=source.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        source.stdout.close()
        _, target_error = receiver.communicate(timeout=300)
        _, source_error = source.communicate(timeout=30)
        assert source.returncode == receiver.returncode == 0, (
            "DIRECT SSH checkpoint stream failed", source_error.decode(), target_error.decode())
        proof = json.loads(remote(
            "import hashlib,json,os\nfrom pathlib import Path\np=Path(" + repr(WEIGHT + ".partial") + ")\n"
            "digest=hashlib.sha256(p.read_bytes()).hexdigest()\nassert digest==" + repr(WEIGHT_SHA) + "\n"
            "n=p.stat().st_size\nos.replace(p," + repr(WEIGHT) + ")\n"
            "print(json.dumps({'sha256':digest,'bytes':n}))"))
        transfer.update(bytes_streamed=proof["bytes"], seconds=time.time() - stream_start,
                        via="two configured DIRECT SSH streams; no local checkpoint file")
    save(package / "audit/CHECKPOINT_TRANSFER.json", transfer)
    files = sorted(seal["files"]) + ["SEAL.json", "ADMIN_DIFF.json", "ROOT_REVIEW_TEMPLATE.json"]
    filelist = package / "audit/CPU_DEPLOY_FILES.txt"
    filelist.write_text("\n".join(files) + "\n")
    sync(package, BASE + "/" + case, filelist)
    command = ("cd " + shlex.quote(BASE + "/" + case) +
               " && PATH=/home/researcher/es/bin:$PATH CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 " +
               shlex.quote(PYTHON) + " audit/materialize_existing.py && " +
               "PATH=/home/researcher/es/bin:$PATH CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 " +
               shlex.quote(PYTHON) + " audit/verify_inputs.py")
    checked = subprocess.run(SSH + [HOST, command], text=True, capture_output=True, check=True)
    cpu_file = BASE + "/" + case + "/audit/TARGET_CPU_VERIFIED.json"
    cpu = json.loads(remote("from pathlib import Path\nprint(Path(" + repr(cpu_file) + ").read_text())"))
    save(package / "audit/TARGET_CPU_VERIFIED.json", cpu)
    proof = json.loads(remote(
        "import os,sys,hashlib,json,time\nfrom pathlib import Path\n"
        "root=Path(" + repr(SHARED) + ")\nexpected=" + repr(runtime_manifest) + "\n"
        "for rel,h in expected.items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel\n"
        "sys.path.insert(0,str(root/'metric_runtime'))\n"
        "from ive_mf_adapter import official_class,verify_vendor\n"
        "import torch\n"
        "assert not torch.cuda.is_initialized() and os.environ['CUDA_VISIBLE_DEVICES']==''\n"
        "tick=time.time();torch.set_num_threads(2)\n"
        "model=official_class()(str(root/'weights/baseline_offline.pth'),device='cpu',grid_size=10,max_frames=None)\n"
        "assert not torch.cuda.is_initialized();assert next(model.model.parameters()).device.type=='cpu'\n"
        "print(json.dumps({'passed':True,'vendor':verify_vendor(),'runtime_files':len(expected),"
        "'weight_sha256':hashlib.sha256((root/'weights/baseline_offline.pth').read_bytes()).hexdigest(),"
        "'torch':torch.__version__,'python':sys.executable,'CUDA_initialized':False,"
        "'model_device':'cpu','cpu_model_load_seconds':time.time()-tick,'unix':time.time()}))"))
    save(package / "audit/CPU_IMPORT_VERIFIED.json", proof)
    result = {"passed": True, "case": case, "seal_sha256": sha(package / "SEAL.json"),
              "runtime_manifest": {"file": str(ROOT / "HOST60_RUNTIME_FILES.json"),
                                   "sha256": sha(ROOT / "HOST60_RUNTIME_FILES.json")},
              "checkpoint": transfer, "batch_upload_bytes": sum((package / p).stat().st_size for p in files),
              "runtime_upload_bytes": sum((runtime / p).stat().st_size for p in runtime_files),
              "target_cpu": {"file": str(package / "audit/TARGET_CPU_VERIFIED.json"),
                             "sha256": sha(package / "audit/TARGET_CPU_VERIFIED.json")},
              "cpu_import": {"file": str(package / "audit/CPU_IMPORT_VERIFIED.json"),
                             "sha256": sha(package / "audit/CPU_IMPORT_VERIFIED.json")},
              "started_unix": started, "completed_unix": time.time(),
              "CUDA_started": False, "external_downloads": 0, "packages_installed": 0}
    save(package / "audit/CPU_DEPLOYMENT.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["short_0085", "long_0039"], required=True)
    main(parser.parse_args().case)
