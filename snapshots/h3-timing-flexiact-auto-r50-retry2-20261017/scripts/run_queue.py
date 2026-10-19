"""Five predeclared FlexiAct jobs, bounded resident hold, generation-bound cleanup."""
import json,subprocess,time,sys
import job,service
from r50_contract import validate_job

def state(**v):service.write_json(service.RUN/'logs/controller_state.json',dict(unix=time.time(),**v))
def run(expected_pid=None,expected_start_ticks=None):
    owner=json.loads((service.RUN/'processes/service.json').read_text());service.assert_owned(owner)
    if expected_pid is not None:
        from start_controller import admit
        admit(expected_pid,expected_start_ticks,owner)
    deadline=time.monotonic()+43200;completed=[];current=None;idle=None
    from recovery_contract import plan as recovery_plan
    recovery=recovery_plan(service.RUN);expected=recovery['new_runs']
    try:
        while time.monotonic()<deadline:
            job.require_generation(job.active_service(),owner)
            plan=json.loads((service.RUN/'configs/queue.json').read_text())
            if set(plan)!={'jobs','finalize'} or plan['jobs']!=expected or type(plan['finalize']) is not bool:raise ValueError('queue scientific job set changed')
            if not all(n in completed for n in expected):
                current=next(n for n in expected if n not in completed);validate_job(current)
                if not (service.RUN/'logs'/f'{current}_job.json').exists():job.submit(current,expected_owner=owner)
                started=time.monotonic()
                while time.monotonic()<deadline:
                    service.assert_owned(owner);result=job.status(current);status=result['status']
                    if isinstance(status,dict):status=status['status_str']
                    state(status=status,current=current,completed=completed,service_pid=owner['pid'])
                    if status=='success':completed.append(current);current=None;break
                    if status in ('error','unknown_missing','submission_uncertain'):raise RuntimeError(str(result))
                    if time.monotonic()-started>14400:raise TimeoutError('job4hour limit')
                    time.sleep(20)
                else:raise TimeoutError('service12hour limit')
            else:
                idle=idle or time.monotonic()
                if plan['finalize'] or time.monotonic()-idle>=1800:
                    state(status='all_queued_jobs_complete',completed=completed,external_completed=[recovery['external_chest']['run_id']],planned_denominator=5);return
                state(status='resident_hold',completed=completed,idle_elapsed=time.monotonic()-idle,service_pid=owner['pid']);time.sleep(15)
        raise TimeoutError('service12hour limit')
    except BaseException as error:
        state(status='failed',current=current,completed=completed,error=repr(error));raise
    finally:
        primary=sys.exc_info()[1]
        try:service.stop(expected_record=owner)
        except Exception as error:
            service.write_json(service.RUN/'logs/controller_cleanup_error.json',{'primary_error':repr(primary),'cleanup_error':repr(error)})
            if primary is None:raise
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int);p.add_argument('--expected-start-ticks');a=p.parse_args()
    run(a.expected_pid,a.expected_start_ticks)
