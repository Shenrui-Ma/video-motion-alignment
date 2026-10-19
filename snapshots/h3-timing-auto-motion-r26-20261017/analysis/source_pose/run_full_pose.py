import argparse,fcntl,json,subprocess,shlex,hashlib,time
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[1];REMOTE='/data5/researcher/h3_runs/timing_auto_motion_r26_20261017/analysis/source_pose';HOST='H3_SERVER_A';PY='/home/researcher/miniconda3/envs/comfyui/bin/python'
a=argparse.ArgumentParser();a.add_argument('source_id',choices=['40372','51317','51304']);args=a.parse_args();cid=args.source_id
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
subprocess.run(['ssh',HOST,'mkdir -p '+REMOTE+'/inputs'],check=True)
subprocess.run(['rsync','-a',str(P/'remote_pose.py'),str(R/'configs/source_selection_inputs.json'),HOST+':'+REMOTE+'/'],check=True)
subprocess.run(['rsync','-a',str(R/'assets/prepared'/f'{cid}_full24.mp4'),HOST+':'+REMOTE+'/inputs/'],check=True)
cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4',PY,REMOTE+'/remote_pose.py',cid]);started=time.time();r=subprocess.run(['ssh','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3',HOST,cmd],capture_output=True,text=True)
i=1
while (P/f'{cid}_attempt{i}.log').exists():i+=1
(P/f'{cid}_attempt{i}.log').write_text(r.stdout+'\nSTDERR\n'+r.stderr)
print(json.dumps({'source':cid,'code':r.returncode,'seconds':time.time()-started,'stdout':r.stdout,'stderr':r.stderr[-1500:]}),flush=True)
if r.returncode:raise SystemExit(r.returncode)
local=P/'full_pose'/cid;local.mkdir(parents=True,exist_ok=True);subprocess.run(['rsync','-a',HOST+':'+REMOTE+'/full_pose/'+cid+'/',str(local)+'/'],check=True)
d=json.loads((local/'COMPLETE.json').read_text());p=local/f'{cid}_full24.pose.json'
if hashlib.sha256(p.read_bytes()).hexdigest()!=d['pose_sha256']:raise ValueError('download pose hash')
