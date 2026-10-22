"""Explicit one CPU phase; durable driver journal; Mac then remote lock."""
import argparse,fcntl,shlex,subprocess,sys,time,traceback
from pathlib import Path
from contract import ROOT,REMOTE_ROOT,authorize,read,require,save
from phase_artifacts import create_attempt


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if not a.execute:print('Prepared only: '+a.phase);return
    authorize(a.phase);plan=read(ROOT/'PHASE_PLAN.json')
    require(a.phase in plan['pose_phases']+[plan['evaluation_phase']],'Unregistered phase')
    if a.phase=='evaluate':args=['scripts/evaluate.py','--execute']
    else:
        kind,name,view=a.phase.split(':');require(kind=='pose' and view in ('flip','pad16'),'Pose phase')
        args=['scripts/run_pose_phase.py','--item',name,'--view',view,'--execute']
    with (ROOT/'audit/one_phase.lock').open('a') as unique:
        try:fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        global_lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
        with global_lock.open('a') as gl:
            try:fcntl.flock(gl,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise SystemExit(75)
            journal=create_attempt(ROOT/'audit/driver_calls');started=time.monotonic()
            remote=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4','/home/researcher/miniconda3/envs/comfyui/bin/python',REMOTE_ROOT+'/'+args[0],*args[1:]]
            cmd=['ssh','-J','H3_SERVER_B','-o','ConnectTimeout=15','H3_SERVER_A',shlex.join(remote)]
            save(journal/'START.json',{'phase':a.phase,'command':cmd,'started_unix':time.time(),'GPU':False})
            try:
                with (journal/'remote.log').open('x') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=420)
                save(journal/'RESULT.json',{'phase':a.phase,'returncode':result.returncode,'status':'completed_or_reused' if result.returncode==0 else 'busy_no_new_work' if result.returncode==75 else 'technical_failure','elapsed_seconds':time.monotonic()-started})
                print(f'Phase {a.phase}: exit {result.returncode}; journal {journal}')
                raise SystemExit(result.returncode)
            except SystemExit:raise
            except BaseException as exc:
                save(journal/'FAILURE.json',{'phase':a.phase,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),'elapsed_seconds':time.monotonic()-started,'remote_retry':'only same explicit phase after lock/liveness/complete checks; no automatic duplicate'})
                raise

if __name__=='__main__':main()
