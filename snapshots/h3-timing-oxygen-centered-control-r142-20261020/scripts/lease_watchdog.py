"""Exact owner/controller lifetime guard; HTTP availability is observational only."""
import argparse,time
import service
from r86_contract import read,require

def main(pid,start):
 record=read(service.RUN/'processes/service.json')
 require(record['pid']==pid and str(record['identity']['start_ticks'])==str(start),'watchdog launched for wrong generation')
 controller=read(service.RUN/'processes/controller.json');deadline=time.monotonic()+18000
 while time.monotonic()<deadline:
  if service.current_identity(pid)!=record['identity']:return
  if service.current_identity(controller['pid'])!=controller['identity']:break
  time.sleep(5)
 # Controller loss or hard deadline: stop only the pinned original service.
 if service.current_identity(pid)==record['identity']:
  current=read(service.RUN/'processes/service.json')
  if current['pid']==pid and current['identity']==record['identity']:service.stop(expected_record=record)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--expected-pid',type=int,required=True);p.add_argument('--expected-start',required=True);a=p.parse_args();main(a.expected_pid,a.expected_start)
