"""Root-bounded CPU continuation after actual short_0263 release."""
import json,os,shlex,subprocess,time
from pathlib import Path
HOME=Path(__file__).resolve().parent
HOST='H3_SERVER_B'
ROOT='/data3/researcher/h3_runs/timing_ivebench_auto_r55_20261017'
POST=ROOT+'/analysis/postrun'
PHY='/data3/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/ivebench_physical_time_eval_20261017'
LPHY=Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/analysis/ivebench_physical_time_eval_20261017')
PY='/data3/researcher/ComfyUI/.venv/bin/python'
ENV=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4','MKL_NUM_THREADS=4',PY]
logdir=HOME/'short0263_completion';logdir.mkdir(exist_ok=True)
def phase(name,args):
 deadline=time.monotonic()+1200;attempt=0
 while time.monotonic()<deadline:
  attempt+=1
  p=subprocess.run(['ssh','-o','ConnectTimeout=10',HOST,shlex.join(ENV+args)],capture_output=True,text=True,timeout=600)
  (logdir/(name+'_'+str(attempt)+'.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
  if p.returncode==0:
   print(name,'PASS',flush=True);return
  if p.returncode!=75:raise RuntimeError(name+' failed; inspect '+str(logdir))
  time.sleep(25)
 raise TimeoutError(name+' remained CPU/online busy; retry after reviewing logs')
def fetch(remote,local):
 local.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-a','-e','ssh -o ConnectTimeout=10',HOST+':'+remote+'/',str(local)+'/'],check=True,timeout=180)
phase('identity',[POST+'/audit/run_identity_pair.py','--pair','short_0263'])
phase('score_reuse',[POST+'/audit/reuse_ive_score.py','--pair','short_0263'])
fetch(POST+'/audit/media_identity/short_0263',HOME/'media_identity/short_0263')
metric=POST+'/completed_cases/r55_short_0263_seed2026101701_auto/final/r55_short_0263_seed2026101701_auto/METRIC_INPUTS.json'
phase('pose',[PHY+'/admin/runtime_priority_v2/run_phase.py','pose','--pair','short_0263','--method','auto','--metric-inputs',metric])
phase('physical_pair',[PHY+'/admin/runtime_priority_v2/run_phase.py','pair','--pair','short_0263','--output',PHY+'/results/short_0263.json'])
fetch(PHY+'/records/auto_short_0263',LPHY/'records/auto_short_0263')
(LPHY/'results').mkdir(exist_ok=True)
subprocess.run(['rsync','-a','-e','ssh -o ConnectTimeout=10',HOST+':'+PHY+'/results/short_0263.json',str(LPHY/'results/short_0263.json')],check=True,timeout=180)
print('COMPLETE',flush=True)
