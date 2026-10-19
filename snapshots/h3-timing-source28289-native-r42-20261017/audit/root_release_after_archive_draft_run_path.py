from pathlib import Path
import json,hashlib,time,urllib.request
r=Path("/data5/researcher/h3_runs/timing_source28289_native_r42_20261017")
run="r42_source_28289_seed2026101701_native"
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 t=p.with_suffix(p.suffix+".tmp");t.write_text(json.dumps(d,indent=2)+"\n");t.replace(p)
owner=read(r/"processes/service.json")
assert owner["pid"]==48733 and owner["identity"]["uid"]==1016 and owner["identity"]["start_ticks"]=="2623957929"
proc=Path("/proc")/str(owner["pid"])
assert proc.stat().st_uid==1016 and proc.joinpath("stat").read_text().rsplit(")",1)[1].split()[19]=="2623957929"
assert sha(proc/"cmdline")=="812b7e5ba61fc33906dc2c2076a019cb48ba2e3feea645b1e6cfa7b538b08809"
arc=r/"analysis/postrun/captured"/run
gp=arc/"RUN_GATE.json";gate=read(gp);receipt=read(arc.parent.parent/"archive_receipts"/(run+".json"))
assert gate["passed"] is True and gate["run_id"]==run and gate["owner"]==owner
assert receipt["run_gate_sha256"]==sha(gp) and receipt["inventory_sha256"]==sha(arc/"FILE_INVENTORY.json")
with urllib.request.urlopen("http://127.0.0.1:8504/queue",timeout=10) as response:q=json.load(response)
assert not q["queue_running"] and not q["queue_pending"]
c=read(r/"logs/controller_state.json");assert c["status"]=="resident_hold" and c["completed"]==[run]
qp=r/"configs/queue.json";queue=read(qp);assert queue["finalize"] is False
request={"pid":owner["pid"],"owner":owner["identity"],"gate_file":str(gp),"gate_sha256":sha(gp),"unix":time.time(),"empty_queue_verified":True}
save(r/"audit/root_release_request.json",request)
queue["finalize"]=True;save(qp,queue)
print(json.dumps({"release_requested":True,"pid":owner["pid"],"gate_sha256":sha(gp),"unix":request["unix"]}))
