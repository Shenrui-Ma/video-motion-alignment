"""Root-invoked bounded CPU phase. No resident loop or producer mutation."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from contract import *
import consume as base

def readiness(snapshot,state,now,seconds):
 require(snapshot['status'] in ('pending','failed','success_files_present'),'unexpected producer status')
 if snapshot['status']!='success_files_present':return snapshot['status'],None
 if state is None or state['token']!=snapshot['token']:return 'stabilizing',{'token':snapshot['token'],'time':now}
 return ('ready' if now-state['time']>=seconds else 'stabilizing'),state

def prepare():
 require(base.P.get('producer_state')=='DEPLOYMENT_BOUND','formal producer deployment remains PENDING')
 require(not (HERE/'CONSUMER_FAILURE.json').exists(),'prior uncertain phase needs explicit review')
 freeze=read(HERE/'FREEZE.json')
 for rel,d in freeze['files'].items():require(sha(HERE/rel)==d,'consumer changed')
 b=read(HERE/'BINDING.json');require(b['approved_for_consumer_start'] is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json') and b['consumer_freeze_sha256']==sha(HERE/'FREEZE.json'),'root consumer binding/authorization')
 subprocess.run(base.SSH+[base.HOST,'mkdir -p '+shlex.quote(base.REMOTE)],check=True,timeout=30)
 sources=[str(HERE/r) for r in freeze['files'] if '/' not in r]+[str(HERE/'BINDING.json'),str(HERE/'FREEZE.json')]
 subprocess.run(['rsync','-a','-e',shlex.join(base.SSH),*sources,base.HOST+':'+base.REMOTE+'/'],check=True,timeout=60)

def execute_one():
 unique=(HERE/'unique_consumer.lock').open('a')
 try:fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:unique.close();return {'status':'busy','scope':'another R57 driver','no_phase_started':True}
 with unique:
  prepare();(HERE/'logs').mkdir(exist_ok=True);stamp=str(time.time_ns())
  def call(args):
   p=base.remote(args);(HERE/'logs'/('one_phase_'+stamp+'_'+args[0]+'.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
   return p
  snap=base.result(call(['snapshot']));save(HERE/'LATEST.json',snap)
  statepath=HERE/'ONE_PHASE_STABILITY.json';state=read(statepath) if statepath.exists() else None
  mode,state=readiness(snap,state,time.time(),base.P['stability_seconds'])
  if state is not None:save(statepath,state)
  elif statepath.exists():statepath.unlink()
  if mode!='ready':return {'status':mode,'snapshot':snap,'no_phase_started':True}
  # Only this context may own the Mac lock. Remote functions acquire the same
  # existing server lock nonblocking and yield to pending online pose.
  with base.CPU.open('a') as cpu:
   try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':'Mac CPU','no_phase_started':True}
   p=call(['status'])
   if p.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','no_phase_started':True}
   phase=base.result(p)
   if phase['phase']=='complete':
    base.download();return {'status':'complete','result':phase['result'],'no_phase_started':True}
   if phase['phase']=='await_root_release':return {'status':'await_root_release','phase':phase,'no_phase_started':True}
   args=[phase['phase']]
   if phase['phase']=='archive':args+=['--token',snap['token']]
   elif phase['phase']=='case':args+=['--run',phase['run']]
   else:require(phase['phase']=='finalize','unknown CPU phase')
   p=call(args)
   if p.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','no_phase_started':True}
   result=base.result(p)
   if phase['phase'] in ('archive','finalize'):base.download()
   return {'status':'phase_complete','phase':phase,'result':result,'pid':os.getpid(),'time':time.time(),'more_requires_explicit_invocation':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('Prepared one-phase CPU entry; root BINDING and --execute required; no wait loop');return
 result=execute_one();save(HERE/'LAST_ONE_PHASE.json',result);print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except Exception as exc:save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'entry':'one_phase','error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
