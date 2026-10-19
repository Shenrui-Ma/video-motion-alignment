"""One bounded CPU phase on .41, with Mac and server shared locks."""
import argparse,fcntl,json,os,shlex,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
REMOTE='/data3/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/ivebench_physical_time_eval_20261017'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['pose','pair','manifest']);ap.add_argument('--pair');ap.add_argument('--method',choices=['native','auto']);ap.add_argument('--metric-inputs');a=ap.parse_args()
    args=[PYTHON,REMOTE+'/'+{'pose':'pose90.py','pair':'run_pair.py','manifest':'manifest.py'}[a.phase]]
    if a.phase in ['pose','pair']:
        if not a.pair:ap.error('--pair required')
        args+=['--pair',a.pair]
    if a.phase=='pose':
        if not a.method or not a.metric_inputs:ap.error('--method and --metric-inputs required')
        args+=['--method',a.method,'--metric-inputs',a.metric_inputs]
    if a.phase=='pair':args+=['--output',REMOTE+'/results/'+a.pair+'.json']
    with LOCK.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:print('MAC_CPU_BUSY');return 75
        command=' '.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4','NUMEXPR_NUM_THREADS=4','PYTHONDONTWRITEBYTECODE=1',shlex.join(args)])
        stamp=str(time.time_ns());(HERE/'audit').mkdir(exist_ok=True)
        p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','H3_SERVER_B',command],capture_output=True,text=True,timeout=420)
        (HERE/'audit'/f'{a.phase}_{stamp}.log').write_text(p.stdout+'\nSTDERR\n'+p.stderr)
        print(p.stdout);print(p.stderr);return p.returncode
if __name__=='__main__':raise SystemExit(main())
