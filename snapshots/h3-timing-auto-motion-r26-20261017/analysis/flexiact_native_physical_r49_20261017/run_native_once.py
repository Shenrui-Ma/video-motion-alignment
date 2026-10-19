"""Administrative single-case launch with the existing Mac/server CPU locks."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = '/data5/researcher/h3_runs'
REMOTE = BASE + '/timing_auto_motion_r26_20261017/analysis/flexiact_native_physical_r49_20261017'
GENERATED = BASE + '/timing_auto_motion_r26_20261017/analysis/flexiact_generated_pose158_20261017'
SOURCE = BASE + '/timing_flexiact_native_r49_20261017/analysis/source_pose158_sidecar'
SSH = ['ssh', '-J', 'H3_SERVER_B', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15']
PYTHON = '/home/researcher/miniconda3/envs/comfyui/bin/python'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, choices=['chest', 'crouch', 'fitness', 'one_leg', 'rotate'])
    source = parser.parse_args().source
    lock = Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('BUSY_MAC'); return
    generated_local = HERE.parent / 'flexiact_generated_pose158_20261017'
    subprocess.run([sys.executable, str(generated_local / 'manifest.py')], check=True, timeout=30)
    subprocess.run(['rsync', '-a', '-e', shlex.join(SSH), str(generated_local / 'MANIFEST.json'),
                    'H3_SERVER_A:' + GENERATED + '/MANIFEST.json'], check=True, timeout=40)
    argv = [REMOTE + '/run_native.py', '--binding-root', BASE + '/flexiact_physical_time_run_20261017',
            '--generated-manifest', GENERATED + '/MANIFEST.json', '--source-manifest', SOURCE + '/MANIFEST.json',
            '--source-protocol', SOURCE + '/PROTOCOL.json', '--numeric-root', BASE + '/flexiact_physical_time_eval_20261017',
            '--metric-root', BASE + '/flexiact_official_metric_20261017', '--pair', 'human/' + source + '/000',
            '--output', REMOTE + '/results/' + source + '.json']
    code = '''import fcntl,hashlib,json,runpy,sys
from pathlib import Path
root=Path(%r)
if hashlib.sha256((root/'FREEZE.json').read_bytes()).hexdigest()!=%r:raise ValueError('Native wrapper freeze identity differs')
f=json.loads((root/'FREEZE.json').read_text())
for n,h in f['files'].items():
 if hashlib.sha256((root/n).read_bytes()).hexdigest()!=h:raise ValueError('Native wrapper freeze differs')
def pending():
 for name in ('timing_signed_source6980766_r53_20261017','timing_flexiact_auto_r50_20261017'):
  for d in (Path(%r)/name/'audit/observations').glob('step*'):
   if (d/'request.json').exists() and (d/'native.json').exists() and not (d/'pose_complete.json').exists() and not (d/'response.json').exists():return True
 return False
if pending():raise SystemExit(75)
lock=Path(%r).open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(75)
if pending():raise SystemExit(75)
sys.argv=%r
runpy.run_path(sys.argv[0],run_name='__main__')
''' % (REMOTE, hashlib.sha256((HERE/'FREEZE.json').read_bytes()).hexdigest(), BASE, BASE + '/timing_architecture_r2_20261016/analysis/pose/consumer.lock', argv)
    command = SSH + ['H3_SERVER_A', shlex.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2',PYTHON,'-c',code])]
    audit = HERE / 'audit'; audit.mkdir(exist_ok=True); stamp = str(time.time_ns())
    (audit / (stamp + '.command.json')).write_text(json.dumps({'command': command},indent=2)+'\n')
    result = subprocess.run(command,capture_output=True,text=True,timeout=180)
    (audit / (stamp + '.log')).write_text(result.stdout+'\nSTDERR\n'+result.stderr)
    if result.returncode == 75:
        print('BUSY_SERVER_OR_ONLINE');return
    if result.returncode:
        print(result.stdout,result.stderr);raise SystemExit(result.returncode)
    dest = HERE / 'results';dest.mkdir(exist_ok=True)
    subprocess.run(['rsync','-a','-e',shlex.join(SSH),'H3_SERVER_A:'+REMOTE+'/results/'+source+'.json',str(dest)+'/'],check=True,timeout=40)
    print(result.stdout)


if __name__ == '__main__':
    main()
