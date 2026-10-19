"""One root-approved final archive recovery. No resident worker or GPU action."""
import argparse,fcntl,shlex,subprocess,time,traceback
from contextlib import ExitStack
from common import *
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3'];HOST='H3_SERVER_A'
CPU=Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock')
def execute(download_only=False):
 p,root,old,legacy=bootstrap();approve(p);require(not (HERE/'FAILURE.json').exists(),'new failure requires explicit review')
 with ExitStack() as stack:
  for path in (root/'analysis/postrun/unique_consumer.lock',old/'unique_consumer.lock',HERE/'unique_consumer.lock',CPU):
   f=stack.enter_context(path.open('a'))
   try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':str(path),'no_phase_started':True}
  remote=p['root_remote']+'/'+p['new_postrun'];sources=[str(HERE/n) for n in read(HERE/'FREEZE.json')['files']]+[str(HERE/'FREEZE.json'),str(HERE/'BINDING.json')]
  subprocess.run(SSH+[HOST,'mkdir -p '+shlex.quote(remote)],check=True,timeout=30)
  subprocess.run(['rsync','-a','-e',shlex.join(SSH),*sources,HOST+':'+remote+'/'],check=True,timeout=90)
  stamp=str(time.time_ns());(HERE/'logs').mkdir(exist_ok=True)
  if not download_only:
   budget=p['timeout_seconds'];cmd=shlex.join(['env','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','/usr/bin/timeout','--signal=TERM','--kill-after=15s',str(budget)+'s','/home/researcher/miniconda3/envs/comfyui/bin/python',remote+'/remote_finalize.py','--execute'])
   out=subprocess.run(SSH+[HOST,cmd],capture_output=True,text=True,timeout=budget+60);(HERE/'logs'/f'{stamp}_final.log').write_text(out.stdout+'\nSTDERR\n'+out.stderr)
   if out.returncode==75:return {'status':'busy','scope':'remote CPU/online pose','no_phase_started':True}
   require(out.returncode==0,'remote limited recovery failed; retain partial and request review')
  # A completed remote receipt is mandatory for both initial and download-only resume.
  subprocess.run(['rsync','-a','-e',shlex.join(SSH),HOST+':'+remote+'/COMMIT_RECEIPT.json',str(HERE)+'/'],check=True,timeout=30)
  receipt=read(HERE/'COMMIT_RECEIPT.json');check_scope(receipt);require(receipt['passed'] is True and receipt['run']==p['run'],'wrong remote completion')
  target=HERE/'captured'/p['run'];target.mkdir(parents=True,exist_ok=True);archive=p['root_remote']+'/'+p['original_archive']
  subprocess.run(['rsync','-a','-e',shlex.join(SSH),'--exclude=*.pt',HOST+':'+archive+'/',str(target)+'/'],check=True,timeout=p['download_timeout_seconds'])
  local=legacy.validate_local_inventory(target);check_scope(read(target/'CPU_COMPLETE.json'));check_scope(read(target/'final/FINAL_SUMMARY.json'))
  for key,name in [('completion_sha256','CPU_COMPLETE.json'),('derived_inventory_sha256','DERIVED_FILES.json'),('original_inventory_sha256','FILE_INVENTORY.json')]:require(sha(target/name)==receipt[key],'download receipt mismatch '+name)
  checked_partial(target/'final',p['partial_files'],('EFFICIENCY.json','FINAL_SUMMARY.json'))
  require(sha(old/'CONSUMER_FAILURE.json')==p['old_failure_sha256'],'old failure changed')
  result={'status':'complete_with_failed_original_RGB_gate','run':p['run'],'local_archive':str(target),'remote_archive':archive,'local_inventory':local,'completion_sha256':sha(target/'CPU_COMPLETE.json'),'derived_inventory_sha256':sha(target/'DERIVED_FILES.json'),'old_failure_preserved':True,**scope_fields()}
  save_new(HERE/f'DOWNLOAD_{stamp}.json',result);return result

def main():
 a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');a.add_argument('--download-only',action='store_true');v=a.parse_args()
 if not v.execute:print('Preparation only. Root approval and --execute required; existing failed outcome remains failed.');return
 print(json.dumps(execute(v.download_only),allow_nan=False))
if __name__=='__main__':
 try:main()
 except Exception as e:
  if not (HERE/'FAILURE.json').exists():save_new(HERE/'FAILURE.json',{'error':repr(e),'traceback':traceback.format_exc(),'unix':time.time(),'automatic_retry':False})
  raise
