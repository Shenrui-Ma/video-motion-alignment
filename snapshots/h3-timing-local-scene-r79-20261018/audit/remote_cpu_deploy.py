import hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
R=Path('/data3/researcher/h3_runs/timing_local_scene_r79_20261018');C=R/'analysis/evaluation';bundle=R/'audit/CPU_DEPLOY_BUNDLE.tar.gz'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(bundle)=='1503c57ec5a96d7369514ee5f60be69a62070bcc4c014b7747a96838250782fe'
with tarfile.open(bundle) as t:
 for item in t.getmembers():
  assert item.isfile() and not Path(item.name).is_absolute() and '..' not in Path(item.name).parts,item.name
 t.extractall(R)
for d in ['logs','processes','temp','input','output','user']:(R/d).mkdir(exist_ok=True)
for d in ['inputs','prepared','tracks','controls','incoming','results','media','audit']:(C/d).mkdir(exist_ok=True)
files=json.loads((R/'audit/DEPLOY_FILES.json').read_text());assert all(sha(R/p)==v['sha256'] for p,v in files.items())
py='/data3/researcher/ComfyUI/.venv/bin/python';env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',TMPDIR=str(R/'temp'),TMP=str(R/'temp'),TEMP=str(R/'temp'))
checks=[]
def run(cwd,name,args):
 path=R/'audit'/name
 with path.open('w') as h:x=subprocess.run([py,*args],cwd=cwd,env=env,stdout=h,stderr=subprocess.STDOUT,timeout=300)
 checks.append(dict(name=name,exit_code=x.returncode,sha256=sha(path)));print(json.dumps(checks[-1]),flush=True);assert x.returncode==0,name
run(R,'HOST41_PRODUCER_TESTS.log',['-m','unittest','discover','-s','tests','-v'])
run(R,'HOST41_PREFLIGHT.json',['scripts/preflight.py'])
run(C,'HOST41_MATERIALIZED.json',['scripts/materialize_inputs.py','--producer-root',str(R)])
run(C,'HOST41_CONSUMER_TESTS.log',['-m','unittest','discover','-s','tests','-v'])
for sid in ['short_0144','short_0166']:
 run(C,f'HOST41_{sid}_CHECKONLY.log',['scripts/track_one.py','--source',sid,'--method','source','--check-only','--attempt','0'])
runtime=json.loads((R/'configs/runtime.json').read_text());core=Path(runtime['core']);corechecks={rel:sha(core/rel)==digest for rel,digest in json.loads((R/'configs/parent_core_hashes.json').read_text()).items()};assert all(corechecks.values())
value=dict(passed=True,gpu_calls=0,files_verified=len(files),checks=checks,actual_core_matches=corechecks,producer_seal_sha256=sha(R/'deploy_manifest.json'),consumer_freeze_sha256=sha(C/'CONSUMER_FREEZE.json'),admission_ready=json.loads((R/'configs/admission.json').read_text())['ready_for_launch'],service_started=(R/'processes/service.json').exists(),observed_unix=time.time())
assert value['admission_ready'] is False and value['service_started'] is False
(R/'audit/HOST41_CPU_DEPLOYMENT.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
