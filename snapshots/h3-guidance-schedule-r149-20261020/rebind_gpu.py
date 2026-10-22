#!/usr/bin/env python3
"""Root-invoked GPU-only rebinding; retain original CPU proof and deploy five small files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
ALLOWED = {"gpu_index", "expected_gpu_index", "gpu_uuid"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def check_change(before, after):
    changes = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
    if not changes or not changes <= ALLOWED:
        raise ValueError("only a nonempty GPU UUID/index change is allowed")
    if (type(after["gpu_index"]) is not int or after["gpu_index"] < 0 or
        after["gpu_index"] != after["expected_gpu_index"] or
        not after["gpu_uuid"].startswith("GPU-")):
        raise ValueError("GPU binding is inconsistent")
    return sorted(changes)


MATCHER = '''def runtime_smoke_matches(root, smoke):
    root=Path(root)
    if smoke['runtime_sha256']==sha(root/'configs/runtime.json'):return True
    binding=read(root/'configs/runtime_device_rebind.json')
    import hashlib
    before=json.loads(binding['previous_runtime_json']);after=read(root/'configs/runtime.json')
    changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
    return (bool(changed) and changed<={'gpu_uuid','gpu_index','expected_gpu_index'}
        and type(after['gpu_index']) is int and after['gpu_index']>=0
        and after['expected_gpu_index']==after['gpu_index']
        and after['gpu_uuid'].startswith('GPU-')
        and hashlib.sha256(binding['previous_runtime_json'].encode()).hexdigest()==smoke['runtime_sha256']
        and binding['previous_smoke_sha256']==sha(root/'audit/RUNTIME_IMPORT_SMOKE.json')
        and binding['current_runtime_sha256']==sha(root/'configs/runtime.json'))


'''


def remote_check(runtime, old_runtime_sha, old_seal_sha, uuid, index):
    code = r'''
from pathlib import Path
import hashlib,json,os,subprocess,sys
p=Path(CONFIG["remote_root"])
assert hashlib.sha256((p/"configs/runtime.json").read_bytes()).hexdigest()==OLD_RUNTIME
assert hashlib.sha256((p/"deploy_manifest.json").read_bytes()).hexdigest()==OLD_SEAL
sys.path.insert(0,str(p/"scripts"))
import process_identity
service=p/"processes/service.json"
if service.exists():
 record=json.loads(service.read_text());row=process_identity.snapshot(record["pid"])
 if row is not None and process_identity.service_record(row)==record["identity"]:
  raise RuntimeError("original service generation is still live; no rebinding")
raw=subprocess.check_output(["nvidia-smi","--id="+GPU,"--query-gpu=index,uuid,memory.free,temperature.gpu",
                             "--format=csv,noheader,nounits"],text=True).strip()
parts=[x.strip() for x in raw.split(",")]
assert len(parts)==4 and parts[0]==str(INDEX) and parts[1]==GPU
assert parts[2].isdecimal() and int(parts[2])>=40960
assert parts[3].isdecimal() and int(parts[3])<85
apps=subprocess.check_output(["nvidia-smi","--id="+GPU,"--query-compute-apps=pid",
                              "--format=csv,noheader,nounits"],text=True).strip()
assert not apps, "target GPU has a compute process"
print(json.dumps({"passed":True,"gpu_raw":raw,"target_compute_empty":True,
                  "boot_id":Path("/proc/sys/kernel/random/boot_id").read_text().strip()}))
'''
    values = {"CONFIG": runtime, "OLD_RUNTIME": old_runtime_sha, "OLD_SEAL": old_seal_sha,
              "GPU": uuid, "INDEX": index}
    script = "\n".join(k + "=" + repr(v) for k, v in values.items()) + "\n" + code
    result = subprocess.run(["ssh", runtime["host"], "env PYTHONDONTWRITEBYTECODE=1 python3 -"],
                            input=script, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True, choices=("short_0252", "05_real_megumi_v"))
    parser.add_argument("--gpu-index", required=True, type=int)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--apply", required=True, action="store_true")
    parser.add_argument("--deploy", action="store_true")
    args = parser.parse_args()
    case = ROOT / "cases" / args.source_id
    path = case / "configs/runtime.json"
    before = read(path)
    after = dict(before, gpu_index=args.gpu_index, expected_gpu_index=args.gpu_index,
                 gpu_uuid=args.gpu_uuid)
    changed = check_change(before, after)
    old_seal = sha(case / "deploy_manifest.json")
    evidence = remote_check(before, sha(path), old_seal, args.gpu_uuid, args.gpu_index)
    smoke = read(case / "audit/RUNTIME_IMPORT_SMOKE.json")
    previous = path.read_text()
    if smoke["runtime_sha256"] != sha(path):
        old_binding = read(case / "configs/runtime_device_rebind.json")
        previous = old_binding["previous_runtime_json"]
    if hashlib.sha256(previous.encode()).hexdigest() != smoke["runtime_sha256"]:
        raise ValueError("original CPU proof runtime binding is unavailable")
    archive = case / "audit" / ("gpu_rebind_" + str(time.time_ns()))
    archive.mkdir()
    for rel in ("configs/runtime.json", "scripts/preflight.py", "deploy_manifest.json"):
        target = archive / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(case / rel, target)
    path.write_text(json.dumps(after, indent=2) + "\n")
    binding = {"schema": "r149-gpu-only-rebind-v1", "previous_runtime_json": previous,
               "previous_smoke_sha256": sha(case / "audit/RUNTIME_IMPORT_SMOKE.json"),
               "current_runtime_sha256": sha(path), "changed_fields_this_rebind": changed,
               "previous_seal_sha256": old_seal, "target_health": evidence,
               "science_and_cached_tensors_unchanged": True, "created_unix": time.time()}
    (case / "configs/runtime_device_rebind.json").write_text(json.dumps(binding, indent=2) + "\n")
    preflight = case / "scripts/preflight.py"
    text = preflight.read_text()
    begin, end = text.index("def runtime_smoke_matches("), text.index("def check(")
    preflight.write_text(text[:begin] + MATCHER + text[end:])
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable, str(case / "scripts/preflight.py")], check=True, env=env,
                   stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(case / "scripts/execution_gate.py"), "seal"],
                   check=True, env=env)
    files = ["configs/runtime.json", "configs/runtime_device_rebind.json",
             "scripts/preflight.py", "deploy_manifest.json"]
    if args.deploy:
        for rel in files:
            subprocess.run(["scp", str(case / rel), before["host"] + ":" +
                            before["remote_root"] + "/" + rel], check=True)
        script = ("import sys,json,hashlib\nfrom pathlib import Path\n"
                  "p=Path(" + repr(before["remote_root"]) + ")\n"
                  "sys.path.insert(0,str(p/'scripts'))\nimport preflight\n"
                  "m=json.loads((p/'deploy_manifest.json').read_text())\n"
                  "assert all(hashlib.sha256((p/k).read_bytes()).hexdigest()==v['sha256'] for k,v in m['files'].items())\n"
                  "s=json.loads((p/'audit/RUNTIME_IMPORT_SMOKE.json').read_text())\n"
                  "assert preflight.runtime_smoke_matches(p,s)\n"
                  "print(json.dumps(preflight.check(p)))\n")
        subprocess.run(["ssh", before["host"], "env PYTHONDONTWRITEBYTECODE=1 python3 -"],
                       input=script, text=True, check=True, stdout=subprocess.DEVNULL)
    result = {"passed": True, "source_id": args.source_id, "runtime": after,
              "previous_seal_sha256": old_seal, "seal_sha256": sha(case / "deploy_manifest.json"),
              "files_deployed": files if args.deploy else [], "cached_tensors_reloaded": False,
              "GPU_started": False, "next": "Root archives stale approvals/attempt state as appropriate, writes a fresh review for this seal, then uses the existing launcher."}
    (archive / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
