import argparse,fcntl,hashlib,json,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--sha',required=True);a=p.parse_args()
r=Path(__file__).resolve().parent;project=r.parents[1];v=project/'assets/prepared'/(a.name+'.mp4');remote='/data5/researcher/h3_runs/timing_fresh_source_r24_20261016/analysis/source_pose'
if a.name not in ('fresh_a','fresh_b'):raise ValueError('name')
if hashlib.sha256(v.read_bytes()).hexdigest()!=a.sha:raise ValueError('source SHA')
probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,duration,nb_frames,time_base:frame=best_effort_timestamp_time','-of','json',str(v)]))
st=probe['streams'][0]
if not(st['width']==1312 and st['height']==736 and st['r_frame_rate']=='24/1' and len(probe['frames'])==141 and abs(float(st['duration'])-5.875)<1e-6):raise ValueError('geometry')
if any(abs(float(f['best_effort_timestamp_time'])-i/24)>1e-6 for i,f in enumerate(probe['frames'])):raise ValueError('PTS')
(r/(a.name+'_input_binding.json')).write_text(json.dumps({'file':str(v),'sha256':a.sha,'probe':probe,'recorded_unix':time.time()},indent=2)+'\n')
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
subprocess.run(['ssh','H3_SERVER_A','mkdir -p '+remote+'/inputs'],check=True)
subprocess.run(['rsync','-a',str(r/'PROTOCOL.json'),str(r/'evaluate_source.py'),'H3_SERVER_A:'+remote+'/'],check=True)
subprocess.run(['rsync','-a',str(v),'H3_SERVER_A:'+remote+'/inputs/'],check=True)
cmd="CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 /home/researcher/miniconda3/envs/comfyui/bin/python "+remote+'/evaluate_source.py --name '+a.name+' --sha '+a.sha
started=time.time();x=subprocess.run(['ssh','H3_SERVER_A',cmd],capture_output=True,text=True)
attempt=1
while (r/(a.name+'_attempt'+str(attempt)+'.log')).exists():attempt+=1
(r/(a.name+'_attempt'+str(attempt)+'.log')).write_text(x.stdout+'\nSTDERR\n'+x.stderr)
print(json.dumps({'exit':x.returncode,'wall':time.time()-started,'stdout':x.stdout,'stderr':x.stderr[-2000:]}))
if x.returncode==0:subprocess.run(['rsync','-a','H3_SERVER_A:'+remote+'/'+a.name+'/',str(r/a.name)+'/'],check=True)
raise SystemExit(x.returncode)
