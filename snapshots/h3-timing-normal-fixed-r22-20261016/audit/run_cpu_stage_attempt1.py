import fcntl,subprocess,time,json,hashlib
from pathlib import Path
r=Path('/Users/researcher/DevProjects/h3-timing-normal-fixed-r22-20261016')
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
remote="""python - <<'REMOTE'
import fcntl,os,subprocess,tarfile,time,json
from pathlib import Path
stage=Path('/data5/researcher/h3_runs/timing_normal_fixed_r22_cpu_stage_attempt1')
stage.mkdir(exist_ok=False)
with tarfile.open('/tmp/r22_cpu_stage_attempt1.tar.gz') as t:t.extractall(stage)
(stage/'audit').mkdir(exist_ok=True)
lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
with lock.open('a') as l:
 fcntl.flock(l,fcntl.LOCK_EX)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
 cmd=['/home/researcher/miniconda3/envs/comfyui/bin/python',str(stage/'tests/real_comfy_cpu_smoke.py'),'--core','/data5/researcher/h3_runs/short_event_pilot_20261013/ComfyUI','--parent-audit','/data5/researcher/h3_runs/timing_native_screen_r14_host9_20261016/audit']
 start=time.time();p=subprocess.run(cmd,env=env,cwd=stage,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (stage/'audit/actual_cpu.log').write_text(p.stdout);print(p.stdout);print(json.dumps({'returncode':p.returncode,'elapsed':time.time()-start,'stage':str(stage),'CUDA_VISIBLE_DEVICES':''}))
 raise SystemExit(p.returncode)
REMOTE"""
start=time.time()
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_A',remote],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (r/'audit/actual_cpu_attempt1.log').write_text(p.stdout)
 (r/'audit/actual_cpu_attempt1_status.json').write_text(json.dumps({'returncode':p.returncode,'wall_seconds_including_lock':time.time()-start,'remote_stage':'/data5/researcher/h3_runs/timing_normal_fixed_r22_cpu_stage_attempt1'}))
 print('R22_CPU_RETURN',p.returncode)
 raise SystemExit(p.returncode)
