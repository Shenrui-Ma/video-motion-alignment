"""Full107 final-video CPU poses; original extractor and all detections retained."""
import os,json,hashlib,fcntl,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parent;C=R.parents[1];P=json.loads((R/'PROTOCOL.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
for rel,h in P['bindings'].items():assert sha(R/rel)==h,rel
for path,h in P['pose_external'].items():assert sha(path)==h,path
for x in P['media'].values():assert sha(C/x['file'])==x['sha256']
(R/'temp').mkdir(exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',TMPDIR=str(R/'temp'))
with open(P['cpu_lock'],'a') as lock:
 deadline=time.monotonic()+600
 while True:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:
   if time.monotonic()>deadline:raise TimeoutError('shared CPU lock busy')
   time.sleep(10)
 provenance=None
 for arm,x in P['media'].items():
  out=R/'poses'/arm;assert not out.exists(),'preserve prior pose attempt';out.mkdir(parents=True)
  video=C/x['file'];cmd=[sys.executable,str(R/'vendor/pose_probe.py'),'--video',str(video),'--output-dir',str(out),'--aux-root',P['aux_root'],'--threads','4','--stride','1']
  start=time.monotonic()
  with (out/'pose.log').open('x') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=420)
  assert result.returncode==0,'pose failed: '+str(out)
  path=out/(video.stem+'.pose.json');raw=json.loads(path.read_text())
  assert raw['video']['sha256']==x['sha256']
  assert [raw['video'][k] for k in ['width','height','container_frame_count','fps']]==P['full_geometry']
  assert len(raw['frames'])==107 and all(a['frame']==i and abs(a['time_s']-i/24)<1e-6 for i,a in enumerate(raw['frames']))
  assert raw['provenance']['device']=='cpu' and raw['provenance']['providers']==['CPUExecutionProvider']
  if provenance is None:provenance=raw['provenance']
  else:assert raw['provenance']==provenance,'pose runtime mismatch'
  record={'arm':arm,'passed':True,'file':str(path.relative_to(R)),'sha256':sha(path),'video_sha256':x['sha256'],'protocol_sha256':sha(R/'PROTOCOL.json'),'wall_seconds':time.monotonic()-start,'GPU_calls':0}
  save(out/'COMPLETE.json',record);print(json.dumps(record),flush=True)
