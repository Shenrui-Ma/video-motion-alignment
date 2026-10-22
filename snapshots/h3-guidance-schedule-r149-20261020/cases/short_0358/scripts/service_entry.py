"""No torch import before exact-PID root go. runpy preserves the OS PID and cmdline."""
import hashlib,json,os,runpy,sys,time
from pathlib import Path
import process_identity

def identity(pid=None):
 return process_identity.hashed_record(process_identity.snapshot(os.getpid() if pid is None else pid))

def require_parent(parent,lookup=identity):
 if parent is None:raise ValueError('exact supervisor binding required')
 try:actual=lookup(parent['pid'])
 except (FileNotFoundError,ProcessLookupError):actual=None
 if actual!=parent['identity'] or actual is None or actual['uid']!=os.getuid():raise RuntimeError('pre-CUDA supervisor generation disappeared')

def wait_gate(directory,target,identity_fn=identity,timeout=600,*,parent=None,parent_lookup=identity):
 require_parent(parent,parent_lookup)
 d=Path(directory);target=Path(target);ready=d/'cuda_gate_ready.json';go=d/'cuda_gate_go.json'
 if ready.exists() or go.exists():raise FileExistsError('gate files already exist; explicit generation recovery required')
 own_identity=identity_fn()
 if own_identity is None:raise RuntimeError('own pre-CUDA identity incomplete')
 rec={'schema':'r49-before-CUDA-root-gate-v1','pid':os.getpid(),'identity':own_identity,'target':str(target),'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'argv':sys.argv[:],'unix':time.time(),'supervisor':parent}
 temporary=d/('cuda_gate_ready.'+str(os.getpid())+'.tmp')
 with temporary.open('x') as f:json.dump(rec,f,indent=2)
 try:os.link(temporary,ready)  # exclusive, complete JSON becomes visible atomically
 finally:temporary.unlink()
 start=time.monotonic()
 while not go.exists():
  require_parent(parent,parent_lookup)
  if time.monotonic()-start>timeout:raise TimeoutError('root exact peer registration not supplied')
  time.sleep(.05)
 require_parent(parent,parent_lookup)
 if json.loads(go.read_text())!=rec or identity_fn()!=rec['identity'] or hashlib.sha256(target.read_bytes()).hexdigest()!=rec['target_sha256']:raise ValueError('root go identity/target differs')
 return rec

def main():
 root=Path(__file__).resolve().parents[1];target=Path(sys.argv[1])
 if target!=root/'scripts/compatibility_bootstrap.py':raise ValueError('unexpected service bootstrap')
 parent=json.loads(os.environ['H3_SERVICE_SUPERVISOR_JSON'])
 wait_gate(root/'processes',target,parent=parent)
 # This changes Python argv only; /proc/<pid>/cmdline remains the admitted command.
 sys.argv=sys.argv[1:];runpy.run_path(str(target),run_name='__main__')
if __name__=='__main__':main()
