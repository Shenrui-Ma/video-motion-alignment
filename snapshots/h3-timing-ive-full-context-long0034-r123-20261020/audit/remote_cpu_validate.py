from pathlib import Path
import os,json,hashlib,subprocess,time
R=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
runtime=read(R/'configs/runtime.json');assert str(R)==runtime['remote_root'];manifest=read(R/'deploy_manifest.json');assert not(R/'processes/service.json').exists()
checks={'seal':{p:sha(R/p)==v['sha256'] for p,v in manifest['files'].items()},'inputs':{p:sha(R/'inputs'/p)==v for p,v in read(R/'configs/input_hashes.json').items()},'core':{p:sha(Path(runtime['core'])/p)==v for p,v in read(R/'configs/parent_core_hashes.json').items()}}
assert all(all(v.values()) for v in checks.values()),checks
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=runtime['dependencies'],LC_ALL='C',LANG='C')
commands=[('target_imports',[runtime['python'],'audit/check_cpu_imports.py']),('target_preflight',[runtime['python'],'scripts/preflight.py']),('target_pts',[runtime['python'],'scripts/verify_input_timeline.py']),('target_tests',[runtime['python'],'-m','unittest','discover','-s','tests','-v'])]
results={}
for name,argv in commands:
 start=time.monotonic()
 with (R/'audit'/(name+'.log')).open('wb') as out:q=subprocess.run(argv,cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=600)
 results[name]={'exit_code':q.returncode,'wall_seconds':time.monotonic()-start};assert q.returncode==0,(name,q.returncode)
value={'passed':True,'root':str(R),'seal_sha256':sha(R/'deploy_manifest.json'),'checks':checks,'commands':results,'CUDA_VISIBLE_DEVICES':'','producer_started':False,'imports':read(R/'audit/ACTUAL_CPU_IMPORTS.json'),'created_unix':time.time()};(R/'audit/TARGET_CPU_VERIFIED.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value,indent=2))
