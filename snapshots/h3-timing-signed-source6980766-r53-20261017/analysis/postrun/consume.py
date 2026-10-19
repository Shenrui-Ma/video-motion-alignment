"""Single CPU-only coordinator. Requires explicit --start and root-bound live owner."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']

def remote(args,timeout=900):
 temp=P['root_remote']+'/temp'
 cmd=shlex.join(['env','TMPDIR='+temp,'TMP='+temp,'TEMP='+temp,'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args])
 return subprocess.run(SSH+[HOST,cmd],capture_output=True,text=True,timeout=timeout)

def sync_download(run):
 target=HERE/'captured'/run;target.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),'--exclude=*.pt',HOST+':'+REMOTE+'/captured/'+run+'/',str(target)+'/'],check=True,timeout=600)
 validation=validate_local_inventory(target)
 original=read(target/'FILE_INVENTORY.json')
 for rel,d in original.items():
  if not rel.endswith('.pt'):require(sha(safe(target,rel))==d['sha256'],'downloaded archive changed '+rel)
 if (target/'DERIVED_FILES.json').exists():
  for rel,d in read(target/'DERIVED_FILES.json').items():require(sha(safe(target,rel))==d,'downloaded derived output changed '+rel)
 save(HERE/(run+'_DOWNLOAD.json'),{'original_inventory_sha256':sha(target/'FILE_INVENTORY.json'),'large_PT_archived_and_verified_remote':True,'local_inventory':validation,'download_scope':'all non-PT original and derived files; full raw tensors retained under exact remote archive','observed_unix':time.time()})

def parse_result(proc):
 require(proc.returncode==0,'remote CPU phase failed; do not retry uncertain phase automatically')
 lines=[x for x in proc.stdout.splitlines() if x.strip()]
 return json.loads(lines[-1])
