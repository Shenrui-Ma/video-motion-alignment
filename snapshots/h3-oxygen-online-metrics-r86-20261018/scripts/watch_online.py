"""Unique Mac CPU reader; starts only after binding real root STARTED."""
import argparse,fcntl,time,traceback
from common import *
from collect_online import status,collect
from render_online import render
from media_utils import choose_font
from make_showcase import build
def run(output,ffmpeg,ffprobe,max_hours,interval):
 validate_static();require((ROOT/'audit/EXECUTION_BINDING.json').exists(),'actual STARTED binding required');admin=ROOT/'audit/watcher';admin.mkdir(exist_ok=True)
 with (admin/'watcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);save(admin/f'STARTED_{time.time_ns()}.json',{'pid':os.getpid(),'binding':bound(ROOT/'audit/EXECUTION_BINDING.json'),'scope':'CPU media only; no verifier/observer/GPU','max_hours':max_hours})
  deadline=time.monotonic()+max_hours*3600
  while time.monotonic()<deadline:
   try:
    if not (ROOT/'incoming/COLLECTION.json').exists():
     s=status();save(admin/'STATUS.json',{k:v for k,v in s.items() if k not in ('gate','binding')},replace=True)
     if s['status']=='FAILED_ATTEMPT':return
     if s['status']!='PASSED_GATE':time.sleep(interval);continue
     collect()
    if not (ROOT/'showcase/PRESENTATION.json').exists():render(ffmpeg,ffprobe,choose_font())
    result=build(output);save(admin/'COMPLETE.json',{'passed':True,'presentation':result,'quality':'UNREVIEWED','GPU_started':False});print(json.dumps(result),flush=True);return
   except (OSError,TimeoutError) as e:save(admin/f'TRANSIENT_{time.time_ns()}.json',{'error':repr(e)})
   except Exception as e:
    save(admin/f'FAILURE_{time.time_ns()}.json',{'error':repr(e),'traceback':traceback.format_exc()});raise
   time.sleep(interval)
  save(admin/'WAIT_EXPIRED.json',{'max_hours':max_hours,'GPU_started':False})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--max-hours',type=float,default=12);p.add_argument('--interval',type=float,default=60);a=p.parse_args();require(0<a.max_hours<=24 and a.interval>=30,'bounded waiting required');run(a.output,a.ffmpeg,a.ffprobe,a.max_hours,a.interval)
