"""Real Linux exec/process-session tests; no torch/model/GPU imports."""
import fcntl,json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from observer_import import t

def wait_file(path,timeout=10):
 start=time.monotonic()
 while not path.exists():
  if time.monotonic()-start>timeout:raise TimeoutError(str(path))
  time.sleep(.05)
 return t.read_json(path)
def main():
 results=[]
 with tempfile.TemporaryDirectory(prefix='r27-lifetime-') as temporary:
  for kind in ('timeout','controller_SIGTERM','controller_SIGKILL','CPU_lock_wait_parent_death'):
   r=Path(temporary)/kind;r.mkdir();lock=None;process=None;stage=None;own=None;started=time.monotonic()
   try:
    command=[sys.executable,str(Path(__file__).with_name('lifetime_fixture.py')),'controller','--parent',json.dumps(t.identity(os.getpid())),'--root',str(r),'--timeout','.6' if kind=='timeout' else '60']
    if kind=='CPU_lock_wait_parent_death':
     lock=(r/'pose.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX);command+=['--lock',str(r/'pose.lock')]
    with (r/'controller.log').open('wb') as f:process=subprocess.Popen(command,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
    own=wait_file(r/'controller_ready.json');stage=wait_file(r/'stage_ready.json')
    if kind!='timeout':os.kill(process.pid,signal.SIGTERM if kind=='controller_SIGTERM' else signal.SIGKILL)
    process.wait(timeout=15)
    deadline=time.monotonic()+15
    while t.alive(stage) and time.monotonic()<deadline:time.sleep(.1)
    assert not t.alive(stage),(kind,stage)
    results.append({'case':kind,'controller_exit':process.returncode,'stage_identity_absent':True,'seconds':time.monotonic()-started})
   finally:
    if lock:fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
    if process:t.terminate_owned(process,own)
 print('R19_LIFETIME_CPU_SMOKE='+json.dumps({'success':True,'cases':results,'torch_imported':'torch' in sys.modules}))
if __name__=='__main__':main()
