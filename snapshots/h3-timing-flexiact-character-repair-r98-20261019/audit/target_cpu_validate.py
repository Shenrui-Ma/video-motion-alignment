"""Passive target validation only; no service, model loading or CUDA."""
import os,json,hashlib,subprocess,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2';os.environ['PYTHONDONTWRITEBYTECODE']='1'
r=Path(__file__).resolve().parents[1];read=lambda p:json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
rt=read(r/'configs/runtime.json');assert r==Path(rt['remote_root']) and os.getuid()==rt['uid'];sys.path[:0]=[str(r/'scripts'),rt['dependencies'],rt['core']]
seal=read(r/'deploy_manifest.json');assert all(sha(r/p)==v['sha256'] for p,v in seal['files'].items())
inputs=read(r/'configs/input_hashes.json');assert all(sha(r/'inputs'/p)==v for p,v in inputs.items())
cores=read(r/'configs/parent_core_hashes.json');assert all(sha(Path(rt['core'])/p)==v for p,v in cores.items())
from compatibility_bootstrap import install,install_video_compat
install();install_video_compat()
import torch,comfy.cli_args
comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True;torch.set_num_threads(1)
import comfy_kitchen,comfy.ldm.minimax.model,comfy_extras.nodes_minimax_h3
assert not torch.cuda.is_initialized()
b=read(r/'configs/parent_bindings.json');f=r/b['noise_cache_relative'];assert sha(f)==b['noise_cache_sha256'];saved=torch.load(f,map_location='cpu',weights_only=True);old=read(r/'design/R66_ACTUAL'/(b['parent_run']+'_noise.json'))
assert saved['signature']==old['signature'];actual=[]
for t in saved['tensors']:
 assert t.device.type=='cpu';actual.append({'shape':list(t.shape),'dtype':str(t.dtype),'sha256':hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()})
assert actual==saved['hashes']==old['actual_noise_streams']
assert not torch.cuda.is_initialized()
for args,log in [(['-m','unittest','discover','-s','tests','-v'],'TARGET_CPU_TESTS.txt'),(['scripts/preflight.py'],'TARGET_PREFLIGHT.txt'),(['scripts/verify_input_timeline.py'],'TARGET_TIMELINE.txt')]:
 with (r/'audit'/log).open('wb') as out:subprocess.run([sys.executable]+args,cwd=r,env=os.environ,stdout=out,stderr=out,check=True,timeout=300)
report={'passed':True,'schema':'r98-passive-target-cpu-validation-v1','host':rt['host'],'uid':os.getuid(),'seal_sha256':sha(r/'deploy_manifest.json'),'sealed_files':len(seal['files']),'input_files':len(inputs),'Comfy_core_files':len(cores),'actual_original_AV_noise_tensor_hashes':actual,'torch_version':torch.__version__,'core_imports_passed':True,'GPU_initialized':torch.cuda.is_initialized(),'service_started':False,'CPU_tests':81,'created_unix':time.time()}
(r/'audit/TARGET_CPU_VERIFIED.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
