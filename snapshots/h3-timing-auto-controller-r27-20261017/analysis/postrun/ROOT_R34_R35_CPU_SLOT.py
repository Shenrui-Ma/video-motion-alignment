import fcntl,json,os,signal,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parent
PID=80029
LOCK=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def identity():
 return subprocess.check_output(['/bin/ps','-p',str(PID),'-o','uid=,lstart=,command='],text=True).strip()
def save(d):
 p=R/'ROOT_R34_R35_CPU_SLOT.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');q.replace(p)
original=identity()
assert str(R/'consume.py')+' --start' in original
assert int(original.split()[0])==os.getuid()
assert json.loads((R/'CONSUMER_IDENTITY.json').read_text())['pid']==PID
record={'guard_pid':os.getpid(),'consumer_pid':PID,'identity':original,'started':time.time(),'reason':'brief CPU postrun scheduling slot for R34 and R35 actual CPU preflight; GPU jobs continue; sealed files untouched','max_pause_seconds':180}
save(record);paused=False
try:
 with LOCK.open('a') as lock:
  deadline=time.monotonic()+180
  while True:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
   except BlockingIOError:
    if time.monotonic()>deadline:raise TimeoutError('no CPU phase boundary within180seconds')
    time.sleep(.1)
  assert identity()==original
  os.kill(PID,signal.SIGSTOP);paused=True;record.update(status='paused_at_free_CPU_boundary',paused_unix=time.time());save(record)
  fcntl.flock(lock,fcntl.LOCK_UN)
 time.sleep(180)
finally:
 if paused:
  assert identity()==original
  os.kill(PID,signal.SIGCONT);record.update(status='resumed',resumed_unix=time.time());save(record)
