from pathlib import Path
import json,hashlib,time,urllib.request
r=Path("/data5/researcher/h3_runs/timing_source51765_native_r43_20261017")
run="r43_source_51765_seed2026101701_native"
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(d,indent=2)+"\n");t.replace(p)
owner=read(r/"processes/service.json")
assert owner["pid"]==37646 and owner["identity"]["uid"]==1016 and owner["identity"]["start_ticks"]=="2624194169"
proc=Path("/proc")/str(owner["pid"])
assert proc.stat().st_uid==1016 and proc.joinpath("stat").read_text().rsplit(")",1)[1].split()[19]=="2624194169"
assert sha(proc/"cmdline")=="05667e23441d611739d29d67bdb900096945db12d67416812f6671ef9a4d3b05"
arc=r/"analysis/postrun/captured/batch"
gp=arc/"RUN_GATE.json";gate=read(gp);receipt=read(arc.parent.parent/"archive_receipts/batch.json")
assert gate["passed"] is True and gate["run_id"]=="batch" and gate["runs"]==[run] and gate["owner"]==owner
assert receipt["run_gate_sha256"]==sha(gp) and receipt["inventory_sha256"]==sha(arc/"FILE_INVENTORY.json")
with urllib.request.urlopen("http://127.0.0.1:8505/queue",timeout=10) as response:q=json.load(response)
assert not q["queue_running"] and not q["queue_pending"]
c=read(r/"logs/controller_state.json");assert c["status"]=="resident_hold" and c["completed"]==[run]
qp=r/"configs/queue.json";queue=read(qp);assert queue["finalize"] is False
request={"pid":owner["pid"],"owner":owner["identity"],"gate_file":str(gp),"gate_sha256":sha(gp),"unix":time.time(),"empty_queue_verified":True}
save(r/"audit/root_release_request.json",request)
queue["finalize"]=True;save(qp,queue)
print(json.dumps({"release_requested":True,"pid":owner["pid"],"gate_sha256":sha(gp),"unix":request["unix"]}))
