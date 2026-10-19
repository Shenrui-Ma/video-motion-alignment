"""Administrative environment wrapper; original sealed consumer is imported unchanged."""
import importlib.util,sys,subprocess,shlex,os,time,json,hashlib
from pathlib import Path
ROOT=Path('/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017')
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'analysis/postrun'))
import one_phase,consume
TEMP='/data5/researcher/h3_runs/timing_flexiact_native_r49_20261017/temp'
def remote(args):
 cmd=consume.SSH+[consume.HOST,shlex.join(['env','TMPDIR='+TEMP,'TMP='+TEMP,'TEMP='+TEMP,'CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',consume.PYTHON,consume.REMOTE+'/remote_consume.py',*args])]
 audit={'unix':time.time(),'args':args,'command':cmd,'command_sha256':hashlib.sha256(json.dumps(cmd).encode()).hexdigest(),'consumer_sha256':hashlib.sha256((ROOT/'analysis/postrun/consume.py').read_bytes()).hexdigest(),'one_phase_sha256':hashlib.sha256((ROOT/'analysis/postrun/one_phase.py').read_bytes()).hexdigest(),'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'environment_only':True}
 (HERE/'audit').mkdir(exist_ok=True);(HERE/'audit'/str(time.time_ns())).with_suffix('.json').write_text(json.dumps(audit,indent=2)+'\n')
 return subprocess.run(cmd,capture_output=True,text=True,timeout=900)
if __name__=='__main__':
 subprocess.run(consume.SSH+[consume.HOST,'mkdir -p '+shlex.quote(TEMP)],check=True,timeout=30)
 consume.remote=remote
 try:one_phase.main()
 except Exception as exc:
  import traceback
  one_phase.save(one_phase.HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'entry':'root_approved_temp_environment_wrapper','error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
