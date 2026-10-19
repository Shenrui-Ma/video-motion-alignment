import fcntl,json,subprocess,shlex,sys
from pathlib import Path
P=Path(__file__).resolve().parent
R='/data5/researcher/h3_runs/timing_fresh_source_r24_20261016/analysis/native_sparse_step_observer'
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
state=json.loads((P.parent/'postrun/STATE.json').read_text())
if state['phase'].startswith('consuming '):raise RuntimeError('Full/run consumer priority; wait')
subprocess.run(['ssh','-o','BatchMode=yes','H3_SERVER_A','mkdir -p '+R],check=True)
files=['evaluate.py','PROTOCOL.json','FREEZE.json','observer_frozen.py','observer_protocol.json','wrapper_from_first005.diff']
subprocess.run(['rsync','-a',*[str(P/x) for x in files],'H3_SERVER_A:'+R+'/'],check=True)
cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','/home/researcher/miniconda3/envs/comfyui/bin/python',R+'/evaluate.py'])
p=subprocess.run(['ssh','-o','BatchMode=yes','H3_SERVER_A',cmd],capture_output=True,text=True)
(P/'attempt1.log').write_text(p.stdout+'\nSTDERR\n'+p.stderr)
print(p.stdout,flush=True)
if p.returncode:print(p.stderr,flush=True);sys.exit(p.returncode)
subprocess.run(['rsync','-a','H3_SERVER_A:'+R+'/RESULTS.json',str(P)+'/'],check=True)
