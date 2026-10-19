from pathlib import Path
import fcntl,json,subprocess,hashlib,time,os
r=Path('/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/anime_domain_extension')
priority=Path('/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017/audit/observations')
def pending():
 return any((p/'request.json').exists() and (p/'native.json').exists() and not (p/'pose_complete.json').exists() and not (p/'response.json').exists() for p in priority.glob('step*'))
assert hashlib.sha256((r/'source_anime50_video.mp4').read_bytes()).hexdigest()=='e32f88d291d9a87b2741a2d2369227ca0411b8b817f8dfaab63de8a8a173ea38'
if pending():print('ONLINE_BUSY');raise SystemExit(0)
lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
with lock.open('a') as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('REMOTE_BUSY');raise SystemExit(0)
 if pending():print('ONLINE_BUSY');raise SystemExit(0)
 cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',str(r/'pose_probe.py'),'--video',str(r/'source_anime50_video.mp4'),'--output-dir',str(r/'pose'),'--threads','4']
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
 start=time.time();p=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=300)
 (r/'POSE_EXECUTION.json').write_text(json.dumps({'argv':cmd,'returncode':p.returncode,'elapsed':time.time()-start,'stdout':p.stdout,'stderr':p.stderr,'GPU':False,'source_only':True},indent=2))
 print(p.stdout[-1500:]);print(p.stderr[-1000:]);print('exit',p.returncode)
 raise SystemExit(p.returncode)
