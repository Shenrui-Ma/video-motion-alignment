"""Private SSH byte relay: four saved conditioning tensors and original AV noise."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
CASE = HERE / "cases/short_0358"
cache_path = CASE / "configs/CONDITION_CACHE.json"
contract_path = CASE / "configs/scientific_contract.json"
cache = json.loads(cache_path.read_text())
contract = json.loads(contract_path.read_text())
target = "/home/researcher/h3_runs/reference_feedback_r151_20261021/parents/short_0358"
files = [{"file": cache["conditioning"]["file"],
          "sha256": cache["conditioning"]["sha256"],
          "relative": "audit/" + Path(cache["conditioning"]["file"]).name}]
files += [{"file": row["file"], "sha256": row["sha256"],
           "relative": "audit/tensor_blobs/" + Path(row["file"]).name}
          for row in cache["tensors"]]
files.append({"file": contract["parent_noise_file"],
              "sha256": contract["parent_noise_sha256"],
              "relative": "audit/" + Path(contract["parent_noise_file"]).name})
source_code = "FILES=" + repr(files) + "\n" + r'''
import hashlib,sys,tarfile
from pathlib import Path
with tarfile.open(fileobj=sys.stdout.buffer,mode="w|") as archive:
 for row in FILES:
  p=Path(row["file"])
  h=hashlib.sha256()
  with p.open("rb") as f:
   for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
  assert h.hexdigest()==row["sha256"],str(p)
  archive.add(p,arcname=row["relative"],recursive=False)
'''
ssh = ["ssh", "-o", "ProxyCommand=none", "-o", "BatchMode=yes",
       "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15"]
started = time.time()
with (CASE / "audit/PRIVATE_TRANSFER_SOURCE.log").open("wb") as a, \
     (CASE / "audit/PRIVATE_TRANSFER_TARGET.log").open("wb") as b:
    source = subprocess.Popen(ssh + ["H3_SERVER_B",
                                    "python3 -c " + shlex.quote(source_code)],
                              stdout=subprocess.PIPE, stderr=a)
    destination = subprocess.Popen(
        ssh + ["H3_SERVER_A", "umask 077; mkdir -p " + shlex.quote(target) +
               "; tar -xf - -C " + shlex.quote(target)],
        stdin=source.stdout, stdout=b, stderr=b)
    source.stdout.close()
    destination_code = destination.wait()
    source_code = source.wait()
    if source_code or destination_code:
        raise RuntimeError((source_code, destination_code))
verify = "ROOT=" + repr(target) + "\nFILES=" + repr(files) + "\n" + r'''
import hashlib,json
from pathlib import Path
rows=[]
for row in FILES:
 p=Path(ROOT)/row["relative"];h=hashlib.sha256()
 with p.open("rb") as f:
  for chunk in iter(lambda:f.read(1048576),b""):h.update(chunk)
 assert h.hexdigest()==row["sha256"],str(p)
 rows.append(dict(row,target=str(p),bytes=p.stat().st_size))
print(json.dumps(rows))
'''
result = subprocess.run(ssh + ["H3_SERVER_A", "python3 -"], input=verify,
                        text=True, capture_output=True, check=True)
verified = json.loads(result.stdout)
receipt = {"schema": "r151-exact-private-input-relay-v1", "passed": True,
           "source_host": "H3_SERVER_B", "target_host": "H3_SERVER_A",
           "local_tensor_copies": 0, "GPU_started": False, "files": verified,
           "started_unix": started, "completed_unix": time.time()}
(CASE / "audit/PRIVATE_INPUT_TRANSFER.json").write_text(
    json.dumps(receipt, indent=2) + "\n")
old_parent = cache["parent_root"]
cache["parent_root"] = target
cache["conditioning"]["file"] = target + "/" + files[0]["relative"]
for row in cache["tensors"]:
    row["file"] = target + "/audit/tensor_blobs/" + Path(row["file"]).name
cache["historical_RGB_evidence"] = {
    "host": "H3_SERVER_B", "parent_root": old_parent,
    "conditioning_metadata_sha256": cache["conditioning"]["sha256"],
    "scope": "Original prepared RGB evidence stays at its original host; runtime loads only the four exact tensors."}
contract["parent_noise_file"] = target + "/" + files[-1]["relative"]
cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": True, "bytes": sum(x["bytes"] for x in verified),
                  "seconds": time.time() - started, "files": len(verified)}))
