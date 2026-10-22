"""Copy small actual Native review receipts immediately before the tail launch."""
from pathlib import Path
import hashlib
import json
import shlex
import subprocess

P = Path(__file__).resolve().parents[1]
T = P / "sam_tail_host41/cases/sam07"
remote_query = r'''
from pathlib import Path
import base64,hashlib,json,time
p=Path("/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/sam07")
t=Path("/home/researcher/h3_runs/guidance_schedule_r150_sam_tail_host9_20261021/cases/sam07")
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
req=p/"audit/NATIVE_VISUAL_REVIEW_REQUEST.json";request=json.loads(req.read_text())
paths={"request":req,"review":p/"audit/NATIVE_VISUAL_REVIEW.json",
       "release":p/"audit/NATIVE_VISUAL_REVIEW_RELEASE.json","gate":Path(request["native_gate"])}
for root in [p,t]:
 for role in ["split","global_weak"]:
  run="r150_sam07_seed2026101311_"+role
  for rel in ["logs/"+run+"_job.json","audit/router/"+run+".json",
              "analysis/postrun/sam07/"+run+"_GATE.json"]:
   assert not (root/rel).exists(),str(root/rel)
assert not (t/"processes/service.json").exists()
assert (t/"audit/TAIL_REASSIGNED.json").exists()
assert "retired" in (t/"producer/launch_case.py").read_text().lower()
result={"observed_unix":time.time(),"prefix_seal_sha256":sha(p/"deploy_manifest.json"),
        "prefix_manifest_sha256":sha(p/"configs/MIGRATION_MANIFEST.json"),
        "prefix_allowed_roles":json.loads((p/"configs/execution_segment.json").read_text())["allowed_roles"],
        "prefix_tail_runs_absent":True,"old_tail_never_started":True,"old_tail_launch_retired":True,
        "old_tail_retirement_sha256":sha(t/"audit/TAIL_REASSIGNED.json"),
        "files":{n:{"path":str(f),"sha256":sha(f),"base64":base64.b64encode(f.read_bytes()).decode()}
                 for n,f in paths.items()}}
print(json.dumps(result))
'''
raw = subprocess.check_output(["ssh", "H3_SERVER_A", "python3 -c " + shlex.quote(remote_query)])
evidence = json.loads(raw)
manifest = json.loads((T / "configs/MIGRATION_MANIFEST.json").read_text())
assert evidence["prefix_seal_sha256"] == manifest["prefix_producer_seal_sha256"]
dest = json.loads((T / "configs/runtime.json").read_text())["remote_root"] + "/audit/PREFIX_NATIVE_EVIDENCE.json"
upload = "import pathlib,sys; p=pathlib.Path(sys.argv[1]); tmp=p.with_suffix('.tmp'); tmp.write_bytes(sys.stdin.buffer.read()); tmp.replace(p)"
subprocess.run(["ssh", "H3_SERVER_B", "python3 -c " + shlex.quote(upload) + " " +
                shlex.quote(dest)], input=raw, check=True)
local = T / "audit/PREFIX_NATIVE_EVIDENCE.json"
local.parent.mkdir(parents=True, exist_ok=True)
local.write_bytes(raw)
print(json.dumps({"file": dest, "sha256": hashlib.sha256(raw).hexdigest(),
                  "observed_unix": evidence["observed_unix"]}))
