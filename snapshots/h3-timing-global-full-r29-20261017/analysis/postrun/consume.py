"""One CPU consumer for R29 fixed two-job batch; default is prepare-only."""
import argparse,fcntl,os,shlex,subprocess,time,traceback
from pathlib import Path
from contract import *
P=read(HERE/'PROTOCOL.json');REMOTE=P['root_remote']+'/analysis/postrun';HOST='H3_SERVER_A';PYTHON='/home/researcher/miniconda3/envs/comfyui/bin/python';CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock');SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3']

def remote(args):
 return subprocess.run(SSH+[HOST,shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',PYTHON,REMOTE+'/remote_consume.py',*args])],capture_output=True,text=True,timeout=900)
def result(p):
 require(p.returncode==0,'remote phase failed; no automatic retry');return json.loads([x for x in p.stdout.splitlines() if x.strip()][-1])
def check_download(arc):
 inv=read(arc/'FILE_INVENTORY.json');original={k:v for k,v in inv.items() if not k.endswith('.pt')};allowed={'FILE_INVENTORY.json'}|({'ADMIN_RELEASE_ACCEPTANCE.json'} if (arc/'ADMIN_RELEASE_ACCEPTANCE.json').exists() else set())
 if (arc/'DERIVED_FILES.json').exists():
  derived=read(arc/'DERIVED_FILES.json');done=read(arc/'CPU_COMPLETE.json');require(done['passed'] is True and set(done['derived_outputs'])|{'CPU_COMPLETE.json'}==set(derived),'local completion omitted output');allowed.add('DERIVED_FILES.json')
 else:derived={x:sha(arc/x) for x in ('RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json')}
 require({str(x.relative_to(arc)) for x in arc.rglob('*') if x.is_file()}==set(original)|set(derived)|allowed,'local exact non-PT inventory')
 for rel,row in original.items():require(sha(safe(arc,rel))==row['sha256'],'original download SHA')
 for rel,d in derived.items():require(sha(safe(arc,rel))==d,'derived download SHA')
def download():
 dest=HERE/'captured/batch';dest.mkdir(parents=True,exist_ok=True);subprocess.run(['rsync','-a','--exclude=*.pt','-e',shlex.join(SSH),HOST+':'+REMOTE+'/captured/batch/',str(dest)+'/'],check=True,timeout=600);check_download(dest);save(HERE/'DOWNLOAD.json',{'file_inventory_sha256':sha(dest/'FILE_INVENTORY.json'),'all_PT_retained_and_verified_remote':True,'time':time.time()})
def main():
 p=argparse.ArgumentParser();p.add_argument('--start',action='store_true');a=p.parse_args()
 if not a.start:print('Prepared only; --start requires root BINDING and review');return
 unique=(HERE/'unique_consumer.lock').open('a');fcntl.flock(unique,fcntl.LOCK_EX|fcntl.LOCK_NB);require(not (HERE/'CONSUMER_FAILURE.json').exists(),'prior failure needs explicit review')
 freeze=read(HERE/'FREEZE.json')
 for rel,d in freeze['files'].items():require(sha(HERE/rel)==d,'consumer changed')
 b=read(HERE/'BINDING.json');require(b['approved_for_consumer_start'] is True and b['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'root consumer binding/authorization')
 subprocess.run(SSH+[HOST,'mkdir -p '+shlex.quote(REMOTE)],check=True);sources=[str(HERE/rel) for rel in freeze['files'] if '/' not in rel]+[str(HERE/'BINDING.json'),str(HERE/'FREEZE.json')];subprocess.run(['rsync','-a','-e',shlex.join(SSH),*sources,str(HERE/'parents'),HOST+':'+REMOTE+'/'],check=True)
 save(HERE/'CONSUMER_IDENTITY.json',{'pid':os.getpid(),'start':time.time(),'freeze_sha256':sha(HERE/'FREEZE.json'),'binding_sha256':sha(HERE/'BINDING.json'),'scope':'CPU only; producer read-only'})
 stable=None;(HERE/'logs').mkdir(exist_ok=True)
 while True:
  time.sleep(10)  # waiting never owns either CPU lock
  snap=result(remote(['snapshot']));save(HERE/'LATEST.json',snap)
  if snap['status']=='failed':save(HERE/'PRODUCER_FAILED.json',snap);return
  if snap['status']!='success_files_present':time.sleep(30);continue
  if stable is None or stable['token']!=snap['token']:stable={'token':snap['token'],'time':time.time()}
  if time.time()-stable['time']<P['stability_seconds']:time.sleep(30);continue
  with CPU.open('a') as cpu:
   try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:time.sleep(1);continue
   p=remote(['status'])
   if p.returncode==75:continue
   phase=result(p)
   if phase['phase']=='complete':download();save(HERE/'STATE.json',{'phase':'CPU_complete','time':time.time()});return
   args=[phase['phase']]
   if phase['phase']=='archive':args+=['--token',snap['token']]
   if phase['phase']=='case':args+=['--run',phase['run']]
   p=remote(args);(HERE/'logs'/f'{phase["phase"]}_{time.time_ns()}.log').write_text(p.stdout+'\nSTDERR\n'+p.stderr)
   if p.returncode==75:continue
   value=result(p);save(HERE/'LAST_PHASE.json',{'phase':phase,'result':value});print(json.dumps({'CPU_phase_complete':phase}),flush=True)
   if phase['phase'] in ('archive','finalize'):download()
  time.sleep(3)
if __name__=='__main__':
 try:main()
 except Exception as exc:save(HERE/'CONSUMER_FAILURE.json',{'time':time.time(),'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
