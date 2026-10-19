"""Single CPU-only coordinator. Requires explicit --start and root-bound live owner."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']

def remote(args,timeout=900):
 cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args])
 return subprocess.run(SSH+[HOST,cmd],capture_output=True,text=True,timeout=timeout)

def sync_download(run):
 target=HERE/'captured'/run;target.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),'--exclude=*.pt',HOST+':'+REMOTE+'/captured/'+run+'/',str(target)+'/'],check=True,timeout=600)
 validation=validate_local_inventory(target)
 original=read(target/'FILE_INVENTORY.json')
 for rel,d in original.items():
  if not rel.endswith('.pt'):require(sha(safe(target,rel))==d['sha256'],'downloaded archive changed '+rel)
 if (target/'DERIVED_FILES.json').exists():
  for rel,d in read(target/'DERIVED_FILES.json').items():require(sha(safe(target,rel))==d,'downloaded derived output changed '+rel)
 save(HERE/(run+'_DOWNLOAD.json'),{'original_inventory_sha256':sha(target/'FILE_INVENTORY.json'),'large_PT_archived_and_verified_remote':True,'local_inventory':validation,'download_scope':'all non-PT original and derived files; full raw tensors retained under exact remote archive','observed_unix':time.time()})

def parse_result(proc):
 require(proc.returncode==0,'remote CPU phase failed; do not retry uncertain phase automatically')
 lines=[x for x in proc.stdout.splitlines() if x.strip()]
 return json.loads(lines[-1])

def run():
 lock=(HERE/'unique_consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 freeze=read(HERE/'FREEZE.json')
 for rel,d in freeze['files'].items():require(sha(safe(HERE,rel))==d,'consumer source changed '+rel)
 b=read(HERE/'BINDING.json');require(b['approved_for_consumer_start'] is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'root approval/binding missing')
 require(not (HERE/'CONSUMER_FAILURE.json').exists(),'prior failure needs explicit root-reviewed recovery')
 subprocess.run(SSH+[HOST,'mkdir -p '+shlex.quote(REMOTE)],check=True,timeout=30)
 # Only new postrun consumer files; producer runtime/config are never copied or edited.
 sources=[str(HERE/rel) for rel in freeze['files'] if '/' not in rel]+[str(HERE/'FREEZE.json'),str(HERE/'BINDING.json')]
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),*sources,HOST+':'+REMOTE+'/'],check=True,timeout=60)
 subprocess.run(['rsync','-a','-e',shlex.join(SSH),str(HERE/'parents'),HOST+':'+REMOTE+'/'],check=True,timeout=60)
 identity={'pid':os.getpid(),'started_unix':time.time(),'protocol_sha256':sha(HERE/'PROTOCOL.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'binding_sha256':sha(HERE/'BINDING.json'),'scope':'CPU/read-only producer; no GPU/API/service control'};save(HERE/'CONSUMER_IDENTITY.json',identity)
 statepath=HERE/'STATE.json';state=read(statepath) if statepath.exists() else {'processed':[],'failures':{},'stable':{},'phase':'waiting'}
 # Resume revalidates each completed archive once; subsequent polling does not rehash it.
 state['processed']=[]
 logdir=HERE/'logs';logdir.mkdir(exist_ok=True)
 while True:
  snap_proc=remote(['snapshot'],timeout=60);snap=parse_result(snap_proc);save(HERE/'LATEST.json',snap)
  for case in P['cases']:
   name=case['run_id'];s=snap['runs'][name]
   if name in state['failures'] or name in state['processed']:continue
   if s['status']=='failed':state['failures'][name]=s;save(statepath,state);continue
   if s['status']!='success_files_present':continue
   old=state['stable'].get(name)
   if not old or old['token']!=s['token']:state['stable'][name]={'token':s['token'],'since':time.time()};save(statepath,state);continue
   if time.time()-old['since']<P['stability_seconds']:continue
   with CPU.open('a') as cpu:
    try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:continue
    # Even resume validation hashes large archives, so it also obeys both CPU locks.
    phase_proc=remote(['status','--run',name]);
    if phase_proc.returncode==75:continue
    phase=parse_result(phase_proc)
    if phase['phase']=='complete':
     if name not in state['processed']:sync_download(name);state['processed'].append(name)
     save(statepath,state);continue
    args=[phase['phase'],'--run',name]
    if phase['phase']=='archive':args+=['--token',s['token']]
    if phase['phase']=='observation':args+=['--index',str(phase['index'])]
    key=name+'_'+phase['phase']+('_'+str(phase['index']) if 'index' in phase else '')
    state['phase']=key;save(statepath,state);proc=remote(args);stamp=str(time.time_ns());(logdir/(key+'_'+stamp+'.log')).write_text(proc.stdout+'\nSTDERR\n'+proc.stderr)
    if proc.returncode==75:state['phase']='waiting_CPU_or_online_pose';save(statepath,state);continue
    result=parse_result(proc)
    if phase['phase'] in ('archive','final'):sync_download(name)
    save(HERE/'LAST_PHASE.json',{'run':name,'phase':phase,'completed_unix':time.time(),'result':result})
    print(json.dumps({'run':name,'CPU_phase_complete':phase['phase'],'index':phase.get('index')}),flush=True)
   state['phase']='waiting';save(statepath,state)
  if len(state['processed'])+len(state['failures'])==len(P['cases']):
   state['phase']='CPU_complete' if not state['failures'] else 'finished_with_producer_failures';save(statepath,state);return
  time.sleep(2 if any(v.get('status')=='success_files_present' for v in snap['runs'].values()) else 30)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--start',action='store_true');args=parser.parse_args()
 if not args.start:print('Prepared only. --start requires root BINDING.json and final independent review.');return
 run()
if __name__=='__main__':
 try:main()
 except Exception as exc:
  save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False,'producer_files_changed':False});raise
