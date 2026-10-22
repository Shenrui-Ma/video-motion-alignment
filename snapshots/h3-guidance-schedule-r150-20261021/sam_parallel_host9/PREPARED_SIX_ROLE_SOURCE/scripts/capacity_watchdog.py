import argparse,time
import service,capacity_trial
from r132_contract import read,require
p=argparse.ArgumentParser();p.add_argument('--owner',required=True);a=p.parse_args()
row=read(a.owner);owner=capacity_trial.bind_service(service.RUN)
monitor=read(service.RUN/'processes/capacity_monitor.json')
require(row==read(service.RUN/'processes/service.json'),'owner changed')
try:
 while service.current_identity(row['pid'])==row['identity']:
  if service.current_identity(monitor['pid'])!=monitor['identity']:
   capacity_trial.signal_exact(owner);break
  time.sleep(.25)
except BaseException:
 capacity_trial.signal_exact(owner);raise
