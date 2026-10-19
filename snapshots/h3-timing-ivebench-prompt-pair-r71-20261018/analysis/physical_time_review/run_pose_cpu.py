"""Administrative CPU-only extraction using byte-frozen R55 DWPose."""
import argparse,fcntl,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.environ['CUDA_VISIBLE_DEVICES']=''
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(ok,msg):
 if not ok:raise ValueError(msg)
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def verify():
 p=read(ROOT/'PROTOCOL.json')
 for b in p['bindings']:check(sha(ROOT/b['relative'])==b['sha256'],'frozen source changed')
 for rel,h in p['aux_files'].items():check(sha(Path(p['aux_root'])/rel)==h,'model/code changed')
 gate=ROOT/'inputs/PAIR_RUNTIME_GATE.json';check(sha(gate)==p['pair_gate']['sha256'],'gate changed')
 g=read(gate);check(g['passed'] and len(g['checks'])==22 and all(v is True for v in g['checks'].values()),'R71 actual gate failed')
 return p
def run(arm):
 p=verify();source=Path(p['source_pose']['file']);check(sha(source)==p['source_pose']['sha256'],'source pose changed');raw=read(source);check(raw['provenance']==p['expected_pose_provenance'],'source CPU provenance differs')
 src=ROOT/'poses/source.pose.json';src.parent.mkdir(parents=True,exist_ok=True)
 if not src.exists():shutil.copy2(source,src)
 check(sha(src)==p['source_pose']['sha256'],'cached source differs')
 video=ROOT/'inputs'/(arm+'.mp4');check(sha(video)==p['media'][arm]['sha256'],'target video changed')
 dest=ROOT/'poses'/arm;check(not dest.exists(),'preserve prior extraction');dest.mkdir()
 command=[sys.executable,str(ROOT/'vendor/pose_probe.py'),'--video',str(video),'--output-dir',str(dest),'--aux-root',p['aux_root'],'--threads','4','--stride','1']
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1')
 start=time.monotonic()
 with (dest/'pose.log').open('x') as log:result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=300)
 check(result.returncode==0,'CPU pose failed; preserve log')
 path=dest/(arm+'.pose.json');pose=read(path)
 check(pose['provenance']==raw['provenance'],'target/source CPU environment differs')
 check(pose['video']['sha256']==p['media'][arm]['sha256'],'pose binds wrong video')
 check([pose['video'][k] for k in ['width','height','container_frame_count','fps']]==p['full_geometry'],'target pose geometry differs')
 check(len(pose['frames'])==90 and all(r['frame']==i and abs(r['time_s']-i/24)<1e-8 for i,r in enumerate(pose['frames'])),'pose timeline differs')
 verify()
 record={'status':'complete','arm':arm,'pose':str(path),'pose_sha256':sha(path),'video_sha256':sha(video),'source_pose_sha256':sha(src),'protocol_sha256':sha(ROOT/'PROTOCOL.json'),'command':command,'cpu_seconds':time.monotonic()-start,'provenance':pose['provenance'],'gpu_started':False}
 write(dest/'COMPLETE.json',record);print(json.dumps({'arm':arm,'status':'complete','seconds':record['cpu_seconds']}),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--arm',choices=['p0','p1'],required=True);args=a.parse_args();p=read(ROOT/'PROTOCOL.json')
 try:
  with open(p['cpu_lock'],'a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);run(args.arm)
 except BlockingIOError:print('SHARED_CPU_BUSY',flush=True);raise SystemExit(75)
