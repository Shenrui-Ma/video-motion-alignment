"""Root-authorized passive verification; never starts a service or CUDA work."""
import ast,hashlib,json,os,pathlib,subprocess,time
R=pathlib.Path('/data5/researcher/h3_runs/timing_ive_action_clips_r88_20261018')
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
assert not (R/'processes/service.json').exists()
runtime=read(R/'configs/runtime.json');assert runtime['remote_root']==str(R)
seal=read(R/'deploy_manifest.json');assert sha(R/'deploy_manifest.json')=='80b968fc4a21cc8b099cbfe370eba743d1b3e055abdffd6ce922959ccdd7b676'
for p,v in seal['files'].items():assert sha(R/p)==v['sha256'],p
inputs=read(R/'configs/input_hashes.json')
for p,digest in inputs.items():assert sha(R/'inputs'/p)==digest,p
core={p:sha(pathlib.Path(runtime['core'])/p)==digest for p,digest in read(R/'configs/parent_core_hashes.json').items()};assert len(core)==9 and all(core.values())
commands=[('cpu_tests',[runtime['python'],'-m','unittest','discover','-s','tests','-v']),('preflight',['python3','scripts/preflight.py']),('timeline',['python3','scripts/verify_input_timeline.py'])]
results=[]
for name,cmd in commands:
 t=time.monotonic();a=subprocess.run(cmd,cwd=R,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
 path=R/'audit'/('PASSIVE_'+name+'.log');path.write_bytes(a.stdout)
 results.append({'name':name,'command':cmd,'exit_code':a.returncode,'seconds':time.monotonic()-t,'log_sha256':sha(path)})
 if a.returncode:raise RuntimeError(name+': '+a.stdout.decode(errors='replace')[-4000:])
a=subprocess.run([runtime['python'],'-c','import torch,json;print(json.dumps({"torch":torch.__version__,"CUDA_initialized":torch.cuda.is_initialized()}))'],capture_output=True,text=True,env=os.environ,timeout=120,check=True);torch_env=json.loads(a.stdout);assert torch_env['CUDA_initialized'] is False
receipt={'passed':True,'sealed_files':len(seal['files']),'producer_seal_sha256':sha(R/'deploy_manifest.json'),'input_files':len(inputs),'core_matches':core,'commands':results,'torch':torch_env,'GPU_started':False,'service_started':False,'unix':time.time()};(R/'audit/PASSIVE_DEPLOYMENT_VERIFIED.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
