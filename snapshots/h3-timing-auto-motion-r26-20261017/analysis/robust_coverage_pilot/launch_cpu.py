"""Single nonblocking Mac->remote CPU lock chain. No upload or GPU operation."""
import argparse,fcntl,hashlib,json,os,shlex,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
REMOTE='/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/robust_coverage_pilot'
PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'

def main():
    p=argparse.ArgumentParser();p.add_argument('--binding-name',required=True);p.add_argument('--output-name',required=True);a=p.parse_args()
    for name in (a.binding_name,a.output_name):
        if Path(name).name!=name or name in ('.','..'):raise ValueError('single path component required')
    binding=json.loads((HERE/a.binding_name).read_text())
    if binding.get('authorized_for_actual_evaluation') is not True:raise ValueError('not authorized')
    with (HERE/'unique_consumer.lock').open('a') as own,CPU.open('a') as shared:
        try:
            fcntl.flock(own,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit(75)
        args=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1',PYTHON,REMOTE+'/locked_remote.py',
              '--binding',REMOTE+'/'+a.binding_name,'--output',REMOTE+'/'+a.output_name,'--mac-owner',str(os.getpid())]
        identity={'mac_pid':os.getpid(),'started_unix':time.time(),'binding_sha256':hashlib.sha256((HERE/a.binding_name).read_bytes()).hexdigest(),'command':args}
        with (HERE/(a.output_name+'_launch.json')).open('x') as f:json.dump(identity,f,indent=2)
        # SSH loss/timeout is not automatically retried: inspect the one remote
        # child and partial output before any explicit recovery.
        return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3','H3_SERVER_A',shlex.join(args)],timeout=7200).returncode

if __name__=='__main__':raise SystemExit(main())
