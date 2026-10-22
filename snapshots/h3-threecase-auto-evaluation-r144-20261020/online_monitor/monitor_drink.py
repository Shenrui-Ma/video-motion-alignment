"""Read only small producer summaries every 60 seconds; stop at terminal receipt."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

OUT = Path(__file__).resolve().parent
REMOTE = "/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases/short_0358_cached_gpu2"
ATTEMPT = "root_r144_short_0358_cached_gpu2_attempt1"
HOST = "H3_SERVER_B"
REMOTE_SCRIPT = r'''
import hashlib,json,time
from pathlib import Path
r=Path(REMOTE);a=r/'audit'/ATTEMPT
out={'observed_unix':time.time(),'host_alias':HOST,'remote_root':str(r),'attempt':ATTEMPT,'evidence':{}}
paths={'step_log':r/'audit/AUTO_STEP_LOG.json','started':a/'STARTED.json',
 'failure':a/'FAILURE.json','cleanup_failure':a/'CLEANUP_FAILURE.json',
 'actual_success':a/'ACTUAL_SUCCESS.json','complete':a/'COMPLETE_REVIEW_HOLD.json',
 'release':a/'ROOT_EXIT_RECEIPT.json','gate':r/'analysis/postrun/ONLINE_RUNTIME_GATE.json'}
for name,p in paths.items():
 if not p.is_file():continue
 b=p.read_bytes()
 if len(b)>200000:raise ValueError('Summary unexpectedly too large: '+str(p))
 d=json.loads(b)
 out['evidence'][name]={'file':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'mtime_ns':p.stat().st_mtime_ns}
 if name=='step_log':
  out['progress']={k:v for k,v in d.items() if k!='steps'}
  out['steps']=[];previous=[];last_on=None
  for step in d.get('steps',[]):
   summary={k:v for k,v in step.items() if k!='detected_candidates'}
   candidates=step.get('detected_candidates',[])
   top=max(candidates,key=lambda c:c['absolute_gain']) if candidates else None
   summary['highest_absolute_gain_candidate']=top
   summary['previous_step_selected']=previous
   summary['last_ON']=last_on
   relations=[]
   for selected in previous:
    if top:
     x,y=top['window'],selected['window']
     intersection=max(0,min(x[1],y[1])-max(x[0],y[0])+1)
     relations.append({'selected_window':y,'selected_feature':selected['feature'],
       'same_feature':top['feature']==selected['feature'],
       'inclusive_overlap_over_shorter':intersection/min(x[1]-x[0]+1,y[1]-y[0]+1),
       'candidate_lags':top['lags'],'selected_lags':selected['lags']})
   summary['highest_candidate_vs_previous_selection']=relations
   out['steps'].append(summary);previous=step.get('selected',[])
   if step.get('state')=='ON':last_on={'physical_index':step['physical_index'],'selected':previous}
 elif name in ('failure','cleanup_failure'):
  out[name]={k:v for k,v in d.items() if k in ('error','errors','primary','unix')}
 elif name in ('complete','actual_success'):
  out[name]={k:v for k,v in d.items() if k!='service'}
 elif name=='release':
  out[name]={'passed':d.get('passed'),'unix':d.get('unix'),
   'service_pid':(d.get('service') or {}).get('pid'),
   'service_identity':(d.get('service') or {}).get('identity'),
   'process_absent':(d.get('service_cleanup') or {}).get('process_absent'),
   'own_compute_absent':(d.get('service_cleanup') or {}).get('own_compute_absent'),
   'all_exact_generations_absent':(d.get('observer_children') or {}).get('all_exact_generations_absent'),
   'all_registered_CUDA_pids_absent':(d.get('observer_children') or {}).get('all_registered_CUDA_pids_absent')}
 elif name=='gate':
  out[name]={k:d.get(k) for k in ('passed','status','verified_runs','valid_frames','video','efficiency')}
print(json.dumps(out,separators=(',',':')))
'''


def write_json(name, data):
    path = OUT / name
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def main():
    previous_steps = {}
    if (OUT / "LATEST.json").exists():
        for step in json.loads((OUT / "LATEST.json").read_text()).get("steps", []):
            previous_steps[step["physical_index"]] = step
    source = ("REMOTE=" + repr(REMOTE) + "\nATTEMPT=" + repr(ATTEMPT)
              + "\nHOST=" + repr(HOST) + "\n" + REMOTE_SCRIPT)
    while True:
        began = time.monotonic()
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                 HOST, "python3 -"],
                input=source, text=True, capture_output=True, timeout=40, check=True,
            )
            row = json.loads(result.stdout)
            row["monitor_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            write_json("LATEST.json", row)
            compact = {k: v for k, v in row.items() if k not in ("steps", "gate", "release")}
            changed = []
            for step in row.get("steps", []):
                index = step["physical_index"]
                if previous_steps.get(index) != step:
                    changed.append(step)
                    previous_steps[index] = step
            compact["new_or_changed_steps"] = changed
            with (OUT / "TIMELINE.jsonl").open("a") as handle:
                handle.write(json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\n")
            if changed:
                print(json.dumps({"progress": row["progress"], "new_steps": changed},
                                 ensure_ascii=False, separators=(",", ":")), flush=True)
            terminal = next((k for k in ("failure", "cleanup_failure", "complete") if k in row), None)
            if terminal:
                write_json("FINAL.json", {**row, "terminal_kind": terminal,
                                          "read_only": True, "poll_seconds": 60,
                                          "no_followup_launched": True})
                print(json.dumps({"terminal": terminal, "progress": row.get("progress"),
                                  "details": row[terminal], "final": str(OUT / "FINAL.json")},
                                 ensure_ascii=False, separators=(",", ":")), flush=True)
                return
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            row = {"observed_unix": time.time(), "monitor_error": repr(error),
                   "experiment_terminal_not_inferred": True}
            with (OUT / "TIMELINE.jsonl").open("a") as handle:
                handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            print(json.dumps(row, separators=(",", ":")), flush=True)
        time.sleep(max(0, 60 - (time.monotonic() - began)))


if __name__ == "__main__":
    main()
