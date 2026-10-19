"""Administrative caller for the frozen source publisher with both CPU locks."""
import fcntl,json,shlex,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=json.loads((HERE/'PROTOCOL.json').read_text())
lock=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print(json.dumps({'status':'mac_CPU_busy','phase_started':False}));raise SystemExit(0)
cmd=['env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=2','MKL_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',p['consumer']['python'],p['root_remote']+'/analysis/postrun/source_scores.py']
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',p['consumer']['host'],shlex.join(cmd)],capture_output=True,text=True,timeout=150)
(HERE/'audit'/('source_phase_'+str(time.time_ns())+'.log')).write_text(r.stdout+'\nSTDERR\n'+r.stderr)
print(r.stdout);print(r.stderr);r.check_returncode()
