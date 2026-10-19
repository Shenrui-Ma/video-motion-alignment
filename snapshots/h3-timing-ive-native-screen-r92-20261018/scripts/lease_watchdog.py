"""Root-started administrative replacement watchdog; original producer is unchanged."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import service
from r92_contract import read,registry
HERE=ROOT/'audit/watchdog_runtime_v2'


def owner_matches(a,b):return a['pid']==b['pid'] and a['identity']==b['identity']


def initialize(owner,now_wall,now_mono):
    started=float(owner['started_unix'])
    if not math.isfinite(started) or started>now_wall+5:raise ValueError('service original start time invalid')
    return dict(started=now_mono-max(0.,now_wall-started),active_since=None,active_run=None,idle_since=None)


def update_reason(state,now,queue,limits,known_job=None):
    # Never reset these clocks when HTTP is unavailable.
    if now-state['started']>=limits['max_service_seconds']:return 'bounded_service_lifetime_expired'
    if known_job is not None:
        if known_job.get('failed'):return 'actual_registered_job_failure'
        if known_job.get('active_run'):
            since=known_job['active_since']
            if state['active_run']==known_job['active_run'] and state['active_since'] is not None:
                since=min(since,state['active_since'])
            state['active_run']=known_job['active_run'];state['active_since']=since
        elif known_job.get('all_known_terminal') and not (queue is not None and
                (queue['queue_running'] or queue['queue_pending'])):
            state['active_run']=None;state['active_since']=None
    if state['active_since'] is not None and now-state['active_since']>=limits['job_timeout_seconds']:
        return 'bounded_job_timeout'
    if queue is None:
        # UNKNOWN cannot accumulate idle time. A new observed empty queue restarts this hold.
        state['idle_since']=None
        return None
    active=bool(queue['queue_running'] or queue['queue_pending'])
    if active:
        state['idle_since']=None
        if state['active_since'] is None:state['active_since']=now
        return None
    # A queue/history race is UNKNOWN while a known accepted job lacks a terminal history.
    if state['active_run'] is not None:
        state['idle_since']=None
        return None
    state['active_since']=None
    if state['idle_since'] is None:state['idle_since']=now
    if now-state['idle_since']>=limits['idle_hold_seconds']:return 'bounded_idle_review_expired'
    return None


def known_job_state(owner,now_wall,now_mono):
    jobs,_=registry(ROOT);active=[];seen=False
    for run in jobs:
        p=ROOT/'logs'/(run+'_job.json')
        if not p.exists():continue
        j=read(p)
        if j.get('service_pid')!=owner['pid'] or j.get('service_identity')!=owner['identity']:continue
        seen=True;h=ROOT/'logs'/(run+'_history.json')
        if h.exists():
            history=read(h)
            if history['prompt'][1]!=j.get('prompt_id'):raise ValueError('history belongs to a different prompt')
            status=history['status']
            if status.get('status_str')=='error':return {'failed':True,'run_id':run}
            if status.get('completed') is True and status.get('status_str')=='success':continue
        submitted=float(j['submitted_unix'])
        if not math.isfinite(submitted) or submitted<owner['started_unix']-5 or submitted>now_wall+5:
            raise ValueError('registered job start time invalid')
        active.append((submitted,run))
    if len(active)>1:raise ValueError('more than one registered nonterminal job')
    if active:
        submitted,run=active[0]
        return dict(active_run=run,active_since=now_mono-max(0.,now_wall-submitted))
    return dict(all_known_terminal=seen)


def save_best_effort(name,value):
    try:
        HERE.mkdir(parents=True,exist_ok=True)
        service.write_json(HERE/name,value)
    except Exception as error:print('watchdog receipt unavailable: '+repr(error),file=sys.stderr,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start-ticks',required=True);a=p.parse_args()
    if ROOT!=Path(service.RUNTIME['remote_root']):raise RuntimeError('actual remote root required')
    owner=read(ROOT/'processes/service.json')
    if owner['pid']!=a.expected_pid or str(owner['identity']['start_ticks'])!=a.expected_start_ticks:raise RuntimeError('root supplied owner identity differs')
    service.assert_owned(owner)
    limits=read(ROOT/'configs/scientific_contract.json')['continuous'];now_wall=time.time();now=time.monotonic()
    state=initialize(owner,now_wall,now)
    save_best_effort('STARTED.json',dict(watchdog_pid=os.getpid(),watchdog_identity=service.identity(os.getpid()),owner=owner,state=state,started_unix=now_wall,limits=limits))
    while True:
        current=read(ROOT/'processes/service.json');actual=service.current_identity(owner['pid'])
        if not owner_matches(current,owner) or actual!=owner['identity']:
            save_best_effort('EXIT_OWNER_CHANGED.json',dict(owner=owner,current=current,actual=actual,unix=time.time()));return
        now_wall=time.time();now=time.monotonic();errors={}
        try:known=known_job_state(owner,now_wall,now)
        except Exception as error:known=None;errors['job_observation']=repr(error)
        try:
            queue=service.queue_at(service.PORT)
            if not isinstance(queue,dict) or any(not isinstance(queue.get(k),list) for k in ('queue_running','queue_pending')):raise ValueError('queue response shape differs')
        except Exception as error:queue=None;errors['HTTP_observation']=repr(error)
        reason=update_reason(state,time.monotonic(),queue,limits,known)
        save_best_effort('STATE.json',dict(owner=owner,state=state,reason=reason,errors=errors,HTTP_known=queue is not None,observed_unix=time.time()))
        if reason:
            current=read(ROOT/'processes/service.json')
            if owner_matches(current,owner) and service.current_identity(owner['pid'])==owner['identity']:
                save_best_effort('STOP_REASON.json',dict(owner=owner,state=state,reason=reason,observed_unix=time.time()))
                service.assert_owned(owner);service.stop(expected_record=owner)
            return
        time.sleep(20)

if __name__=='__main__':main()
