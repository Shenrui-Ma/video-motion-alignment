"""One bounded completed-case consumer call; shares full-batch driver locks."""
import argparse,fcntl,json,os,shlex,subprocess,time,traceback
from pathlib import Path
from contract import *
import consume as base
import one_phase

def remote(args):
 cmd=['env','TMPDIR='+base.P['root_remote']+'/temp','TMP='+base.P['root_remote']+'/temp','TEMP='+base.P['root_remote']+'/temp','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1',base.PYTHON,base.REMOTE+'/incremental_case.py',*args]
 p=subprocess.run(base.SSH+[base.HOST,shlex.join(cmd)],capture_output=True,text=True,timeout=900)
 folder=HERE/'logs';folder.mkdir(exist_ok=True);(folder/('incremental_'+str(time.time_ns())+'_'+args[0]+'.log')).write_text(p.stdout+'\nSTDERR\n'+p.stderr)
 return p

def download(run):
 dest=HERE/'completed_cases'/run;dest.mkdir(parents=True,exist_ok=True)
 subprocess.run(['rsync','-a','--bwlimit=1024','--exclude=*.pt','-e',shlex.join(base.SSH),base.HOST+':'+base.REMOTE+'/completed_cases/'+run+'/',str(dest)+'/'],check=True,timeout=600)
 inv=read(dest/'FILE_INVENTORY.json');derived=read(dest/'DERIVED_FILES.json');original={k:v for k,v in inv.items() if not k.endswith('.pt')}
 require({str(x.relative_to(dest)) for x in dest.rglob('*') if x.is_file()}==set(original)|set(derived)|{'FILE_INVENTORY.json','DERIVED_FILES.json'},'incremental local inventory differs')
 for rel,row in original.items():require(sha(safe(dest,rel))==row['sha256'],'incremental source download differs')
 for rel,digest in derived.items():require(sha(safe(dest,rel))==digest,'incremental derived download differs')
 return read(dest/'CASE_READY.json')

def execute(run):
 require(run in [x['run_id'] for x in base.P['cases']],'run outside declared5')
 failure=HERE/'audit'/('INCREMENTAL_FAILURE_'+run+'.json');require(not failure.exists(),'prior partial phase requires inspection')
 with (HERE/'unique_consumer.lock').open('a') as owner:
  try:fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'busy','phase_started':False}
  one_phase.prepare()
  snap=base.result(remote(['snapshot','--run',run]));statepath=HERE/'incremental_stability'/f'{run}.json'
  if snap['status']=='complete':return {'status':'case_ready','result':download(run),'phase_started':False}
  state=read(statepath) if statepath.exists() else None
  mode,state=one_phase.readiness(snap,state,time.time(),base.P['stability_seconds'])
  if state is not None:save(statepath,state)
  if mode!='ready':return {'status':mode,'run':run,'phase_started':False}
  with base.CPU.open('a') as cpu:
   try:fcntl.flock(cpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:return {'status':'busy','scope':'Mac CPU','phase_started':False}
   p=remote(['release','--run',run,'--token',snap['token']])
   if p.returncode==75:return {'status':'busy','scope':'remote CPU or online pose','phase_started':False}
   result=base.result(p);download(run);return {'status':'case_ready','result':result,'partial_batch':True,'planned_denominator':5}

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('Prepared only; --execute requires actual producer seal and service binding');return
 try:
  result=execute(a.run);save(HERE/'audit'/('INCREMENTAL_LATEST_'+a.run+'.json'),result);print(json.dumps(result,allow_nan=False))
 except Exception as exc:
  save(HERE/'audit'/('INCREMENTAL_FAILURE_'+a.run+'.json'),{'time':time.time(),'error':repr(exc),'traceback':traceback.format_exc(),'automatic_retry':False});raise
if __name__=='__main__':main()
