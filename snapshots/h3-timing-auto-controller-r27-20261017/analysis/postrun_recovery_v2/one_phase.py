"""Root-invoked bounded recovery. Defaults to preparation only."""
import argparse,fcntl,shlex,subprocess,time,traceback
from contextlib import ExitStack
from recovery_contract import *
import consume as base

def choose_phase(snapshot,requested=None):
 runs=[c['run_id'] for c in base.P['cases']]
 require(requested is None or requested in runs,'run outside recovery protocol')
 for run in ([requested] if requested else runs):
  v=snapshot['runs'][run];require(v['run']==run and v['phase'] in ('adopt','observation','final','complete'),'invalid phase')
  if v['phase']!='complete':return run,v
 return None,{'phase':'complete'}

def prepare():
 require(not (HERE/'CONSUMER_FAILURE.json').exists(),'uncertain prior phase needs explicit review')
 freeze=read(HERE/'FREEZE.json')
 for n,v in freeze['files'].items():require(sha(safe(HERE,n))==v,'recovery seal changed '+n)
 b=read(HERE/'BINDING.json');require(b['approved_for_consumer_start'] is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'root binding absent')
 old=Path(base.P['recovery']['local_original_postrun']);require(sha(old/'FREEZE.json')==base.P['recovery']['original_freeze_sha256'],'original postrun seal changed')
 subprocess.run(base.SSH+[base.HOST,'mkdir -p '+shlex.quote(base.REMOTE)],check=True,timeout=30)
 sources=[str(HERE/n) for n in freeze['files'] if '/' not in n]+[str(HERE/'BINDING.json'),str(HERE/'FREEZE.json')]
 subprocess.run(['rsync','-a','-e',shlex.join(base.SSH),*sources,str(HERE/'parents'),str(HERE/'history'),base.HOST+':'+base.REMOTE+'/'],check=True,timeout=60)

def execute_one(requested=None):
 with ExitStack() as stack:
  for path in [Path(base.P['recovery']['local_original_postrun'])/'unique_consumer.lock',HERE/'unique_consumer.lock']:
   f=stack.enter_context(path.open('a'))
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':'existing legacy/recovery coordinator','no_phase_started':True}
  prepare();(HERE/'logs').mkdir(exist_ok=True);stamp=str(time.time_ns())
  def call(args):
   p=base.remote(args);(HERE/'logs'/('one_phase_'+stamp+'_'+args[0]+'.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr);return p
  f=stack.enter_context(base.CPU.open('a'))
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy','scope':'Mac CPU','no_phase_started':True}
  snapshot=base.parse_result(call(['snapshot']));save(HERE/'LATEST.json',snapshot);run,phase=choose_phase(snapshot,requested)
  if run is None:
   selected=[requested] if requested else [c['run_id'] for c in base.P['cases']]
   for r in selected:base.sync_download(r)
   return {'status':'complete','runs':selected,'no_phase_started':True}
  args=[phase['phase'],'--run',run]
  if phase['phase']=='observation':args+=['--index',str(phase['index'])]
  p=call(args)
  if p.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','no_phase_started':True}
  result=base.parse_result(p)
  if phase['phase']=='final':base.sync_download(run)
  return {'status':'phase_complete','run':run,'phase':phase['phase'],'index':phase.get('index'),'result':result,'more_requires_explicit_invocation':True,'unix':time.time()}

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--run');args=p.parse_args()
 if not args.execute:print('Prepared only. Root binding and --execute required; one phase then exit.');return
 out=execute_one(args.run);save(HERE/'LAST_ONE_PHASE.json',out);print(json.dumps(out,allow_nan=False))
if __name__=='__main__':
 try:main()
 except Exception as e:save(HERE/'CONSUMER_FAILURE.json',{'unix':time.time(),'error':repr(e),'traceback':traceback.format_exc(),'automatic_retry':False,'producer_model_failure':False});raise
