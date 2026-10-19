"""Source-only CPU DWPose and frozen-feature visibility inventory."""
import argparse,fcntl,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
ROOT=Path(__file__).resolve().parent

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def intervals(mask,frames):
 out=[];start=None
 for i,v in enumerate(mask):
  if v and start is None:start=int(frames[i])
  if start is not None and (not v or i==len(mask)-1):
   end=int(frames[i] if v else frames[i-1]);out.append([start,end]);start=None
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--sha',required=True);a=p.parse_args()
 if a.name not in ('fresh_a','fresh_b'):raise ValueError('name')
 lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 started=time.time();protocol=json.loads((ROOT/'PROTOCOL.json').read_text());video=ROOT/'inputs'/(a.name+'.mp4');out=ROOT/a.name;out.mkdir(exist_ok=True)
 if (out/'RESULTS.json').exists():raise ValueError('do not overwrite result')
 if sha(video)!=a.sha:raise ValueError('input SHA')
 for fn,key in [('pose_probe.py','pose_probe_sha256'),('timing_metrics.py','timing_metrics_sha256')]:
  if sha(OLD/'scripts'/fn)!=protocol[key]:raise ValueError('frozen code hash')
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(out),'--threads','4']
 for frame in protocol['overlay_frames']:cmd+=['--overlay-frame',str(frame)]
 log=out/'extract.log'
 if log.exists():
  i=1
  while (out/('extract_previous'+str(i)+'.log')).exists():i+=1
  log.rename(out/('extract_previous'+str(i)+'.log'))
 with log.open('w') as f:subprocess.run(cmd,check=True,env=env,stdout=f,stderr=subprocess.STDOUT)
 pose=out/(a.name+'.pose.json');raw=json.loads(pose.read_text())
 if raw['video']['sha256']!=a.sha or raw['video']['fps']!=24 or (raw['video']['width'],raw['video']['height'])!=(1312,736) or [x['frame'] for x in raw['frames']]!=list(range(141)):raise ValueError('actual video geometry/frame mismatch')
 prior=json.loads((OLD/'analysis/pose/old_sam/07_real_ary_v.pose.json').read_text())['provenance']
 for k in ('detector_sha256','pose_sha256','detector_code_sha256','pose_code_sha256'):
  if raw['provenance'][k]!=prior[k]:raise ValueError('frozen model/code mismatch '+k)
 if raw['provenance']['script_sha256']!=protocol['pose_probe_sha256']:raise ValueError('current frozen script provenance')
 if raw['provenance']['device']!='cpu' or raw['provenance']['providers']!=['CPUExecutionProvider']:raise ValueError('CPU enforcement')
 spec=importlib.util.spec_from_file_location('frozen_metrics',OLD/'scripts/timing_metrics.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 import numpy as np
 result={'source_only':True,'no_generation_accessed':True,'video':raw['video'],'pose_sha256':sha(pose),'protocol_sha256':sha(ROOT/'PROTOCOL.json'),'script_sha256':sha(Path(__file__)),'provenance':raw['provenance'],'statistics':raw['statistics'],'thresholds':{}}
 for th in (.3,.5):
  try:z=m.load_pose(pose,th)
  except ValueError as e:result['thresholds'][str(th)]={'status':'UNKNOWN','reason':str(e)};continue
  v=np.isfinite(z['xy']).all(axis=-1)&(z['conf']>=th);anchors=z['anchor_valid'];frames=z['frames']
  features={};allwin=[]
  for fn in ('arm_direction','left_arm_direction','right_arm_direction','wrist_relative'):
   ok=np.isfinite(z[fn]).all(axis=-1);fully=ok.all(axis=1);both=fully&anchors
   features[fn]={'feature_slot_coverage':float(ok.mean()),'fully_observable_frame_coverage':float(fully.mean()),'fully_observable_intervals':intervals(fully,frames),'with_anchor_frame_coverage':float(both.mean()),'with_anchor_intervals':intervals(both,frames),'per_frame_valid_slots':ok.sum(axis=1).tolist(),'slots_per_frame':int(ok.shape[1])}
  for s in range(126):
   row={'window_inclusive':[s,s+15],'anchor_coverage':float(anchors[s:s+16].mean()),'features':{}}
   for fn in features:
    ok=np.isfinite(z[fn][s:s+16]).all(axis=-1);cov=float(ok.mean());n=int(ok.any(axis=1).sum());row['features'][fn]={'coverage':cov,'valid_frames':n,'source_support_pass':bool(cov>=.8 and n>=8)}
   row['all_four_support_pass']=all(x['source_support_pass'] for x in row['features'].values());allwin.append(row)
  result['thresholds'][str(th)]={'status':'computed','anchors':{'coverage':float(anchors.mean()),'count':int(anchors.sum()),'joint_coverages':{str(j):float(v[:,j].mean()) for j in (5,6,11,12)},'intervals':intervals(anchors,frames)},'median_torso_scale_pixels':float(z['scale']),'features':features,'all16frame_windows':allwin,'crossings':{'left':m.crossings(z,0,0,140),'right':m.crossings(z,1,0,140)},'out_of_frame_joint_fraction':float(((z['xy'][...,0]<0)|(z['xy'][...,0]>=1312)|(z['xy'][...,1]<0)|(z['xy'][...,1]>=736)).mean())}
 result['elapsed_seconds']=time.time()-started;save(out/'RESULTS.json',result)
 print(json.dumps({'output':str(out/'RESULTS.json'),'seconds':result['elapsed_seconds'],'anchor_coverage':{k:v.get('anchors',{}).get('coverage') for k,v in result['thresholds'].items()}}))
if __name__=='__main__':main()
