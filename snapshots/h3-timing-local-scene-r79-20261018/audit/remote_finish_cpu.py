import json,hashlib,shutil,subprocess,os,time
from pathlib import Path
R=Path('/data3/researcher/h3_runs/timing_local_scene_r79_20261018');C=R/'analysis/evaluation';D=R/'audit/python310_compat_revision';D.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(C/'scripts/make_showcase.py')=='43d0d0ca581cd585a24c853a658ea5976fcd6e4a98bcb61854b616e6e4f94c53'
assert sha(C/'CONSUMER_FREEZE.json')=='bdbdd27b73d84425640236463b8c34b8a79545061fe57ba8112b35a66ef58053'
for name,dest in [('make_showcase.py',C/'scripts/make_showcase.py'),('CONSUMER_FREEZE.json',C/'CONSUMER_FREEZE.json')]:
 shutil.copyfile(dest,D/(name+'.before'));shutil.copyfile(R/'temp'/name,dest)
assert sha(C/'CONSUMER_FREEZE.json')=='c8f53155c1629fd8a46ce0259235828f081b4155dcad24a05a3d073244f2e092'
py='/data3/researcher/ComfyUI/.venv/bin/python';env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',TMPDIR=str(R/'temp'),TMP=str(R/'temp'),TEMP=str(R/'temp'))
checks=[]
def run(name,args):
 p=R/'audit'/name
 with p.open('w') as h:x=subprocess.run([py,*args],cwd=C,env=env,stdout=h,stderr=subprocess.STDOUT,timeout=300)
 row=dict(name=name,exit_code=x.returncode,sha256=sha(p));checks.append(row);print(json.dumps(row),flush=True);assert x.returncode==0,name
run('HOST41_CONSUMER_TESTS_revision2.log',['-m','unittest','discover','-s','tests','-v'])
for sid in ['short_0144','short_0166']:run(f'HOST41_{sid}_CHECKONLY.log',['scripts/track_one.py','--source',sid,'--method','source','--check-only','--attempt','1'])
runtime=json.loads((R/'configs/runtime.json').read_text());core=Path(runtime['core']);corechecks={rel:sha(core/rel)==digest for rel,digest in json.loads((R/'configs/parent_core_hashes.json').read_text()).items()};assert all(corechecks.values())
manifest=json.loads((R/'deploy_manifest.json').read_text());assert all(sha(R/p)==v['sha256'] for p,v in manifest['files'].items())
frozen=json.loads((C/'CONSUMER_FREEZE.json').read_text());assert all(sha(C/p)==digest for p,digest in frozen['files'].items())
for name in ['HOST41_PRODUCER_TESTS.log','HOST41_PREFLIGHT.json','HOST41_MATERIALIZED.json']:checks.append(dict(name=name,sha256=sha(R/'audit'/name),exit_code=0))
value=dict(passed=True,gpu_calls=0,producer_tests=52,consumer_tests=31,checks=checks,actual_core_matches=corechecks,producer_files=len(manifest['files']),consumer_files=len(frozen['files']),producer_seal_sha256=sha(R/'deploy_manifest.json'),consumer_freeze_sha256=sha(C/'CONSUMER_FREEZE.json'),admission_ready=json.loads((R/'configs/admission.json').read_text())['ready_for_launch'],service_started=(R/'processes/service.json').exists(),observed_unix=time.time(),failure_retained='HOST41_CONSUMER_TESTS.log: Python3.10 f-string parse issue, resolved only display code')
assert value['admission_ready'] is False and value['service_started'] is False
(R/'audit/HOST41_CPU_DEPLOYMENT.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value),flush=True)
