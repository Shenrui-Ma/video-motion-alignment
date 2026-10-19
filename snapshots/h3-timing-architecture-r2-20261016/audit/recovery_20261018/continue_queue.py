"""Resume only never-submitted jobs after checking the complete saved prefix."""
import argparse,importlib,json,os,sys,time
from pathlib import Path
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--pid',type=int,required=True);p.add_argument('--start-ticks',required=True);a=p.parse_args();root=a.root
 sys.path.insert(0,str(root/'scripts'));import service,job,preflight,run_queue
 run_queue.wait_controller_registration(a.pid,a.start_ticks);preflight.check(root,live=True)
 owner=read(root/'processes/service.json');assert owner['pid']==a.pid and owner['identity']['start_ticks']==a.start_ticks;service.assert_owned(owner)
 contract=read(root/'configs/scientific_contract.json');policy=contract['continuous'];plan=read(root/'configs/queue.json');order=plan['jobs'];completed=[]
 for name in order:
  f=root/'logs'/f'{name}_job.json'
  if not f.exists():break
  j=read(f);h=read(root/'logs'/f'{name}_history.json');assert j['status']=='success' and h['status']['completed'] is True and h['status']['status_str']=='success'
  completed.append(name)
 assert all(not(root/'logs'/f'{name}_job.json').exists() for name in order[len(completed):])
 assert len(completed)>0,'use original controller for first launch'
 evidence={'completed_prefix':completed.copy(),'remaining':order[len(completed):],'service':owner,'unix':time.time()};service.write_json(root/'audit'/f'RESUME_PREFIX_{a.pid}.json',evidence)
 deadline=time.monotonic()+policy['max_service_seconds']
 try:
  for name in order[len(completed):]:
   assert read(root/'configs/queue.json')==plan
   from execution_gate import admitted_job
   assert admitted_job(name,root)
   assert not(root/'logs'/f'{name}_job.json').exists()
   service.assert_owned(owner);job.submit(name,expected_owner=owner);started=time.monotonic()
   while True:
    status=job.status(name).get('status') or 'running';status=status['status_str'] if isinstance(status,dict) else status
    run_queue.record_resources(name);run_queue.state(status=status,current=name,completed=completed)
    if status=='success':
     history=read(root/'logs'/f'{name}_history.json');assert history['status']['completed'] is True;completed.append(name);break
    if status in ('error','unknown_missing','submission_uncertain'):raise RuntimeError((name,status))
    assert time.monotonic()<deadline and time.monotonic()-started<policy['job_timeout_seconds'];time.sleep(20)
  run_queue.state(status='final_close',current=None,completed=completed,resumed=True)
 except BaseException as e:
  run_queue.state(status='failed',current=name,completed=completed,error=repr(e),resumed=True);raise
 finally:service.stop(expected_record=owner)
if __name__=='__main__':main()
