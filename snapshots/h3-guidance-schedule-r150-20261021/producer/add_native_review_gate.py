"""Add the requested visual Native checkpoint to two unstarted producers."""
from pathlib import Path
import hashlib
import json
import shlex
import shutil
import subprocess

P = Path(__file__).resolve().parents[1]
for root in [P / "cases/firefly06", P / "host9/cases/sam07"]:
    before = (root / "deploy_manifest.json").read_bytes()
    old = json.loads(before)
    old_sha = hashlib.sha256(before).hexdigest()
    archive = root / "producer/PRE_NATIVE_REVIEW"
    archive.mkdir(exist_ok=False)
    shutil.copy2(root / "deploy_manifest.json", archive / "deploy_manifest.json")
    shutil.copy2(root / "scripts/run_queue.py", archive / "run_queue.py")
    shutil.copy2(P / "producer/native_review_gate.py", root / "scripts/native_review_gate.py")
    path = root / "scripts/run_queue.py"
    text = path.read_text()
    marker = "            state(status='arm_verified',current=None,completed=completed[:])"
    assert text.count(marker) == 1
    text = text.replace(marker, marker + "\n"
                        "            from native_review_gate import wait_native_review\n"
                        "            wait_native_review(service.RUN,run_id,owner,state)")
    compile(text, str(path), "exec")
    path.write_text(text)
    subprocess.run(["python3", "scripts/execution_gate.py", "seal"], cwd=root, check=True)
    new = json.loads((root / "deploy_manifest.json").read_text())
    changed = {rel for rel in set(old["files"]) | set(new["files"])
               if old["files"].get(rel) != new["files"].get(rel)}
    assert changed == {"scripts/run_queue.py", "scripts/native_review_gate.py"}, changed
    runtime = json.loads((root / "configs/runtime.json").read_text())
    remote = runtime["remote_root"]
    payload = {rel: (root / rel).read_text()
               for rel in ["scripts/run_queue.py", "scripts/native_review_gate.py",
                           "deploy_manifest.json"]}
    code = """from pathlib import Path
import json,sys,hashlib
root=Path(sys.argv[1]);expected=sys.argv[2]
assert hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest()==expected
assert not (root/'processes/service.json').exists(),'already launched'
assert not list((root/'audit/x0').glob('*')),'sampling exists'
archive=root/'audit/PRE_NATIVE_REVIEW';archive.mkdir(exist_ok=False)
for rel in ['deploy_manifest.json','scripts/run_queue.py','audit/TARGET_CPU_VALIDATION.json','audit/RUNTIME_IMPORT_SMOKE.json']:
 p=root/rel
 if p.exists():q=archive/rel;q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)
for rel,text in json.loads(sys.stdin.read()).items():(root/rel).write_text(text)
print(hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest())
"""
    subprocess.run(["ssh", runtime["host"],
                    "python3 -c " + shlex.quote(code) + " " +
                    shlex.quote(remote) + " " + shlex.quote(old_sha)],
                   input=json.dumps(payload).encode(), check=True)
    command = ("cd " + shlex.quote(remote) +
               " && CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=" +
               shlex.quote(runtime["dependencies"]) + " " + shlex.quote(runtime["python"]) +
               " scripts/remote_cpu_validate.py")
    with (root / "producer/CPU_NATIVE_REVIEW.log").open("x") as log:
        subprocess.run(["ssh", runtime["host"], command], stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    for rel in ["audit/TARGET_CPU_VALIDATION.json", "audit/RUNTIME_IMPORT_SMOKE.json"]:
        (root / rel).write_bytes(subprocess.check_output(
            ["ssh", runtime["host"], "cat " + shlex.quote(remote + "/" + rel)]))
    new_sha = hashlib.sha256((root / "deploy_manifest.json").read_bytes()).hexdigest()
    result = {"root": str(root), "remote_root": remote, "old_seal": old_sha,
              "new_seal": new_sha, "changed_files": sorted(changed),
              "scientific_files_unchanged": True, "target_CPU_passed": True}
    (root / "producer/NATIVE_REVIEW_CHANGE.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
