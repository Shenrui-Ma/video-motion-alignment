"""One authorized serial tracker batch; only exact child and peer entry are owned."""
import fcntl,signal,sys
from common import *
def row_for(i):return {'pid':i['pid'],'identity':{k:v for k,v in i.items() if k!='pid'}}
def update_rows(value,ident,adding):
 rows=value['permitted_compute_processes'];new=row_for(ident);matching=[r for r in rows if r['pid']==ident['pid']]
 if adding:
  require(not matching,'PID already registered; cannot overwrite');value['permitted_compute_processes']=rows+[new]
 else:
  require(matching==[new],'exact tracker peer changed before removal');value['permitted_compute_processes']=[r for r in rows if r!=new]
 return value
def peer_change(ident,adding):
 path=PEER/'configs/admission.json'
 with (PEER/'configs/quant_recovery_peer.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);raw=path.read_bytes();value=json.loads(raw)
  require(value['scope']=='own_user_video_jobs' and value['ready_for_launch'] is True,'R96 mutable admission unavailable')
  original=json.loads(raw);value=update_rows(value,ident,adding)
  require(path.read_bytes()==raw,'admission concurrently changed; no overwrite');save(path,value)
  require(read(path)==value,'admission write changed')
  save(ROOT/'controls'/CURRENT_ROLE/('PEER_REGISTERED.json' if adding else 'PEER_REMOVED.json'),{'before':original,'after':value,'exact_tracker':ident,'unix':time.time()})
def absent_cuda(pid):
 output=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=15)
 return str(pid) not in {x.strip() for x in output.splitlines()}
def wait_release(child,ident):
 deadline=time.monotonic()+30;last=None
 while time.monotonic()<deadline:
  last={'process_absent':identity(ident['pid']) is None,'CUDA_absent':absent_cuda(ident['pid'])}
  if all(last.values()):return last
  time.sleep(.5)
 raise RuntimeError('tracker cleanup incomplete: '+str(last))
def main():
 global CURRENT_ROLE
 verify_seal();require(os.getuid()==1004,'actual host UID differs')
 with (ROOT/'audit/batch.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  require(not (ROOT/'audit/STARTED.json').exists(),'batch attempt already exists')
  owner=read(PEER/'processes/service.json');expected=bind_service_owner(owner);require(identity(owner['pid'])==expected,'R96 owner stale')
  save(ROOT/'audit/STARTED.json',{'identity':identity(os.getpid()),'peer_owner':owner,'seal_sha256':sha(ROOT/'SEAL.json'),'unix':time.time()})
  for role in ('source','native','forced'):
   CURRENT_ROLE=role;resource_check(GPU);require(identity(owner['pid'])==expected,'R96 service changed before tracker')
   control=ROOT/'controls'/role;child=None;ident=None;registered=False;primary=None;started=time.monotonic();samples=[]
   command=[PYTHON,'-u',str(ROOT/'scripts/track.py'),'--role',role]
   try:
    with (ROOT/'audit'/f'{role}.log').open('xb',buffering=0) as log:
     child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=dict(os.environ,CUDA_VISIBLE_DEVICES=GPU,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'),start_new_session=True)
    deadline=time.monotonic()+300
    while not (control/'ready.json').exists():
     require(child.poll() is None,'tracker exited before ready');require(time.monotonic()<deadline,'tracker preCUDA deadline');time.sleep(.2)
    ready=read(control/'ready.json');ident=ready['identity'];require(ident['pid']==child.pid and identity(child.pid)==ident and ready['CUDA_started'] is False and ready['gpu_uuid']==GPU and ready['input_manifest_sha256']==sha(ROOT/'INPUTS.json') and ready['seal_sha256']==sha(ROOT/'SEAL.json'),'ready identity/input mismatch')
    admission=resource_check(GPU);known={owner['pid']:expected}
    for row in admission['processes']:
     if row['uid']==os.getuid():require(row['pid'] in known and {k:row[k] for k in ident}==known[row['pid']],'unregistered other own compute')
    peer_change(ident,True);registered=True
    save(control/'LAUNCH.json',{'command':command,'identity':ident,'admission':admission,'unix':time.time()});save(control/'go.json',ready)
    print(json.dumps({'role':role,'pid':child.pid,'identity':ident,'GO':True,'command':command}),flush=True)
    deadline=time.monotonic()+1800
    while child.poll() is None:
     require(time.monotonic()<deadline,'tracker bounded1800s deadline')
     sample=cgroup();status=Path('/proc')/str(child.pid)/'status'
     if status.exists():sample['proc_memory']={x.split(':')[0]:x.split(':',1)[1].strip() for x in status.read_text().splitlines() if x.startswith(('VmRSS:','VmHWM:'))}
     samples.append(sample);time.sleep(.5)
    require(child.returncode==0,'tracker process failed; see role log')
    d=read(ROOT/'tracks'/role/'REPORT.json');require(d.get('passed') is True and d['method']==role and d['effective_frame_count']==105 and d['tracks_sha256']==sha(ROOT/'tracks'/role/'tracks.npz'),'actual tracking report/tensor differs')
   except BaseException as error:
    primary=error
   finally:
    cleanup=[]
    if child is not None:
     if child.poll() is None:
      # Popen ownership is direct; never signal a lookup-only PID or another process.
      child.terminate()
      try:child.wait(timeout=15)
      except subprocess.TimeoutExpired:child.kill();child.wait(timeout=15)
     if ident is None:
      ident=identity(child.pid)
     if ident is not None:
      try:
       release=wait_release(child,ident);save(control/'EXIT.json',{'identity':ident,**release,'returncode':child.returncode,'unix':time.time()})
      except BaseException as e:cleanup.append(repr(e))
    if registered and not cleanup:
     try:peer_change(ident,False)
     except BaseException as e:cleanup.append(repr(e))
    try:save(control/'TELEMETRY.json',{'samples':samples,'sampled_cgroup_peak':max([x['current'] for x in samples],default=None),'wall_seconds':time.monotonic()-started,'primary_error':repr(primary) if primary else None,'cleanup_errors':cleanup})
    except Exception as e:cleanup.append(repr(e))
    if primary is not None:raise primary
    require(not cleanup,'cleanup error: '+str(cleanup))
  subprocess.run([PYTHON,str(ROOT/'scripts/score.py')],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'),check=True)
  save(ROOT/'audit/COMPLETE.json',{'passed':True,'summary':read(ROOT/'results/SUMMARY.json'),'unix':time.time()})
def interrupted(signum,frame):raise RuntimeError('bounded batch signal '+str(signum))
if __name__=='__main__':
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
 try:main()
 except BaseException as error:
  try:save(ROOT/'audit/FAILURE.json',{'error':repr(error),'unix':time.time()})
  except Exception:pass
  raise
