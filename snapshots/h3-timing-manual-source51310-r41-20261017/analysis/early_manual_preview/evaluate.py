from pathlib import Path
import sys,json,hashlib,time,fcntl
R=Path("/Users/researcher/DevProjects/h3-timing-manual-source51310-r41-20261017/analysis/postrun")
sys.path.insert(0,str(R))
from evaluate_helpers import fixed_metrics,common_regions
import timing_metrics as metrics
from contract import read,sha,save,validate_phase
out=Path(__file__).resolve().parent
lock=Path("/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock")
with lock.open("a") as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print("BUSY");raise SystemExit(75)
 p=read(R/"PROTOCOL.json");arc=R/"captured"/p["cases"][0]["run_id"]
 rec=validate_phase(arc,"pose");source=arc/"configs/source.pose.json";native=R/p["parents"]["Native"]["pose"];manual=arc/"analysis/pose"/rec["metadata"]["pose_relative"]
 assert sha(source)==p["source_pose_sha256"] and sha(native)==p["parents"]["Native"]["pose_sha256"] and sha(manual)==rec["metadata"]["pose_sha256"]
 poses={"Native":native,"Manual":manual};start=time.monotonic()
 fixed=fixed_metrics(source,poses,p["cases"][0]["windows"],p["thresholds"],metrics)
 regions={"primary64_95":list(range(64,96)),"full0_140":list(range(141))}
 for a,b in p["cases"][0]["windows"]:regions[f"fixed{a}_{b}"]=list(range(a,b+1))
 common={str(c):common_regions(source,poses,regions,c,metrics) for c in p["thresholds"]}
 save(out/"RESULT.json",{"scope":"additional early descriptive Native/Manual preview using the five producer-predeclared windows; Auto final pending; final3way analysis unchanged","results":fixed,"common":common,"evidence":{str(q):sha(q) for q in [source,native,manual,R/"PROTOCOL.json"]},"elapsed_seconds":time.monotonic()-start})
 print("COMPLETE",out/"RESULT.json")
