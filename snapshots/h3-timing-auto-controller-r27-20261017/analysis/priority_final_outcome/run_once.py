"""Bounded independent priority evaluator: no producer or formal-consumer mutation."""
import fcntl,json,os,shlex,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REMOTE='/data5/researcher/h3_runs/timing_auto_controller_r27_20261017/analysis/priority_final_outcome'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3','H3_SERVER_A']
PY='/home/researcher/miniconda3/envs/comfyui/bin/python'

if __name__=='__main__':
    unique=(H/'unique.lock').open('a');fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (H/'IDENTITY.json').write_text(json.dumps({'pid':os.getpid(),'started_unix':time.time(),'scope':'two CPU phases; formal consumer untouched'},indent=2)+'\n')
    print(json.dumps({'priority_pid':os.getpid()}),flush=True)
    for phase in ['imports','pose','metrics']:
        while True:
            busy=False
            with CPU.open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:busy=True
                if not busy:
                    cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',PY,REMOTE+'/evaluate_priority.py',phase])
                    r=subprocess.run(SSH+[cmd],capture_output=True,text=True,timeout=600)
                    (H/f'{phase}_{time.time_ns()}.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
                    if r.returncode==75:busy=True
                    elif r.returncode:
                        print(r.stdout+r.stderr,flush=True);raise SystemExit(r.returncode)
                    else:print(r.stdout,flush=True)
            if not busy:break
            print(json.dumps({'phase':phase,'status':'waiting_CPU_or_online_priority','unix':time.time()}),flush=True)
            time.sleep(25)
    (H/'EXECUTION_COMPLETE.json').write_text(json.dumps({'passed':True,'finished_unix':time.time(),'no_GPU':True},indent=2)+'\n')
