import hashlib,json,os,signal,subprocess,threading,time
from pathlib import Path

def require(ok,message):
 if not ok:raise ValueError(message)

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def read_json(path):
 return json.loads(Path(path).read_text(),parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON '+s)))

def write_new(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 data=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 return sha(path)

def identity(pid):
 p=Path('/proc')/str(pid)
 try:
  stat=(p/'stat').read_text(); tail=stat[stat.rindex(')')+2:].split()
  if tail[0]=='Z':return None
  return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':int(tail[19]),'cmdline_sha256':hashlib.sha256((p/'cmdline').read_bytes()).hexdigest()}
 except (FileNotFoundError,ProcessLookupError):return None

def alive(entry):return entry is not None and identity(entry['pid'])==entry

def terminate_owned(process,entry,grace=8):
 if process.poll() is not None:return
 if alive(entry):
  require(entry['uid']==os.getuid() and os.getpgid(entry['pid'])==entry['pid'],'not an owned isolated process group')
  os.killpg(entry['pid'],signal.SIGTERM)
 try:process.wait(timeout=grace)
 except subprocess.TimeoutExpired:
  if alive(entry):os.killpg(entry['pid'],signal.SIGKILL)
  process.wait(timeout=10)

def install_lifetime_guard(parent):
 """No fork/preexec in CUDA parent. Each fresh exec watches its exact parent."""
 require(parent['uid']==os.getuid() and alive(parent),'parent identity is not live')
 own=os.getpid();require(os.getpgid(own)==own,'child must own its isolated process group')
 def abort(signum,frame):raise SystemExit(128+signum)
 signal.signal(signal.SIGTERM,abort);signal.signal(signal.SIGINT,abort)
 def watch():
  while alive(parent):time.sleep(.25)
  # Our process group contains only descendants created by this fresh exec.
  os.killpg(own,signal.SIGTERM)
  time.sleep(8)
  os.killpg(own,signal.SIGKILL)
 threading.Thread(target=watch,name='exact-parent-lifetime',daemon=True).start()

def run_child(command,env,directory,label,timeout,parent):
 directory=Path(directory);log=directory/(label+'.log');start=time.monotonic();proc=None;entry=None
 try:
  require(alive(parent),'parent exited before child launch')
  with log.open('xb') as handle:
   proc=subprocess.Popen(command,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
   deadline=time.monotonic()+3
   while entry is None and proc.poll() is None and time.monotonic()<deadline:
    entry=identity(proc.pid)
   require(entry is not None and entry['uid']==os.getuid(),'unable to bind own child')
   write_new(directory/(label+'.process.json'),dict(entry,command=command,parent=parent,timeout_seconds=timeout))
   while proc.poll() is None:
    require(alive(parent),'parent exited during child execution')
    if time.monotonic()-start>timeout:raise TimeoutError(label+' timeout')
    time.sleep(.2)
   if proc.returncode:raise RuntimeError(label+' exit '+str(proc.returncode)+'; see '+str(log))
 finally:
  if proc is not None:
   terminate_owned(proc,entry)
   write_new(directory/(label+'.exit.json'),{'pid':proc.pid,'returncode':proc.returncode,'identity_absent':not alive(entry),'wall_seconds':time.monotonic()-start})
 return {'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode}
