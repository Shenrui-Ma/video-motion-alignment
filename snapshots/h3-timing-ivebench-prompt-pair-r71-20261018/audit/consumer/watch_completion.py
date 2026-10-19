"""Passive CPU watcher; records final job completion and stops at the requested arm."""
import argparse,hashlib,json,os,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUNS={arm:f'r71_short_0210_seed2026101701_{arm}' for arm in ('p0','p1')}
def read(p):return json.loads(p.read_text())
def inspect():
 result={}
 for arm,run in RUNS.items():
  p=ROOT/'logs'/(run+'_job.json');h=ROOT/'logs'/(run+'_history.json')
  job=read(p) if p.exists() else {};status=job.get('status','pending');complete=False
  if status=='success':
   if not h.exists():raise ValueError('success without actual history')
   history=read(h);complete=history['status']['completed'] is True and history['status']['status_str']=='success'
   if not complete:raise ValueError('job/history mismatch')
  result[arm]={'run_id':run,'status':status,'actual_history_complete':complete,'history':str(h) if h.exists() else None}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--until',choices=RUNS,required=True);p.add_argument('--timeout',type=float,default=28800);a=p.parse_args();deadline=time.monotonic()+a.timeout;previous=None
 while time.monotonic()<deadline:
  state=inspect();encoded=json.dumps(state,sort_keys=True)
  if encoded!=previous:
   record={'unix':time.time(),'watcher_pid':os.getpid(),'jobs':state,'CUDA_started':False};tmp=HERE/('STATUS.'+str(os.getpid())+'.tmp');tmp.write_text(json.dumps(record,indent=2)+'\n');os.replace(tmp,HERE/'STATUS.json');print(json.dumps(record),flush=True);previous=encoded
  if any(row['status'] in ('error','submission_uncertain','unknown_missing') for row in state.values()):raise RuntimeError('actual producer failure; preserve evidence')
  if state[a.until]['actual_history_complete']:break
  time.sleep(20)
 else:raise TimeoutError('passive completion wait expired')
