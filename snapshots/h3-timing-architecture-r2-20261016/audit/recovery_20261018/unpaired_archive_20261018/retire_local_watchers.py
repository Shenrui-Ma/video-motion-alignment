"""Retire only explicitly bound local CPU waiters for held R72/R74 pairs."""
import hashlib,json,os,signal,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
TARGETS=[(84838,"/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv-current/bin/python /Users/researcher/DevProjects/h3-flexiact-official-six-metrics-r74-20261018/scripts/watch_pairs.py"),(62606,"/Users/researcher/DevProjects/diffsynth-h3-next-study-20261013/.venv/bin/python /Users/researcher/DevProjects/h3-timing-flexiact-prompt-pair-r72-20261018/audit/consumer/sync_publish.py --watch-hours 12")]
def identity(pid):
 r=subprocess.run(["ps","-p",str(pid),"-o","uid=,pid=,lstart=,command="],capture_output=True,text=True,check=False)
 if r.returncode==1 and not r.stdout.strip():return None
 assert r.returncode==0,r.stderr
 return r.stdout.strip()
def children(pid):
 out=subprocess.check_output(["ps","-axo","pid=,ppid="],text=True)
 return [int(a) for a,b in (line.split() for line in out.splitlines()) if int(b)==pid]
def save(name,obj):
 (HERE/name).write_text(json.dumps(obj,indent=2)+"\n")
rows=[]
for pid,cmd in TARGETS:
 before=identity(pid)
 if before is None:
  rows.append({"pid":pid,"already_absent":True});continue
 assert int(before.split()[0])==os.getuid(),before
 assert before.endswith(cmd),before
 deadline=time.monotonic()+30
 while children(pid) and time.monotonic()<deadline:time.sleep(.25)
 assert not children(pid),children(pid)
 save(str(pid)+"_BEFORE.json",{"identity":before,"children":[],"requested_command":cmd,"unix":time.time()})
 assert identity(pid)==before
 os.kill(pid,signal.SIGTERM)
 deadline=time.monotonic()+10
 while identity(pid)==before and time.monotonic()<deadline:time.sleep(.1)
 after=identity(pid)
 assert after is None or after!=before,(pid,after)
 rows.append({"pid":pid,"identity":before,"original_process_absent":True,"after":after,"signal":"SIGTERM"})
save("LOCAL_CPU_WATCHERS_RETIRED.json",{"scope":"Held R72/R74 CPU waiters only","rows":rows,"GPU_calls":0,"unix":time.time()})
print(json.dumps(rows))
