"""Collect an actual completed video and its small bound evidence, never tensors."""
from pathlib import Path
import hashlib
import io
import json
import shlex
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sid, arm = sys.argv[1:3]
case = HERE / "cases" / sid
runtime = json.loads((case / "configs/runtime.json").read_text())
contract = json.loads((case / "configs/scientific_contract.json").read_text())
row = next(x for x in contract["cases"] if x["arm"] == arm)
run = row["run_id"]
remote = runtime["remote_root"]
gate_rel = f"analysis/postrun/{sid}/{run}_GATE.json"
ssh = ["ssh", "-o", "ProxyCommand=none", "H3_SERVER_A"]
raw = subprocess.check_output(ssh + ["cat " + shlex.quote(remote + "/" + gate_rel)])
gate = json.loads(raw)
assert gate["schema"] == "r151-bidirectional-job-gate-v1" and gate["passed"]
assert gate["run_id"] == run and gate["role"] == arm
assert gate["producer_seal_sha256"] == hashlib.sha256((case / "deploy_manifest.json").read_bytes()).hexdigest()
assert gate["NFE"] == gate["Euler_updates"] == 20
assert gate["alpha"] == row["alpha"] and gate["beta"] == row["beta"]
assert gate["noise_sha256"] == contract["parent_noise_sha256"]
files = dict(gate["binding_artifacts"])
files[gate_rel] = hashlib.sha256(raw).hexdigest()
video_rel = str(Path(gate["video"]["file"]).relative_to(remote))
files[video_rel] = gate["video"]["sha256"]
for rel in files:
    assert not Path(rel).is_absolute() and ".." not in Path(rel).parts
    assert Path(rel).suffix in (".json", ".mp4")
destination = case
receipt_path = case / "actual" / run / "COLLECTED.json"
if receipt_path.exists():
    old = json.loads(receipt_path.read_text())
    assert old["gate_sha256"] == hashlib.sha256(raw).hexdigest()
    print(json.dumps(old))
    raise SystemExit(0)
script = "ROOT=" + repr(remote) + "\nFILES=" + repr(files) + "\n" + r'''
from pathlib import Path
import hashlib,sys,tarfile
root=Path(ROOT)
with tarfile.open(fileobj=sys.stdout.buffer,mode="w|") as t:
 for rel,expected in FILES.items():
  p=root/rel
  assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,rel
  t.add(p,arcname=rel,recursive=False)
'''
result = subprocess.run(ssh + ["python3 -c " + shlex.quote(script)], capture_output=True, check=True)
with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
    for member in archive:
        assert member.name in files and member.isfile()
        data = archive.extractfile(member).read()
        assert hashlib.sha256(data).hexdigest() == files[member.name]
        p = destination / member.name
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            assert hashlib.sha256(p.read_bytes()).hexdigest() == files[member.name]
        else:
            p.write_bytes(data)
receipt = {"schema": "r151-completed-job-collection-v1", "source_id": sid, "run_id": run,
           "arm": arm, "remote_root": remote, "gate_sha256": files[gate_rel],
           "gate": str(destination / gate_rel), "video": str(destination / video_rel),
           "video_sha256": gate["video"]["sha256"], "files": files,
           "batch_release": "Pending separate actual ROOT_EXIT; this is a completed-job preview."}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
