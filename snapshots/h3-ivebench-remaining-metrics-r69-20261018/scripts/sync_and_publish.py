"""Passive CPU intake and local presentation. No GPU invocation or service control."""
import argparse
import json
import subprocess
import sys
import time
from common import *

HOST='H3_SERVER_B'
REMOTE='/data3/researcher/h3_runs/ivebench_remaining_metrics_r69_20261018'
PYTHON='/data3/researcher/ComfyUI/.venv/bin/python'
DEPS='/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/runtime_deps'

def once():
    command=f'cd {REMOTE} && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH={DEPS} {PYTHON} scripts/consume_cpu.py'
    result=subprocess.run(['ssh','-o','ConnectTimeout=10',HOST,command],capture_output=True,text=True,timeout=1200)
    if result.returncode==75:return {'busy':True}
    if result.returncode!=0:raise RuntimeError(result.stderr[-5000:])
    for folder in ('incoming','prepared','results'):
        subprocess.run(['rsync','-a','--exclude','*.pt','--exclude','*.npz',HOST+':'+REMOTE+'/'+folder+'/',str(ROOT/folder)+'/'],check=True,timeout=600)
    subprocess.run(['scp','-q',HOST+':'+REMOTE+'/audit/PROGRESS.json',str(ROOT/'audit/PROGRESS.json')],check=True,timeout=30)
    for source in PAIRS:
        if (ROOT/'prepared'/source/'READY.json').exists() and not (ROOT/'showcase'/source/'PRESENTATION.json').exists():
            subprocess.run([sys.executable,str(ROOT/'scripts/render_pair.py'),'--source',source],check=True,timeout=600)
    subprocess.run([sys.executable,str(ROOT/'scripts/make_showcase.py'),'--output',str(ROOT/'showcase/index_singlefile.html')],check=True,timeout=60,capture_output=True)
    return read(ROOT/'audit/PROGRESS.json')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch-hours',type=float,default=0);a=p.parse_args()
    require(0<=a.watch_hours<=12,'bounded watch up to12hours')
    deadline=time.monotonic()+a.watch_hours*3600
    while True:
        result=once()
        print(json.dumps({'unix':time.time(),'all_four_prepared':result.get('all_four_prepared'),'all_four_scored':result.get('all_four_scored'),'busy':result.get('busy',False)}),flush=True)
        if result.get('all_four_scored') or time.monotonic()>=deadline:break
        time.sleep(30)
