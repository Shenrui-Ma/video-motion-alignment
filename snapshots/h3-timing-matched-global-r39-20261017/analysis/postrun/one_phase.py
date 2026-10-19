"""Explicit root invocation; one bounded CPU phase, no permanent process."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from contract import *
import consume as base

def readiness(snapshot,state,now,seconds):
 if snapshot['status']!='success_files_present':return snapshot['status'],None
 if state is None or state['token']!=snapshot['token']:return 'stabilizing',{'token':snapshot['token'],'time':now}
 return ('ready' if now-state['time']>=seconds else 'stabilizing'),state

def prepare():
 require(not (HERE/'CONSUMER_FAILURE.json').exists(),'prior uncertain failure requires review')
 frozen=read(HERE/'FREEZE.json')
 for rel,d in frozen['files'].items():require(sha(safe(HERE,rel))==d,'frozen consumer changed '+rel)
 b=read(HERE/'BINDING.json');require(b.get('approved_for_consumer_start') is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'root actual binding absent')
 subprocess.run(base.SSH+[base.HOST,'mkdir -p '+shlex.quote(base.REMOTE)],check=True,timeout=30)
 files=[str(HERE/r) for r in frozen['files'] if '/' not in r]+[str(HERE/'BINDING.json'),str(HERE/'FREEZE.json'),str(HERE/'parents')]
 if (HERE/'AUTO_PARENT_BINDING.json').exists():files.append(str(HERE/'AUTO_PARENT_BINDING.json'))
 subprocess.run(['rsync','-a','-e',shlex.join(base.SSH),*files,base.HOST+':'+base.REMOTE+'/'],check=True,timeout=60)

def execute_one():
 with (Path(base.P['root_local'])/'analysis/postrun/unique_consumer.lock').open('a') as unique:
  try:fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy','scope':'R39 phase driver'}
  prepare();(HERE/'logs').mkdir(exist_ok=True);stamp=str(time.time_ns())
  def call(args):
   proc=base.remote(args);(HERE/'logs'/f'{stamp}_{args[0]}.log').write_text(proc.stdout+'\nSTDERR\n'+proc.stderr);return proc
  with base.CPU.open('a') as cpu:
   try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':'Mac CPU'}
   proc=call(['status'])
   if proc.returncode==75:return {'status':'busy','scope':'remote CPU or online pose'}
   state=base.parse_result(proc);phase=state['phase']
   if phase=='waiting_parent':return {'status':'waiting_parent','reason':'completed actual R32 final binding required','no_phase_started':True}
   if phase=='complete':base.sync_download();return {'status':'complete','no_phase_started':True}
   args=[phase]
   if phase=='archive':
    snap=base.parse_result(call(['snapshot']));save(HERE/'LATEST.json',snap);path=HERE/'ONE_PHASE_STABILITY.json';old=read(path) if path.exists() else None;mode,new=readiness(snap,old,time.time(),base.P['stability_seconds'])
    if new is not None:save(path,new)
    if mode!='ready':return {'status':mode,'no_phase_started':True}
    args+=['--token',snap['token']]
   else:require(phase in (*PHASES,'finalize'),'invalid next phase')
   proc=call(args)
   if proc.returncode==75:return {'status':'busy','scope':'remote CPU or online pose'}
   result=base.parse_result(proc);base.sync_download();return {'status':'phase_complete','phase':phase,'pid':os.getpid(),'time':time.time(),'more_requires_explicit_invocation':True}

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('Prepared only. Root-bound BINDING and --execute required.');return
 result=execute_one();save(HERE/'LAST_ONE_PHASE.json',result);print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except Exception as e:save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False});raise
