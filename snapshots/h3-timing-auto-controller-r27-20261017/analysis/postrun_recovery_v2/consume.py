"""Explicit one-phase transport; no resident consumer, service or GPU controls."""
import os,shlex,subprocess,time
from recovery_contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun_recovery_v2';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']

def remote(args):
 mode=args[0];budget=P['recovery']['timeout_seconds'].get(mode,180)
 cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','/usr/bin/timeout','--signal=TERM','--kill-after=15s',str(budget)+'s',PYTHON,REMOTE+'/remote_consume.py',*args])
 return subprocess.run(SSH+[HOST,cmd],capture_output=True,text=True,timeout=budget+60)

def parse_result(proc):
 require(proc.returncode==0,'remote phase failed/timeout; retain evidence and do not automatically retry')
 return json.loads([x for x in proc.stdout.splitlines() if x.strip()][-1])

def sync_download(run):
 target=HERE/'captured'/run;target.mkdir(parents=True,exist_ok=True);old=P['recovery']['remote_original_postrun']+'/captured/'+run
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),'--exclude=*.pt',HOST+':'+old+'/',str(target)+'/'],check=True,timeout=P['recovery']['timeout_seconds']['download'])
 check=validate_local_inventory(target)
 save(HERE/(run+'_DOWNLOAD.json'),{'original_inventory_sha256':sha(target/'FILE_INVENTORY.json'),'derived_inventory_sha256':sha(target/'DERIVED_FILES.json'),'local_inventory':check,'large_PT_archived_and_verified_remote':True,'remote_archive':old,'observed_unix':time.time()})
 return check
