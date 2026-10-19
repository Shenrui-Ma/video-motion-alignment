"""Extend the existing static seal after actual guided CPU release; no GPU."""
import time,shutil
from common import *
def main():
 verify_runtime();validate_cache();ready=read(ROOT/'prepared/guided/READY.json');require(ready['passed'] is True,'actual guided release pending')
 for k in ['metric_inputs','tracker_manifest']:require(sha(ready[k]['file'])==ready[k]['sha256'],'actual release receipt changed')
 mf=read(ROOT/'incoming/R101_MF_INPUTS.json');validate_gate(read(ROOT/'incoming/PAIR_RUNTIME_GATE.json'),mf['media'])
 item=read(ROOT/'prepared/guided/TRACK_INPUTS.json')['inputs'][0];tracker=load('frozen_actual_binding',METRIC/'run_tracks.py');tracker.validate_generated_binding(item,Path(item['file']))
 require(sha(ROOT/'incoming/forced.mp4')==mf['media']['forced']['sha256'],'guided media changed')
 before=read(ROOT/'CONSUMER_FREEZE.json');j=read(ROOT/'CONSUMER_FREEZE.json')
 for folder in ['incoming','prepared']:
  for p in (ROOT/folder).rglob('*'):
   if p.is_file():j['files'][str(p.relative_to(ROOT))]=sha(p)
 j['files']=dict(sorted(j['files'].items()));j['status']='ACTUAL_GUIDED_INPUT_READY_TRACKING_PENDING';j['no_GPU_started']=True
 backup=ROOT/'audit'/('pre_actual_freeze_'+str(time.time_ns())+'.json');save(backup,before);save(ROOT/'CONSUMER_FREEZE.json',j)
 print(__import__('json').dumps({'actual_freeze':bound(ROOT/'CONSUMER_FREEZE.json'),'previous_freeze':bound(backup),'files':len(j['files']),'GPU_started':False}))
if __name__=='__main__':main()
