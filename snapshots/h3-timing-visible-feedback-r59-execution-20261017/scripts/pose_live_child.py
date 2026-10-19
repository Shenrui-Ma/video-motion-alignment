"""CPU-only frozen DWPose and measurement, after decoder has exited."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
from observer_import import t,ROOT

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--parent-json',required=True);a=p.parse_args()
 t.install_lifetime_guard(json.loads(a.parent_json));r=t.request(a.request);directory=Path(a.request).parent
 t.require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU pose must hide all GPUs')
 b=t.bindings(external=True);protocol=t.read_json(ROOT/'configs/protocol.json');resource=protocol['resources']
 lock=Path(resource['CPU_lock']);lock.parent.mkdir(parents=True,exist_ok=True);start=time.monotonic()
 with lock.open('a') as handle:
  while True:
   try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:
    t.require(t.alive(r['parent']),'main parent gone while waiting CPU lock')
    if time.monotonic()-start>600:raise TimeoutError('CPU lock admission timeout')
    time.sleep(.3)
  wait=time.monotonic()-start;start=time.monotonic()
  try:
   output=directory/'pose';output.mkdir(exist_ok=False)
   command=[sys.executable,str(ROOT/'scripts/pose_probe.py'),'--video',str(directory/'native.mp4'),'--output-dir',str(output),'--aux-root',b['aux_root'],'--threads','4','--stride','1']
   # Children stay in this exact isolated group; lifetime guard kills that group on parent loss.
   subprocess.run(command,check=True,timeout=240)
   pose=output/'native.pose.json';raw=t.read_json(pose)
   t.require(raw['video']['sha256']==t.sha(directory/'native.mp4'),'pose video hash differs')
   from pose_domain import validate_pose
   geometry=t.geometry_for(r['run_id']);validate_pose(pose,geometry)
   case=t.case_for(r['run_id']);source=t.inside(str(t.ROOT/case['source_pose_path']),t.ROOT)
   t.require(t.sha(source)==case['source_pose_sha256'],'wrong source pose for case')
   case_path=directory/'geometry_case.json';t.write_new(case_path,{'geometry':geometry.video_geometry,'valid_frame_count':geometry.valid_frames})
   subprocess.run([sys.executable,str(ROOT/'scripts/scan_current_pose.py'),'--source',str(source),'--pose',str(pose),'--index',str(r['physical_index']),'--output',str(directory/'observer.json'),'--geometry-case',str(case_path)],check=True,timeout=max(1,240-(time.monotonic()-start)))
   t.write_new(directory/'pose_complete.json',{'status':'complete','request_sha256':t.sha(a.request),'lock_wait_seconds':wait,'pose_metric_seconds':time.monotonic()-start,'pose':str(pose),'observer':str(directory/'observer.json')})
  finally:fcntl.flock(handle,fcntl.LOCK_UN)
if __name__=='__main__':main()
