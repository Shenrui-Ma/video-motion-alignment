"""One persistent Comfy service per source lane; bounded hold, exact cleanup."""
import json,os,subprocess,sys,time
import service,job,preflight
from r118_contract import registry,read,sha

def state(**value):service.write_json(service.RUN/'logs/controller_state.json',dict(unix=time.time(),**value))
def remaining(order,completed):
 if order[:len(completed)]!=completed:raise ValueError('Completed job prefix was rewritten or reordered')
 return order[len(completed):]
def idle_action(plan,idle_seconds,hold):
 if plan['finalize']:return 'final_close'
 if idle_seconds>=hold:return 'bounded_idle_expired'
 return 'resident_hold'

def record_resources(current):
    sample={'unix':time.time(),'job':current}
    try:
        stats=subprocess.run(['nvidia-smi','-i',service.GPU,'--query-gpu=uuid,memory.used,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=20,check=True)
    except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
        sample.update(sample=None,sample_available=False,error_type=type(error).__name__,error=str(error))
    else:
        sample.update(sample=stats.stdout.strip() or None,sample_available=bool(stats.stdout.strip()))
    with (service.RUN/'logs/resources.jsonl').open('a') as handle:handle.write(json.dumps(sample)+'\n')


def wait_controller_registration(expected_pid, expected_start_ticks, *, timeout=10,
                                 clock=time.monotonic, sleep=time.sleep):
    """No Comfy submission until the launcher publishes this exact controller."""
    own_pid = os.getpid()
    own_identity = service.identity(own_pid)
    deadline = clock() + timeout
    path = service.RUN / 'processes/controller.json'
    while clock() < deadline:
        if service.current_identity(own_pid) != own_identity:
            raise RuntimeError('controller generation changed before registration')
        if path.exists():
            record = read(path)
            if (record.get('pid') != own_pid or record.get('identity') != own_identity or
                record.get('role') != 'controller' or record.get('service_pid') != expected_pid or
                str(record.get('service_identity', {}).get('start_ticks')) != str(expected_start_ticks)):
                raise RuntimeError('controller registration does not identify this launch')
            owner = read(service.RUN / 'processes/service.json')
            if owner['pid'] != expected_pid or owner['identity'] != record['service_identity']:
                raise RuntimeError('registered controller service generation differs')
            service.assert_owned(owner)
            return record
        sleep(min(.02, max(0, deadline-clock())))
    raise TimeoutError('controller registration missing; no job submitted')


def run(expected_pid=None,expected_start_ticks=None):
    wait_controller_registration(expected_pid, expected_start_ticks)
    preflight.check(service.RUN)
    owner=read(service.RUN/'processes/service.json');service.assert_owned(owner)
    if owner['pid']!=expected_pid or str(owner['identity']['start_ticks'])!=str(expected_start_ticks):raise RuntimeError('stale controller generation')
    policy=read(service.RUN/'configs/scientific_contract.json')['continuous']
    deadline=time.monotonic()+policy['max_service_seconds'];completed=[];current=None;idle=None;row_pins={}
    try:
        while time.monotonic()<deadline:
            current_owner=read(service.RUN/'processes/service.json')
            if current_owner['pid']!=owner['pid'] or current_owner['identity']!=owner['identity']:raise RuntimeError('service generation changed during queue lifetime')
            service.assert_owned(owner)
            jobs,order=registry(service.RUN);plan=read(service.RUN/'configs/queue.json')
            for name,pinned in row_pins.items():
                if jobs.get(name)!=pinned:raise ValueError('Registered pending/completed scientific binding changed')
            for name,row in jobs.items():row_pins.setdefault(name,row)
            pending=remaining(order,completed)
            if not pending:
                idle=idle if idle is not None else time.monotonic()
                action=idle_action(plan,time.monotonic()-idle,policy['idle_hold_seconds'])
                resident=service.residency_snapshot(action)
                state(status=action,completed=completed,current=None,residency=resident,idle_seconds=time.monotonic()-idle)
                if action!='resident_hold':return
                time.sleep(20);continue
            current=pending[0]
            from execution_gate import admitted_job
            if not admitted_job(current,service.RUN):
                idle=idle if idle is not None else time.monotonic()
                state(status='awaiting_first_pair_review',completed=completed,current=None,
                      next_run=current,idle_seconds=time.monotonic()-idle)
                if time.monotonic()-idle>=policy['idle_hold_seconds']:return
                time.sleep(20);continue
            idle=None
            if (service.RUN/'logs'/f'{current}_job.json').exists():raise RuntimeError('Existing job record requires manual recovery, never auto-resubmit')
            service.residency_snapshot('before_'+current);job.submit(current,expected_owner=owner);started=time.monotonic()
            while time.monotonic()<deadline:
                result=job.status(current);status=result.get('status') or 'running'
                status=status['status_str'] if isinstance(status,dict) else status
                record_resources(current)
                state(status=status,current=current,completed=completed)
                if status=='success':
                    history=read(service.RUN/'logs'/f'{current}_history.json')
                    if history['status']['completed'] is not True:raise ValueError('Success history not completed')
                    completed.append(current)
                    service.residency_snapshot('after_'+current)
                    current=None;break
                if status in ('error','unknown_missing','submission_uncertain'):raise RuntimeError(f'{current}: {status}')
                if time.monotonic()-started>policy['job_timeout_seconds']:raise TimeoutError('One job exceeded frozen safety timeout')
                time.sleep(20)
            else:raise TimeoutError('Service maximum lifetime reached')
        raise TimeoutError('Service maximum lifetime reached')
    except BaseException as exc:
        state(status='failed',current=current,completed=completed,error=repr(exc));raise
    finally:
        primary = sys.exc_info()[1]
        try:
            service.stop(expected_record=owner)
        except BaseException as cleanup:
            service.write_json(service.RUN/'logs/controller_cleanup_error.json',
                {'primary':repr(primary),'cleanup':repr(cleanup),'service_pid':owner['pid']})
            if primary is None:raise
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start-ticks',required=True);a=p.parse_args();run(a.expected_pid,a.expected_start_ticks)
