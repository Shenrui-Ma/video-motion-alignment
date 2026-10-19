"""One persistent Comfy service per source lane; bounded hold, exact cleanup."""
import json,os,subprocess,sys,time
import service,job,preflight
from r116_contract import registry,read,sha

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


def expired_review_owner(owner,phase):
    if phase not in ('awaiting_native_review','awaiting_first_guided_review'):return False
    file=service.RUN/'audit/watchdog_runtime_v2/STOP_REASON.json'
    if not file.exists():return False
    record=read(file)
    return (record.get('reason')=='bounded_idle_review_expired' and
            record.get('owner',{}).get('pid')==owner['pid'] and
            record['owner'].get('identity')==owner['identity'] and
            service.current_identity(owner['pid']) is None)

def run(expected_pid=None,expected_start_ticks=None):
    from r116_contract import SOURCES,require
    from execution_gate import admitted_job,decision,finish_source,first_guided_reviewed,ledger
    wait_controller_registration(expected_pid,expected_start_ticks)
    preflight.check(service.RUN)
    owner=read(service.RUN/'processes/service.json');service.assert_owned(owner)
    require(owner['pid']==expected_pid and str(owner['identity']['start_ticks'])==str(expected_start_ticks),'stale controller generation')
    require(not (service.RUN/'audit/SCREEN_LEDGER.json').exists(),'existing ledger requires explicit recovery, never automatic resume')
    policy=read(service.RUN/'configs/scientific_contract.json')['continuous']
    deadline=time.monotonic()+policy['max_service_seconds'];completed=[];current=None;review_phase=None;review_source=None;registered,order=registry(service.RUN)
    def owner_and_registry():
        actual=read(service.RUN/'processes/service.json');require(actual['pid']==owner['pid'] and actual['identity']==owner['identity'],'service generation changed');service.assert_owned(owner)
        require(registry(service.RUN)==(registered,order),'registered scientific bindings changed')
        if time.monotonic()>=deadline:raise TimeoutError('Service maximum lifetime reached')
    def execute(name):
        nonlocal current
        owner_and_registry();require(admitted_job(name,service.RUN),'root decision or previous case review pending');current=name
        require(not(service.RUN/'logs'/f'{name}_job.json').exists(),'Existing job record requires recovery; never auto-resubmit')
        service.residency_snapshot('before_'+name);job.submit(name,expected_owner=owner);started=time.monotonic()
        while True:
            owner_and_registry()
            try:result=job.status(name)
            except job.StatusUnavailable as error:result={'status':'observation_unknown','observation_error':repr(error)}
            status=result.get('status') or 'running';status=status['status_str'] if isinstance(status,dict) else status
            record_resources(name);state(status=status,current=name,completed=completed,observation_error=result.get('observation_error'))
            if status=='success':
                require(read(service.RUN/'logs'/f'{name}_history.json')['status']['completed'] is True,'success history incomplete')
                completed.append(name);current=None;service.residency_snapshot('after_'+name);return
            if status in ('error','submission_uncertain'):raise RuntimeError(name+': '+status)
            if time.monotonic()-started>policy['job_timeout_seconds']:raise TimeoutError('One job exceeded frozen safety timeout')
            time.sleep(20)
    def verify(source,native_only):
        owner_and_registry();state(status='verifying_native' if native_only else 'verifying_pair',source_id=source,completed=completed,current=None)
        cmd=[service.RUNTIME['python'],'analysis/postrun/verify_pair.py','--source',source]+(['--native-only'] if native_only else [])
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=service.RUNTIME['dependencies'],OMP_NUM_THREADS='1')
        with (service.RUN/'logs'/(source+('_native_verify.log' if native_only else '_pair_verify.log'))).open('xb') as log:
            subprocess.run(cmd,cwd=service.RUN,env=env,stdout=log,stderr=log,check=True,timeout=600)
    def hold(source,phase,readiness):
        nonlocal review_phase,review_source
        review_phase=phase;review_source=source
        since=time.monotonic()
        while True:
            owner_and_registry();value=readiness()
            if value:review_phase=None;review_source=None;return value
            elapsed=time.monotonic()-since
            state(status=phase,source_id=source,completed=completed,current=None,idle_seconds=elapsed,decision_deadline_seconds=policy['idle_hold_seconds'],terminal_sources=ledger(service.RUN)['rows'])
            if elapsed>=policy['idle_hold_seconds']:
                state(status='review_timeout',phase=phase,source_id=source,completed=completed,current=None,pending=True,terminal_sources=ledger(service.RUN)['rows']);return None
            time.sleep(20)
    try:
        for source in SOURCES:
            native='r116_'+source+'_seed2026101701_native';forced='r116_'+source+'_seed2026101701_forced'
            execute(native);verify(source,True)
            selected=hold(source,'awaiting_native_review',lambda:decision(service.RUN,source))
            if selected is None:return
            if selected['choice']=='guide':execute(forced);verify(source,False)
            row=finish_source(service.RUN,source)
            state(status='source_terminal',source_id=source,completed=completed,current=None,result=row,terminal_sources=ledger(service.RUN)['rows'])
            if row['status']=='paired' and not first_guided_reviewed(service.RUN):
                if hold(source,'awaiting_first_guided_review',lambda:first_guided_reviewed(service.RUN)) is None:return
        state(status='all_sources_finished',completed=completed,current=None,terminal_sources=ledger(service.RUN)['rows'])
    except BaseException as error:
        if expired_review_owner(owner,review_phase):
            state(status='review_timeout',phase=review_phase,source_id=review_source,completed=completed,current=None,pending=True,reason='exact watchdog bounded idle expiry');return
        state(status='failed',current=current,completed=completed,error=repr(error));raise
    finally:
        primary=sys.exc_info()[1]
        try:service.stop(expected_record=owner)
        except BaseException as cleanup:
            try:service.write_json(service.RUN/'logs/controller_cleanup_error.json',{'primary':repr(primary),'cleanup':repr(cleanup),'service_pid':owner['pid']})
            except BaseException:pass
            if primary is None:raise

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start-ticks',required=True);a=p.parse_args();run(a.expected_pid,a.expected_start_ticks)
