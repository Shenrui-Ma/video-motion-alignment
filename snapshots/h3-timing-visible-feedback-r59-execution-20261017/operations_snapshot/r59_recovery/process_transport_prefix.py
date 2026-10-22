def identity(pid):
 p=Path('/proc')/str(pid)
 try:
  stat=(p/'stat').read_text(); tail=stat[stat.rindex(')')+2:].split()
  if tail[0]=='Z':return None
  command=(p/'cmdline').read_bytes()
  # /proc can expose an empty cmdline during process startup. Bind only after
  # exec has published the actual command; the existing launch deadline applies.
  if not command:return None
  return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':int(tail[19]),'cmdline_sha256':hashlib.sha256(command).hexdigest()}
 except (FileNotFoundError,ProcessLookupError):return None
def alive(entry):return entry is not None and identity(entry['pid'])==entry
def bind_launched_child(process,command,*,timeout=3,lookup=None,clock=time.monotonic,sleep=time.sleep):
 expected=hashlib.sha256(b'\0'.join(os.fsencode(v) for v in command)+b'\0').hexdigest()
 deadline=clock()+timeout;generation=None
 while process.poll() is None and clock()<deadline:
  candidate=(lookup or identity)(process.pid)
  if candidate is not None:
   current=(candidate['pid'],candidate['uid'],candidate['start_ticks'])
   require(candidate['uid']==os.getuid(),'launched child owner differs')
   if generation is None:generation=current
   require(current==generation,'child generation changed before command binding')
   if candidate['cmdline_sha256']==expected:return candidate
  sleep(.01)
 raise ValueError('unable to bind launched child to complete expected argv')
def bind_or_reap_launched_child(process,command):
 try:return bind_launched_child(process,command)
 except BaseException as primary:
  # This is our newly created, still-unregistered direct Popen child.
  try:
   if process.poll() is None:process.terminate()
   try:process.wait(timeout=8)
   except subprocess.TimeoutExpired:
    if process.poll() is None:process.kill()
    process.wait(timeout=10)
  except BaseException as cleanup:
   if hasattr(primary,'add_note'):primary.add_note('unregistered child cleanup: '+repr(cleanup))
  raise
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
def run_child(command,env,directory,label,timeout,parent,*,execution_started_path=None,execution_timeout=None):
 directory=Path(directory);log=directory/(label+'.log');start=time.monotonic();proc=None;entry=None;execution_start=None
 marker=None
 if execution_started_path is not None:
  marker=inside(str(Path(execution_started_path).absolute()),ROOT/'audit/observations')
  require(not marker.exists(),'execution marker already exists')
  require(isinstance(execution_timeout,(int,float)) and 0<execution_timeout<=780,'invalid child execution timeout')
 def check_execution_budget():
  nonlocal execution_start
  if marker is None:return
  if execution_start is None and marker.exists():
   try:record=read_json(marker)
   except json.JSONDecodeError:return  # write_new may be between open and write
   require(record.get('schema')=='h3-child-execution-start-v1' and record.get('identity')==entry,'execution marker identity differs')
   started=record.get('started_monotonic')
   require(type(started) in (int,float) and start<=started<=time.monotonic(),'execution marker time invalid')
   execution_start=record
  if execution_start is not None and time.monotonic()-execution_start['started_monotonic']>execution_timeout:
   raise TimeoutError(label+' execution timeout')
 try:
  require(alive(parent),'parent exited before child launch')
  with log.open('xb') as handle:
   proc=subprocess.Popen(command,env=env,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
   entry=bind_or_reap_launched_child(proc,command)
   write_new(directory/(label+'.process.json'),dict(entry,command=command,parent=parent,timeout_seconds=timeout,execution_timeout_seconds=execution_timeout,execution_started_path=str(marker) if marker else None))
   while proc.poll() is None:
    require(alive(parent),'parent exited during child execution')
    check_execution_budget()
    if time.monotonic()-start>timeout:raise TimeoutError(label+' total timeout')
    time.sleep(.2)
   if proc.returncode:raise ChildExitError(label+' exit '+str(proc.returncode)+'; see '+str(log),{'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start})
   check_execution_budget()
   if marker is not None:require(execution_start is not None,'successful child lacks execution start evidence')
 finally:
  if proc is not None:
   primary_error=sys.exc_info()[1];cleanup_error=None
   try:terminate_owned(proc,entry)
   except Exception as error:
    cleanup_error=type(error).__name__+': '+str(error)
    if primary_error is None:raise
   write_new(directory/(label+'.exit.json'),{'pid':proc.pid,'returncode':proc.returncode,'identity_absent':(not alive(entry) if entry is not None else proc.poll() is not None),'wall_seconds':time.monotonic()-start,'execution_start':execution_start,'cleanup_error':cleanup_error})
 return {'process':entry,'wall_seconds':time.monotonic()-start,'returncode':proc.returncode,'execution_start':execution_start}
