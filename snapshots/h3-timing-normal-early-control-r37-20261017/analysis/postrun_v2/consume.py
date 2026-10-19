"""Transport helpers only; no resident consumer or GPU/service management."""
import os,shlex,subprocess,time
from contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun_v2';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']
def remote(args,timeout=900):
 cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args]);return subprocess.run(SSH+[HOST,cmd],capture_output=True,text=True,timeout=timeout)
def parse_result(proc):
 require(proc.returncode==0,'remote phase failed; explicit review before retry');return json.loads([s for s in proc.stdout.splitlines() if s.strip()][-1])
def sync_download():
 run=P['cases'][0]['run_id'];target=HERE/'captured'/run;target.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),'--exclude=*.pt',HOST+':'+P['recovery']['archive_root']+'/',str(target)+'/'],check=True,timeout=600)
 result=validate_delivery(target,local=True);save(HERE/'DOWNLOAD.json',{'run':run,'observed_unix':time.time(),'inventory_sha256':sha(target/'FILE_INVENTORY.json'),'validation':result,'all_large_PT_remain_verified_remote':True});return result
