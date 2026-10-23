"""Run only delegated unfinished AWQ metrics under the existing 30 GiB budget."""
from pathlib import Path
import os,fcntl,json,subprocess,time,sys,hashlib
R=Path(__file__).resolve().parent;D=R/'run';P=R.parent;BASE=P.parent

def atomic(p,data):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(data,indent=2));t.replace(p)
def identity(pid):
 p=Path('/proc')/str(pid);return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19]}
def alive(rec):
 try:
  a=identity(rec['pid']);state=(Path('/proc')/str(rec['pid'])/'stat').read_text().rsplit(')',1)[1].split()[0]
  return a['uid']==rec['uid'] and a['start_ticks']==str(rec['start_ticks']) and state!='Z'
 except FileNotFoundError:return False
with (D/'launch.lock').open('a') as lock,(BASE/'deployment.lock').open('a') as shared:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(shared,fcntl.LOCK_EX|fcntl.LOCK_NB)
 own=identity(os.getpid());atomic(D/'supervisor_identity.json',own)
 workerfile=D/'worker_identity.json'
 if workerfile.exists():assert not alive(json.loads(workerfile.read_text()))
 release=json.loads((D/'source_release.json').read_text());manifest=json.loads((D/'expected_manifest.json').read_text());assert release['status']=='delegated_active' and manifest==release['pending_manifest'] and len(manifest['jobs'])==10
 checks=json.loads((BASE/'weights_verified.json').read_text());assert len(checks['verified'])>=11
 for row in checks['verified']:
  p=BASE/'weights/Qwen2.5-VL-72B-Instruct-AWQ'/row['path'];assert p.stat().st_size==row['size'] and p.stat().st_mtime<checks['time']
 # CPU-only dry run and immutable source/input SHA gates precede model allocation.
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONNOUSERSITE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TMPDIR=str(P/'tmp'),HF_HOME=str(P/'cache/huggingface'),TRITON_CACHE_DIR=str(P/'cache/triton'),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',NO_PROXY='*',no_proxy='*')
 for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(k,None)
 env['PATH']=str(P/'bin')+':'+str(P/'venv/bin')+':'+env.get('PATH','')
 args=[str(P/'venv/bin/python'),'-u',str(R/'batch_eval.py'),'--manifest',str(D/'expected_manifest.json'),'--output',str(D/'evaluation_awq'),'--model',str(BASE/'weights/Qwen2.5-VL-72B-Instruct-AWQ'),'--path-map','/data/research-user/h3_metrics_20261022='+str(R/'staged')]
 result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=120);assert result.returncode==0,result.stderr;dry=json.loads(result.stdout);assert dry['ready']==10;atomic(D/'dry_run.json',dry)
 deadline=time.time()+48*3600;cards=['GPU-REPLACE-WITH-DEVICE-UUID','GPU-REPLACE-WITH-DEVICE-UUID']
 while True:
  evidence=[]
  for card in cards:
   uuid,free,total,util=[x.strip() for x in subprocess.check_output(['nvidia-smi','-i',card,'--query-gpu=uuid,memory.free,memory.total,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=20).strip().split(',')];evidence.append({'uuid':uuid,'free_mib':int(free),'total_mib':int(total),'healthy':util.isdigit()})
  if all(e['uuid']==c and e['healthy'] and e['free_mib']>=37500 for e,c in zip(evidence,cards)):break
  atomic(D/'status.json',{'status':'waiting_gpu_budget','cards':evidence,'time':time.time()});assert time.time()<deadline;time.sleep(60)
 atomic(D/'admission.json',{'cards':evidence,'allocator_cap_gib_per_card':30,'time':time.time()})
 with (D/'evaluation.log').open('a',buffering=1) as log:
  worker=subprocess.Popen(args+['--run'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);rec=identity(worker.pid);rec['command']=args+['--run'];atomic(workerfile,rec);atomic(D/'status.json',{'status':'running','worker':rec,'time':time.time()});rc=worker.wait()
 atomic(D/'status.json',{'status':'completed' if rc==0 else 'failed','exit_code':rc,'time':time.time()})
