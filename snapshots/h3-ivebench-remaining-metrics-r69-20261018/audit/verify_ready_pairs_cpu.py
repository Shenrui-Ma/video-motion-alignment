"""Administrative CPU watcher for completed producer pairs; no model inference."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
os.environ['CUDA_VISIBLE_DEVICES']=''
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import PAIRS, cpu_lock, read, verify_runtime
from consume_cpu import replace_json

def readiness(producer, source):
    gate=producer/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
    if gate.exists():
        value=read(gate)
        if value.get('passed') is not True:raise ValueError('Existing actual gate failed: '+source)
        return 'PASSED'
    for method in ('native','forced'):
        run='r69_'+source+'_seed2026101701_'+method
        hist=producer/'logs'/(run+'_history.json')
        job=producer/'logs'/(run+'_job.json')
        if not hist.exists() or not job.exists():return 'PENDING'
        try:h,j=read(hist),read(job)
        except json.JSONDecodeError:return 'PENDING_WRITING'
        if j.get('status') in ('error','failed'):return 'PRODUCER_FAILED'
        if h.get('status',{}).get('status_str')=='error':return 'PRODUCER_FAILED'
        if h.get('status',{}).get('completed') is not True or h.get('status',{}).get('status_str')!='success' or j.get('status')!='success':return 'PENDING'
    return 'READY'

def once():
    producer=Path(read(ROOT/'configs/paths.json')['producer_remote41'])
    rows=[]
    for source in PAIRS:
        status=readiness(producer,source)
        if status=='READY':
            try:
                with cpu_lock():
                    verify_runtime()
                    # Check again after obtaining the global CPU lock.
                    if readiness(producer,source)=='READY':
                        log=ROOT/'audit'/('VERIFY_'+source+'.log')
                        start=time.monotonic()
                        with log.open('a') as output:
                            result=subprocess.run([sys.executable,str(producer/'analysis/postrun/verify_pair.py'),'--source',source],env=os.environ.copy(),stdout=output,stderr=subprocess.STDOUT,timeout=1800)
                        if result.returncode:raise RuntimeError('Producer CPU verification failed: '+source+'; log='+str(log)+'; returncode='+str(result.returncode))
                        status=readiness(producer,source)
                        if status!='PASSED':raise RuntimeError('Verifier returned without passed gate: '+source)
                        print(json.dumps({'source':source,'gate':'PASSED','wall_seconds':time.monotonic()-start}),flush=True)
                    else:status=readiness(producer,source)
            except BlockingIOError:status='CPU_BUSY'
        rows.append({'source':source,'status':status})
    result={'unix':time.time(),'rows':rows,'all_passed':all(x['status']=='PASSED' for x in rows),'gpu_started':False}
    replace_json(ROOT/'audit/VERIFY_WATCH_PROGRESS.json',result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--watch-hours',type=float,default=0);args=p.parse_args()
    if not 0<=args.watch_hours<=12:raise ValueError('watch bound is0..12hours')
    with (ROOT/'audit/verification_watcher.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        replace_json(ROOT/'audit/VERIFY_WATCH_PROCESS.json',{'pid':os.getpid(),'proc_stat':Path('/proc/self/stat').read_text() if Path('/proc/self/stat').exists() else None,'argv':sys.argv,'started_unix':time.time(),'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES']})
        deadline=time.monotonic()+3600*args.watch_hours
        while True:
            result=once()
            if result['all_passed'] or time.monotonic()>=deadline:break
            time.sleep(30)
if __name__=='__main__':
    try:main()
    except BaseException as error:
        replace_json(ROOT/'audit/VERIFY_WATCH_FAILURE.json',{'unix':time.time(),'type':type(error).__name__,'error':str(error)})
        raise
