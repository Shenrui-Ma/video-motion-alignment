"""Root-authorized single middle-pair CPU verification; no model or service API."""
import hashlib,json,os,subprocess,time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_ive_subject_capacity_r89_20261018')
SOURCE='short_0358'
OUT=R/'audit/timely_short_0358_cpu_20261018'
GATE=R/'analysis/postrun'/SOURCE/'PAIR_RUNTIME_GATE.json'
SEAL='b3b25e8a00270a333762723d9f19c66bf6b64862790fcaa6438e898740be126b'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def require(ok,why):
 if not ok:raise RuntimeError(why)
def save(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def check_owner(owner):
 require(owner['pid']==36315 and str(owner['identity']['start_ticks'])=='2635074861','bound R89 generation differs')
 p=Path('/proc')/str(owner['pid']);stat=(p/'stat').read_text();ticks=stat.rsplit(') ',1)[1].split()[19]
 require(ticks==str(owner['identity']['start_ticks']),'service start identity differs')
 require(p.stat().st_uid==owner['identity']['uid'],'service UID differs')
 command=(p/'cmdline').read_bytes().replace(b'\x00',b' ').decode().strip()
 require(command==owner['identity']['cmdline'].strip(),'service command differs')
 require(read(R/'processes/service.json')==owner,'owner record differs')
def state():
 d=read(R/'logs/controller_state.json');queue=read(R/'configs/queue.json')['jobs'];done=d['completed']
 require(queue[:len(done)]==done,'completed order differs')
 remaining=queue[len(done):];pair=[f'r89_{SOURCE}_seed2026101701_{arm}' for arm in ('native','forced')]
 require(all(x in done for x in pair),'0358 pair not yet completed')
 require(pair!=queue[:2] and pair!=queue[-2:],'first/final pair not authorized')
 require(d['status']=='pending_or_running' and remaining and d['current'] in remaining,'final wrapper owns verification now')
 return d,remaining,pair
def main():
 require(not GATE.exists() and not GATE.with_name('PAIR_RUNTIME_GATE_FAILURE.json').exists(),'gate already exists; do not rerun')
 require(sha(R/'deploy_manifest.json')==SEAL,'producer seal changed')
 d,remaining,pair=state();owner=read(R/'processes/service.json');check_owner(owner);outputs=[]
 for run in pair:
  jobp=R/'logs'/f'{run}_job.json';hp=R/'logs'/f'{run}_history.json';job=read(jobp);history=read(hp)
  require(job['status']=='success' and job['name']==run,'job incomplete')
  require(job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'],'job owner differs')
  require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][1]==job['prompt_id'],'history incomplete')
  images=history['outputs']['14']['images'];require(len(images)==1 and images[0]['type']=='output','history output not single')
  im=images[0];rel=Path(im.get('subfolder',''))/im['filename'];require(not rel.is_absolute() and '..' not in rel.parts,'unsafe output path')
  p=R/'output'/rel;require(p.is_file() and not p.is_symlink() and p.stat().st_size>0,'output not closed file')
  outputs.append({'run_id':run,'file':str(p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha(p),'job_sha256':sha(jobp),'history_sha256':sha(hp)})
 time.sleep(2)
 for row in outputs:
  p=Path(row['file']);require((p.stat().st_size,p.stat().st_mtime_ns)==(row['bytes'],row['mtime_ns']),'output still changing')
  for fd in (Path('/proc')/str(owner['pid'])/'fd').iterdir():
   try:target=os.readlink(fd)
   except FileNotFoundError:continue
   require(target!=row['file'],'service still has output open')
 check_owner(owner);d,remaining,_=state();require(not GATE.exists(),'gate appeared; no rerun')
 previous={str(p):sha(p) for p in (R/'analysis/postrun').glob('*/PAIR_RUNTIME_GATE.json')}
 argv=['/home/researcher/miniconda3/envs/comfyui/bin/python','analysis/postrun/verify_pair.py','--source',SOURCE]
 overrides={'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONPATH':'/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps'}
 OUT.mkdir(exist_ok=True)
 save(OUT/'STARTED.json',{'schema':'r89-timely-single-pair-cpu-verifier-start-v1','source_id':SOURCE,'unix':time.time(),'cwd':str(R),'argv':argv,'environment_overrides':overrides,'controller_before':d,'remaining_jobs':remaining,'outputs_closed_and_stable':outputs,'previous_gates_sha256':previous,'producer_seal_sha256':SEAL,'execution_limit':'one invocation for this middle pair only'})
 started=time.monotonic();result={'source_id':SOURCE,'invocations':1}
 try:
  with (OUT/'VERIFY.log').open('x') as log:process=subprocess.run(argv,cwd=R,env={**os.environ,**overrides},stdout=log,stderr=subprocess.STDOUT,timeout=600)
  result['returncode']=process.returncode
 except BaseException as error:
  result['error']=repr(error)
 finally:
  result['wall_seconds']=time.monotonic()-started;result['previous_gates_unchanged']=all(sha(Path(p))==h for p,h in previous.items())
  if GATE.is_file():
   gate=read(GATE);result.update(gate_sha256=sha(GATE),passed=gate['passed'],checks=gate['checks'],runs={arm:{k:r[k] for k in ('run_id','video','valid_frames','NFE','routed_blocks','job_wall_seconds')} for arm,r in gate['runs'].items()})
  save(OUT/'RESULT.json',result)
 print(json.dumps(result))
 require(result.get('returncode')==0 and result.get('passed') is True and result['previous_gates_unchanged'],'CPU gate failed; preserve receipt')
if __name__=='__main__':main()
