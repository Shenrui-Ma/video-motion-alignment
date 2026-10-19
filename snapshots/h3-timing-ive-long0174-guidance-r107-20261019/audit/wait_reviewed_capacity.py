"""Bounded CPU wait for root-approved admission, then the existing exact-owner launcher."""
import fcntl
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import cgroup_memory as cg
import process_identity


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);args=parser.parse_args()
    attempt=args.attempt
    assert attempt.replace('_','').isalnum()
    assert str(ROOT)=='/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019'
    assert os.getuid()==1004
    with (ROOT/'audit/CAPACITY_WAIT.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt={'pid':os.getpid(),'identity':process_identity.hashed_record(process_identity.snapshot(os.getpid())),'start_unix':time.time(),'deadline_seconds':3600}
        (ROOT/'audit'/('CAPACITY_WAIT_OWNER_'+attempt+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        deadline=time.monotonic()+3600
        while time.monotonic()<deadline:
            assert not (ROOT/'processes/service.json').exists()
            assert not (ROOT/'audit'/attempt).exists()
            snap=cg.snapshot();policy=json.loads((ROOT/'configs/cgroup_policy.json').read_text())
            try:
                capacity=cg.admit(snap,policy)
            except RuntimeError as error:
                capacity={'admitted':False,'error':str(error),'snapshot':snap}
            with (ROOT/'audit/CAPACITY_WAIT_SAMPLES.jsonl').open('a') as out:
                out.write(json.dumps(capacity)+'\n')
            stable_margin=capacity['admitted'] and all(
                room-capacity['working_set_admission']['policy']['minimum_'+kind+'_headroom_bytes']>=128*1024**2
                for row in capacity['working_set_admission']['bounded_ancestors']
                for kind,room in row['headroom_bytes'].items())
            if stable_margin:
                command=['python3','-u',str(ROOT/'audit/root_run_control.py'),'--execute','--attempt',attempt,'--parent-tasks-reviewed']
                with (ROOT/'audit'/('ROOT_LAUNCH_'+attempt+'.log')).open('ab',buffering=0) as log:
                    child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                time.sleep(.1)
                launched={'created_unix':time.time(),'pid':child.pid,'identity':process_identity.hashed_record(process_identity.snapshot(child.pid)),'command':command,'attempt':attempt,'capacity_before_launch':capacity}
                (ROOT/'audit'/('ROOT_LAUNCH_'+attempt+'.json')).write_text(json.dumps(launched,indent=2)+'\n')
                print(json.dumps({'launched':True,'pid':child.pid,'attempt':attempt}),flush=True)
                return
            print(json.dumps({'waiting':True,'unix':time.time(),'reason':capacity.get('error','admitted; waiting128MiB transient margin')}),flush=True)
            time.sleep(60)
        (ROOT/'audit/CAPACITY_WAIT_EXPIRED.json').write_text(json.dumps({'unix':time.time(),'GPU_started':False})+'\n')


if __name__=='__main__':main()
