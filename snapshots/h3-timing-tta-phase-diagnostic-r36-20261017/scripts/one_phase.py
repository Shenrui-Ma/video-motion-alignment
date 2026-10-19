"""Explicit one CPU phase; Mac then remote lock; default never connects."""
import argparse,fcntl,os,shlex,subprocess,sys
from pathlib import Path
from contract import ROOT,REMOTE_ROOT,authorize

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared only: '+a.phase);return
    authorize(a.phase)
    if a.phase=='evaluate':args=['scripts/evaluate.py','--execute']
    else:
        kind,name,view=a.phase.split(':');assert kind=='pose' and view in ('flip','pad16')
        args=['scripts/run_pose_phase.py','--item',name,'--view',view,'--execute']
    unique=ROOT/'audit/one_phase.lock'
    with unique.open('a') as u:
        try:fcntl.flock(u,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        global_lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
        with global_lock.open('a') as g:
            try:fcntl.flock(g,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise SystemExit(75)
            remote=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4','/home/researcher/miniconda3/envs/comfyui/bin/python',REMOTE_ROOT+'/'+args[0],*args[1:]]
            cmd=['ssh','-J','H3_SERVER_B','-o','ConnectTimeout=15','H3_SERVER_A',shlex.join(remote)]
            result=subprocess.run(cmd,timeout=420)
            raise SystemExit(result.returncode)

if __name__=='__main__':main()
