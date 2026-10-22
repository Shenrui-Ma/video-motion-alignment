import json,subprocess,pathlib
R=pathlib.Path(__file__).resolve().parent
code='''import pathlib,json,time,hashlib
b=pathlib.Path("/data5/researcher/h3_runs")
names=["timing_ive_p1_guidance_r99_20261019","timing_flexiact_character_guidance_r101_20261019","timing_ive_task_repair_r100_20261019","timing_flexiact_fitness_pair_r94_20261018","timing_flexiact_p1_control_r90_20261018","timing_ive_event_candidates_r93_20261018"]
out={"observed_unix":time.time(),"scope":"one read-only small-JSON snapshot; no runtime import or CUDA","roots":{}}
for name in names:
 p=b/name; row={"exists":p.exists(),"receipts":{},"jobs":{}}
 qs=list(p.glob("audit/*/STARTED.json"))+list(p.glob("audit/*/COMPLETE.json"))+list(p.glob("processes/service.json"))+list(p.glob("analysis/postrun/*/*GATE*.json"))
 for q in qs:
  if "watchdog" in str(q):continue
  raw=q.read_bytes();d=json.loads(raw); x={"file":str(q),"sha256":hashlib.sha256(raw).hexdigest()}
  if q.name=="service.json": x.update({k:d.get(k) for k in ["pid","identity","port","gpu_uuid","started_unix"]});x["proc_exists"]=pathlib.Path("/proc/"+str(d["pid"])).exists()
  else: x.update({k:d.get(k) for k in ["passed","state","status","run_id","source_id","service_pid","service_owner","created_unix"] if k in d})
  row["receipts"][str(q.relative_to(p))]=x
 for q in p.glob("logs/*_job.json"):
  d=json.load(open(q));row["jobs"][q.name]={k:d.get(k) for k in ["run_id","prompt_id","state","status","submitted_unix","completed_unix"] if k in d}
 out["roots"][name]=row
print(json.dumps(out))'''
p=subprocess.run(['ssh','-o','ConnectTimeout=20','H3_SERVER_A','python3 -'],input=code,text=True,capture_output=True,timeout=45)
(R/'snapshots/REMOTE_STATUS.stderr.txt').write_text(p.stderr)
p.check_returncode();d=json.loads(p.stdout);(R/'snapshots/REMOTE_STATUS.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for k,v in d['roots'].items():print(k,[(key,x.get('pid'),x.get('proc_exists')) for key,x in v['receipts'].items()],list(v['jobs']))
