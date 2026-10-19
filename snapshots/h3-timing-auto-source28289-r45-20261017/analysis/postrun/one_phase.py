"""Root-invoked one CPU phase; no resident loop, GPU, service or queue operations."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from contract import *
import consume as base

def readiness(snapshot,state,now,seconds):
 if snapshot['status']!='success_files_present':return snapshot['status'],None
 if state is None or state['token']!=snapshot['token']:return 'stabilizing',{'token':snapshot['token'],'time':now}
 return ('ready' if now-state['time']>=seconds else 'stabilizing'),state

def prepare():
 require(not (HERE/'CONSUMER_FAILURE.json').exists(),'prior uncertain phase requires explicit review')
 freeze=read(HERE/'FREEZE.json')
 for rel,d in freeze['files'].items():require(sha(safe(HERE,rel))==d,'consumer changed '+rel)
 b=read(HERE/'BINDING.json');require(b['approved_for_consumer_start'] is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'root binding absent')
 subprocess.run(base.SSH+[base.HOST,'mkdir -p '+shlex.quote(base.REMOTE)],check=True,timeout=30)
 sources=[str(HERE/r) for r in freeze['files'] if '/' not in r]+[str(HERE/'BINDING.json'),str(HERE/'FREEZE.json')]
 subprocess.run(['rsync','-a','-e',shlex.join(base.SSH),*sources,str(HERE/'parents'),base.HOST+':'+base.REMOTE+'/'],check=True,timeout=60)

def execute_one():
 with (HERE/'unique_consumer.lock').open('a') as unique:
  try:fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy','scope':'another R45 phase driver','no_phase_started':True}
  prepare();run=base.P['cases'][0]['run_id'];(HERE/'logs').mkdir(exist_ok=True);stamp=str(time.time_ns())
  def call(args):
   proc=base.remote(args);(HERE/'logs'/('one_phase_'+stamp+'_'+args[0]+'.log')).write_text(proc.stdout+'\nSTDERR\n'+proc.stderr);return proc
  # Once an archive receipt exists remotely, status needs only the small anchors.
  # Initial readiness uses completion metadata, sizes, mtimes and JSON hashes.
  with base.CPU.open('a') as cpu:
   try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':'Mac CPU','no_phase_started':True}
   proc=call(['status','--run',run])
   if proc.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','no_phase_started':True}
   phase=base.parse_result(proc)
   if phase['phase']=='complete':
    base.sync_download(run);return {'status':'complete','run':run,'no_phase_started':True}
   args=[phase['phase'],'--run',run]
   if phase['phase']=='archive':
    snap=base.parse_result(call(['snapshot']));save(HERE/'LATEST.json',snap)
    statepath=HERE/'ONE_PHASE_STABILITY.json';state=read(statepath) if statepath.exists() else None
    mode,state=readiness(snap['runs'][run],state,time.time(),base.P['stability_seconds'])
    if state is not None:save(statepath,state)
    if mode!='ready':return {'status':mode,'run':run,'no_phase_started':True}
    args+=['--token',snap['runs'][run]['token']]
   elif phase['phase']=='observation':args+=['--index',str(phase['index'])]
   else:require(phase['phase']=='final','unexpected phase')
   proc=call(args)
   if proc.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','no_phase_started':True}
   result=base.parse_result(proc)
   if phase['phase'] in ('archive','final'):base.sync_download(run)
   return {'status':'phase_complete','run':run,'phase':phase['phase'],'index':phase.get('index'),'pid':os.getpid(),'time':time.time(),'more_requires_explicit_invocation':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('Prepared only; root-bound BINDING and --execute required. One bounded phase per invocation.');return
 result=execute_one();save(HERE/'LAST_ONE_PHASE.json',result);print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
 try:main()
 except Exception as exc:save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'entry':'one_phase','error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
