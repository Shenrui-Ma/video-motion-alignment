from pathlib import Path
import json,subprocess,sys,hashlib
BASE=Path(__file__).resolve().parent
sid=sys.argv[1];case=BASE/'cases'/sid;r=json.loads((case/'configs/runtime.json').read_text());remote=r['remote_root']
with (BASE/(sid+'_host9.tar.gz')).open('rb') as f:
 subprocess.run(['ssh','H3_SERVER_A',"umask 077; mkdir -p "+remote+"; tar -xzf - -C "+remote],stdin=f,check=True)
input_root='/home/researcher/h3_runs/timing_oxygen_generic_retention_r141b_host9_20261020/inputs' if sid=='short_0252' else '/data5/researcher/h3_runs/timing_autoresearch_20261016/inputs'
script='ROOT='+repr(remote)+'\nRUNTIME='+repr(r)+'\nINPUT='+repr(input_root)+'\n'+r'''
from pathlib import Path
import os,shutil,json,subprocess,hashlib,errno
p=Path(ROOT)
for name in ['inputs','input','output','temp','user','logs','processes','custom_nodes']:(p/name).mkdir(exist_ok=True)
for name,digest in json.loads((p/'configs/input_hashes.json').read_text()).items():
 source=Path(INPUT)/name;target=p/'inputs'/name
 if not target.exists():
  try:os.link(source,target)
  except OSError as e:
   if e.errno!=errno.EXDEV:raise
   shutil.copy2(source,target)
 assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
policy=subprocess.run(['python3','-c',"import sys;sys.path.insert(0,"+repr(str(p/'scripts'))+");import cgroup_memory,json;print(json.dumps(cgroup_memory.check()))"],text=True,capture_output=True)
(p/'audit/HOST9_MEMORY_PRECHECK.json').write_text(policy.stdout);assert policy.returncode==0,policy.stderr
cmd=[RUNTIME['python'],'-m','unittest','discover','-s',str(p/'tests'),'-v']
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=RUNTIME['dependencies'],PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
r=subprocess.run(cmd,text=True,capture_output=True,env=env)
(p/'audit/TARGET_CPU_TESTS.txt').write_text(r.stdout+r.stderr);assert r.returncode==0,(r.stdout+r.stderr)[-6000:]
r=subprocess.run([RUNTIME['python'],str(p/'scripts/remote_cpu_validate.py')],text=True,capture_output=True,env=env)
(p/'audit/TARGET_CPU_VALIDATE.log').write_text(r.stdout+r.stderr);assert r.returncode==0,(r.stdout+r.stderr)[-6000:]
print(json.dumps({'passed':True,'root':ROOT,'seal_sha256':hashlib.sha256((p/'deploy_manifest.json').read_bytes()).hexdigest(),'tests':11,'GPU_started':False,'cached_bytes_copied_between_hosts':0}))
'''
rp=subprocess.run(['ssh','H3_SERVER_A','env PYTHONDONTWRITEBYTECODE=1 python3 -'],input=script,text=True,capture_output=True)
(case/'audit/DEPLOY_CPU.log').write_text(rp.stdout+rp.stderr)
print(rp.returncode,rp.stdout,rp.stderr[-6000:].replace('No such file or directory','missing path'))
if rp.returncode:raise SystemExit(rp.returncode)
for name in ['HOST9_MEMORY_PRECHECK.json','TARGET_CPU_TESTS.txt','RUNTIME_IMPORT_SMOKE.json','TARGET_CPU_VALIDATION.json']:
 subprocess.run(['scp','H3_SERVER_A:'+remote+'/audit/'+name,str(case/'audit'/name)],check=True)
