"""Mac CPU coordinator: verified pairs, preparation, display and pose; never CUDA."""
import fcntl,json,os,shlex,subprocess,sys,time,traceback
from common import *
REMOTE=read(ROOT/'configs/contract.json')['root_host41'];PY=read(ROOT/'configs/contract.json')['python_host41'];SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_B'];ADMIN=ROOT/'audit/watcher'
def atomic(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def call(script,args,timeout=900):
 command=['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=4','MKL_NUM_THREADS=4','OPENBLAS_NUM_THREADS=4',PY,REMOTE+'/scripts/'+script]+args
 p=subprocess.run(SSH+[shlex.join(command)],capture_output=True,text=True,timeout=timeout);log=ADMIN/'logs'/f'{script}_{time.time_ns()}.log';log.parent.mkdir(parents=True,exist_ok=True);log.write_text(p.stdout+'\nSTDERR\n'+p.stderr)
 if p.returncode==75:return None
 if p.returncode:raise RuntimeError(f'CPU phase {script} failed {p.returncode}; {log}')
 return p.stdout

def download(pair,physical=False):
 # No big x0/conditioning PT; only actual video and metadata needed by reviewer.
 rels=['incoming/'+pair+'/', 'prepared/'+pair+'/READY.json']
 if physical:rels+=['poses/'+pair+'/', 'source_pose/'+pair_info(pair)['motion_source_id']+'/', 'scores/physical/'+pair+'/']
 for rel in rels:
  dest=ROOT/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  cmd=['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=15']
  if rel.endswith('/'):
   dest.mkdir(exist_ok=True);cmd+=['--include=*/','--include=*.json','--include=*.mp4','--exclude=*']
  subprocess.run(cmd+['H3_SERVER_B:'+REMOTE+'/'+rel,str(dest)],check=True,timeout=180)
 dest=ROOT/'showcase';dest.mkdir(exist_ok=True)
 subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=15','--include='+pair+'_*','--exclude=*','H3_SERVER_B:'+REMOTE+'/showcase/',str(dest)+'/'],check=True,timeout=180)
 g=verify_gate(read(ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json'),pair)
 for m in METHODS:require(sha(ROOT/'incoming'/pair/f'{m}.mp4')==g['runs'][m]['video']['sha256'],'downloaded actual video changed')
 pr=read(dest/f'{pair}_PRESENTATION.json')
 for v in pr['videos']:require(sha(dest/Path(v['video']['file']).name)==v['video']['sha256'],'downloaded display changed')
 atomic(ADMIN/'receipts'/pair/('PHYSICAL_READY.json' if physical else 'MEDIA_READY.json'),{'pair':pair,'actual_gate':bound(ROOT/'incoming'/pair/'PAIR_RUNTIME_GATE.json'),'presentation':bound(dest/f'{pair}_PRESENTATION.json'),'CPU_only':True,'physical':physical})

def pair_physical(pair):
 action=pair_info(pair)['motion_source_id']
 query='from pathlib import Path;import json;r=Path('+repr(REMOTE)+');print(json.dumps({"source":(r/"source_pose"/'+repr(action)+'/"COMPLETE.json").is_file(),"native":(r/"poses"/'+repr(pair)+'/"native/COMPLETE.json").is_file(),"forced":(r/"poses"/'+repr(pair)+'/"forced/COMPLETE.json").is_file()}))'
 p=subprocess.run(SSH+[shlex.join(['python3','-c',query])],check=True,capture_output=True,text=True,timeout=40);s=json.loads(p.stdout)
 for phase,key,done in [('source',action,s['source']),('native',pair,s['native']),('forced',pair,s['forced'])]:
  if not done and call('physical.py',['--key',key,'--action',phase],timeout=420) is None:return False
 return call('physical.py',['--key',pair,'--action','evaluate'],timeout=180) is not None

def main():
 verify_runtime();ADMIN.mkdir(exist_ok=True)
 with (ADMIN/'watcher.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  atomic(ADMIN/'STARTED.json',{'pid':os.getpid(),'started_unix':time.time(),'argv':sys.argv,'consumer_freeze_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),'scope':'CPU-only watcher; root schedules MF CUDA'})
  while True:
   for pair in PAIR_KEYS:
    if (ADMIN/'receipts'/pair/'PHYSICAL_READY.json').exists():continue
    state=call('consume_pair.py',['--pair',pair,'--phase','status'],timeout=60)
    if state is None:continue
    s=json.loads(state)
    atomic(ADMIN/'STATUS.json',{'pair':pair,'state':s,'unix':time.time()})
    if not s['jobs_success']:continue
    for phase,key in [('verify','gate'),('collect','intake'),('prepare','prepared'),('render','rendered')]:
     if not s[key] and call('consume_pair.py',['--pair',pair,'--phase',phase]) is None:break
    else:
     if not (ADMIN/'receipts'/pair/'MEDIA_READY.json').exists():download(pair);print(json.dumps({'event':'MEDIA_READY','pair':pair}),flush=True)
     if not s['physical'] and not pair_physical(pair):continue
     download(pair,physical=True);print(json.dumps({'event':'PHYSICAL_READY','pair':pair}),flush=True)
   if all((ADMIN/'receipts'/p/'PHYSICAL_READY.json').exists() for p in PAIR_KEYS):atomic(ADMIN/'COMPLETE.json',{'passed':True,'all_six':True,'GPU_started':False});return
   time.sleep(45)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  atomic(ADMIN/('FAILURE_'+str(time.time_ns())+'.json'),{'error':repr(error),'traceback':traceback.format_exc(),'GPU_started':False});raise
