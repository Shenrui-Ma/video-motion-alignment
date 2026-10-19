"""CPU-only remote entry, called by the Mac lock owner after explicit review."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
GLOBAL=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')

def main():
    p=argparse.ArgumentParser();p.add_argument('--binding',required=True);p.add_argument('--output',required=True);p.add_argument('--mac-owner',required=True,type=int);a=p.parse_args()
    if a.mac_owner<=0:raise ValueError('Mac owner identity required')
    if str(HERE)!='/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/robust_coverage_pilot':raise ValueError('wrong isolated remote root')
    with (HERE/'unique_consumer.lock').open('a') as own,GLOBAL.open('a') as shared:
        try:
            fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',H3_ROBUST_PILOT_LOCKED='mac_then_remote',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        print(json.dumps({'remote_pid':os.getpid(),'mac_owner':a.mac_owner,'started_unix':time.time(),'scope':'CPU-only completed-archive evaluation'}),flush=True)
        return subprocess.run([sys.executable,str(HERE/'evaluate.py'),'--binding',a.binding,'--output',a.output],env=env).returncode

if __name__=='__main__':raise SystemExit(main())
