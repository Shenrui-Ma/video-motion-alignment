"""Exact owner/controller lifetime guard; HTTP availability is observational only."""
import argparse,time,threading
import service
from r86_contract import read,require

def main(pid,start,capacity_pid,capacity_start):
 record=read(service.RUN/'processes/service.json')
 require(record['pid']==pid and str(record['identity']['start_ticks'])==str(start),'watchdog launched for wrong generation')
 capacity=read(service.RUN/'processes/capacity_monitor.json')
 require(capacity['pid']==capacity_pid and str(capacity['identity']['start_ticks'])==str(capacity_start),'capacity watchdog generation differs')
 import capacity_trial
 owner=capacity_trial.bind_service(service.RUN)
 from own_nvml import run as sample_nvml
 sampling_stop=threading.Event()
 threading.Thread(target=sample_nvml,args=(service.RUN,owner,sampling_stop),daemon=True,name='own-pid-nvml').start()
 controller=read(service.RUN/'processes/controller.json');deadline=time.monotonic()+18000
 while time.monotonic()<deadline:
  if service.current_identity(pid)!=record['identity']:return
  if service.current_identity(capacity_pid)!=capacity['identity']:
   capacity_trial.signal_exact(owner)
   return
  if service.current_identity(controller['pid'])!=controller['identity']:break
  time.sleep(.25)
 # Controller loss or hard deadline: stop only the pinned original service.
 if service.current_identity(pid)==record['identity']:
  current=read(service.RUN/'processes/service.json')
  if current['pid']==pid and current['identity']==record['identity']:service.stop(expected_record=record)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start',required=True);p.add_argument('--capacity-pid',type=int,required=True);p.add_argument('--capacity-start',required=True);a=p.parse_args();main(a.expected_pid,a.expected_start,a.capacity_pid,a.capacity_start)
