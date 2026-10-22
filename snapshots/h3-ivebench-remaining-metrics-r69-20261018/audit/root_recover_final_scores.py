"""Complete only the two unstarted scores after a CPU lock collision."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/data3/researcher/h3_runs/ivebench_remaining_metrics_r69_20261018')
PRODUCER=ROOT.parent/'timing_ivebench_remaining_r69_20261018'
PEER=ROOT.parent/'timing_flexiact_prompt_pair_r72_20261018'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
sys.path.insert(0,str(PRODUCER/'scripts'))
import service

def read(p):return json.loads(p.read_text())
def main():
 audit=ROOT/'audit/root_finish_remaining_attempt2';audit.mkdir(exist_ok=False)
 assert read(ROOT/'audit/root_remaining_targets_attempt1/COMPLETE.json')['passed']
 pids=[470280,471455,470267]
 assert all(not Path('/proc',str(p)).exists() for p in pids)
 assert not any(r['pid'] in pids for r in service.compute_processes())
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
 for method in ['native','forced']:
  target=ROOT/'results/short_0370'/f'{method}_source1_target1.json'
  assert not target.exists(), target
  for attempt in range(180):
   r=subprocess.run([PYTHON,'scripts/score_one.py','--source','short_0370','--method',method],cwd=ROOT,env=env,capture_output=True,text=True)
   (audit/f'{method}_{attempt}.log').write_text(r.stdout+'\n'+r.stderr)
   if r.returncode==0:break
   if 'BlockingIOError: [Errno 11]' in r.stderr and 'flock' in r.stderr:time.sleep(10);continue
   raise RuntimeError(r.stderr)
  else:raise TimeoutError('CPU lock unavailable')
  print(method,read(target)['motion_fidelity'],flush=True)
 plan=read(PRODUCER/'configs/queue.json');plan['finalize']=True;service.write_json(PRODUCER/'configs/queue.json',plan)
 admission=PEER/'configs/admission.json';a=read(admission)
 a['permitted_compute_processes']=[r for r in a['permitted_compute_processes'] if r['pid']!=470280]
 service.write_json(admission,a)
 record={'passed':True,'exact_pids_absent':pids,'CUDA_allocation_absent':True,'unix':time.time(),'recovery':'two remaining CPU scores only; all prior GPU results reused with binding checks','prior_failure':str(ROOT/'audit/root_finish_remaining_attempt1/FAILURE.json')}
 service.write_json(audit/'COMPLETE.json',record)
 print(json.dumps(record),flush=True)
if __name__=='__main__':main()
