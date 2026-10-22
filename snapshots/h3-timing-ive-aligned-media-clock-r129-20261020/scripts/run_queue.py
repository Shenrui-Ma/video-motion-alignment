"""One persistent Comfy service per source lane; bounded hold, exact cleanup."""
import json,os,subprocess,sys,time
import service,job,preflight
from r129_contract import registry,read,sha

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
    from r129_contract import require,RUN_ID
    wait_controller_registration(expected_pid,expected_start_ticks)
    preflight.check(service.RUN)
    owner=read(service.RUN/'processes/service.json');service.assert_owned(owner)
    require(owner['pid']==expected_pid and str(owner['identity']['start_ticks'])==str(expected_start_ticks),'stale controller')
    limits=read(service.RUN/'configs/scientific_contract.json')['continuous']
    try:
        service.residency_snapshot('before_'+RUN_ID)
        job.submit(RUN_ID,expected_owner=owner);started=time.monotonic()
        while True:
            service.assert_owned(owner)
            try: result=job.status(RUN_ID)
            except job.StatusUnavailable as error: result={'status':'observation_unknown','error':repr(error)}
            status=result.get('status','running');status=status.get('status_str') if isinstance(status,dict) else status
            record_resources(RUN_ID);state(status=status,current=RUN_ID,completed=[])
            if status=='success':break
            if status in ('error','submission_uncertain'):raise RuntimeError('aligned job failed: '+status)
            if time.monotonic()-started>limits['job_timeout_seconds']:raise TimeoutError('single job timeout')
            time.sleep(20)
        service.residency_snapshot('after_'+RUN_ID)
        state(status='verifying_aligned',current=None,completed=[RUN_ID])
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=service.RUNTIME['dependencies'],OMP_NUM_THREADS='1')
        with (service.RUN/'logs/aligned_verify.log').open('xb') as log:
            subprocess.run([service.RUNTIME['python'],'analysis/postrun/verify_aligned.py'],cwd=service.RUN,env=env,stdout=log,stderr=log,check=True,timeout=600)
        state(status='all_sources_finished',current=None,completed=[RUN_ID])
    except BaseException as error:
        state(status='failed',current=RUN_ID,error=repr(error));raise
    finally:
        primary=sys.exc_info()[1]
        try:service.stop(expected_record=owner)
        except BaseException as cleanup:
            service.write_json(service.RUN/'logs/controller_cleanup_error.json',{'primary':repr(primary),'cleanup':repr(cleanup),'service_pid':owner['pid']})
            if primary is None:raise

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start-ticks',required=True);a=p.parse_args();run(a.expected_pid,a.expected_start_ticks)
