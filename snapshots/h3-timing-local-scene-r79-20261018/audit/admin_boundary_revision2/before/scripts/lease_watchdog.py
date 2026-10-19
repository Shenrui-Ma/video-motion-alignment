"""Bounded service lifetime, single-job runtime and idle review hold; exact owner only."""
import json,time
import service
from r79_contract import read

def reason(state,now,queue,limits):
    if now-state['started']>=limits['max_service_seconds']:return 'bounded_service_lifetime_expired'
    if queue is None:
        return 'HTTP_unavailable_timeout' if now-state['last_http']>=900 else None
    state['last_http']=now
    active=bool(queue['queue_running'] or queue['queue_pending'])
    if active:
        state['idle_since']=None
        if state['active_since'] is None:state['active_since']=now
        if now-state['active_since']>=limits['job_timeout_seconds']:return 'bounded_job_timeout'
    else:
        state['active_since']=None
        if state['idle_since'] is None:state['idle_since']=now
        if now-state['idle_since']>=limits['idle_hold_seconds']:return 'bounded_idle_review_expired'
    return None

def main():
    record=read(service.RUN/'processes/service.json');limits=read(service.RUN/'configs/scientific_contract.json')['continuous'];now=time.monotonic()
    state=dict(started=now,last_http=now,idle_since=None,active_since=None);stop_reason=None
    while True:
        actual=service.current_identity(record['pid'])
        if actual!=record['identity']:return
        try:queue=service.queue_at(service.PORT)
        except Exception:queue=None
        stop_reason=reason(state,time.monotonic(),queue,limits)
        if stop_reason:break
        time.sleep(20)
    current=read(service.RUN/'processes/service.json')
    if current['pid']==record['pid'] and current['identity']==record['identity'] and service.current_identity(record['pid'])==record['identity']:
        service.write_json(service.RUN/'processes/watchdog_reason.json',dict(reason=stop_reason,state=state,observed_unix=time.time(),pid=record['pid']))
        service.assert_owned(record);service.stop(expected_record=record)
if __name__=='__main__':main()
