"""Mac-only read/collect/render watcher. Root alone verifies and runs GPU work."""
import argparse,fcntl,time,traceback
from common import *
from collect_pair import status,collect
from render_pair import render,choose_font
from make_showcase import build

def run(output,ffmpeg,ffprobe,max_hours,interval):
 validate_static();require((ROOT/'audit/EXECUTION_BINDING.json').exists(),'bind real root STARTED before watcher')
 admin=ROOT/'audit/watcher';admin.mkdir(exist_ok=True)
 with (admin/'watcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);save(admin/f'STARTED_{time.time_ns()}.json',{'pid':os.getpid(),'binding':bound(ROOT/'audit/EXECUTION_BINDING.json'),'scope':'read-only producer; local CPU media; no verifier/tracker/GPU','max_hours':max_hours})
  deadline=time.monotonic()+max_hours*3600
  while time.monotonic()<deadline:
   for pair in PAIRS:
    if (ROOT/'showcase'/pair/'PRESENTATION.json').exists():continue
    try:
     if not (ROOT/'incoming'/pair/'COLLECTION.json').exists():
      s=status(pair);save(admin/f'{pair}_STATUS.json',{k:v for k,v in s.items() if k not in ('gate','binding')},replace=True)
      if s['status']!='PASSED_GATE':continue
      collect(pair)
     result=render(pair,ffmpeg,ffprobe,choose_font());save(admin/f'{pair}_MEDIA_READY.json',result,replace=True);print(json.dumps({'event':'MEDIA_READY','pair':pair,'presentation':result}),flush=True);print(json.dumps(build(output)),flush=True)
    except (OSError,TimeoutError) as e:
     save(admin/f'TRANSIENT_{time.time_ns()}.json',{'pair':pair,'error':repr(e)});continue
    except Exception as e:
     # Validation mismatches are preserved and surfaced instead of consumed.
     save(admin/f'FAILURE_{time.time_ns()}.json',{'pair':pair,'error':repr(e),'traceback':traceback.format_exc()});raise
   if all((ROOT/'showcase'/p/'PRESENTATION.json').exists() for p in PAIRS):save(admin/'COMPLETE.json',{'passed':True,'all_three':True,'GPU_started':False});return
   time.sleep(interval)
  save(admin/f'WAIT_EXPIRED_{time.time_ns()}.json',{'all_three':False,'GPU_started':False,'max_hours':max_hours})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--max-hours',type=float,default=18);p.add_argument('--interval',type=float,default=60);a=p.parse_args();require(0<a.max_hours<=24 and a.interval>=30,'bounded polling parameters required');run(a.output,a.ffmpeg,a.ffprobe,a.max_hours,a.interval)
