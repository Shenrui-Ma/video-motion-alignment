"""No torch import before exact-PID root go. runpy preserves the OS PID and cmdline."""
import hashlib,json,os,runpy,sys,time
from pathlib import Path

def identity(pid=None):
 p=Path('/proc')/str(os.getpid() if pid is None else pid)
 return {'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().split(') ',1)[1].split()[19], 'cmdline_sha256':hashlib.sha256(p.joinpath('cmdline').read_bytes()).hexdigest()}

def wait_gate(directory,target,identity_fn=identity,timeout=600):
 d=Path(directory);target=Path(target);ready=d/'cuda_gate_ready.json';go=d/'cuda_gate_go.json'
 if ready.exists() or go.exists():raise FileExistsError('gate files already exist; explicit generation recovery required')
 rec={'schema':'r42-before-CUDA-root-gate-v1','pid':os.getpid(),'identity':identity_fn(),'target':str(target),'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'argv':sys.argv[:],'unix':time.time()}
 temporary=d/('cuda_gate_ready.'+str(os.getpid())+'.tmp')
 with temporary.open('x') as f:json.dump(rec,f,indent=2)
 try:os.link(temporary,ready)  # exclusive, complete JSON becomes visible atomically
 finally:temporary.unlink()
 start=time.monotonic()
 while not go.exists():
  if time.monotonic()-start>timeout:raise TimeoutError('root exact peer registration not supplied')
  time.sleep(.05)
 if json.loads(go.read_text())!=rec or identity_fn()!=rec['identity'] or hashlib.sha256(target.read_bytes()).hexdigest()!=rec['target_sha256']:raise ValueError('root go identity/target differs')
 return rec

def main():
 root=Path(__file__).resolve().parents[1];target=Path(sys.argv[1])
 if target!=root/'scripts/compatibility_bootstrap.py':raise ValueError('unexpected service bootstrap')
 wait_gate(root/'processes',target)
 # This changes Python argv only; /proc/<pid>/cmdline remains the admitted command.
 sys.argv=sys.argv[1:];runpy.run_path(str(target),run_name='__main__')
if __name__=='__main__':main()
