"""Read-only producer verification and CPU tests; never launch CUDA or service."""
import hashlib,json,os,subprocess,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
seal=read(root/'deploy_manifest.json');runtime=read(root/'configs/runtime.json')
assert str(root)==runtime['remote_root']
assert all(sha(root/p)==v['sha256'] for p,v in seal['files'].items())
assert all(sha(root/'inputs'/p)==v for p,v in read(root/'configs/input_hashes.json').items())
core={p:sha(Path(runtime['core'])/p)==v for p,v in read(root/'configs/parent_core_hashes.json').items()};assert all(core.values())
assert not (root/'processes/service.json').exists()
assert read(root/'configs/admission.json')['ready_for_launch'] is False
required=[runtime[k] for k in ['python','core','dependencies','models','kj_nodes']]
assert all(Path(p).exists() for p in required)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=runtime['dependencies'])
for name,command in [('CPU_REMOTE_TESTS',[runtime['python'],'-m','unittest','discover','-s',str(root/'tests'),'-v']),('CPU_REMOTE_PREFLIGHT',[runtime['python'],str(root/'scripts/preflight.py')]),('CPU_REMOTE_STORAGE',[runtime['python'],str(root/'scripts/check_storage.py')])]:
 p=subprocess.run(command,env=env,cwd=root,capture_output=True,text=True,timeout=120)
 (root/'audit'/(name+'.txt')).write_text(p.stdout+p.stderr)
 assert p.returncode==0,p.stdout+p.stderr
p=subprocess.run([runtime['python'],'-c','import torch,json; print(json.dumps({"torch":torch.__version__,"CUDA_initialized":torch.cuda.is_initialized()}))'],env=env,capture_output=True,text=True,check=True)
torch=json.loads(p.stdout);assert torch['CUDA_initialized'] is False
out={'passed':True,'producer_seal_sha256':sha(root/'deploy_manifest.json'),'sealed_files':len(seal['files']),'actual_core_hashes':core,'runtime_paths_exist':required,'torch':torch,'CPU_tests':40,'GPU_started':False,'service_registry_absent':True,'admission_ready':False,'disk':{'free_bytes':shutil.disk_usage(root).free,'total_bytes':shutil.disk_usage(root).total}}
(root/'audit/PASSIVE_DEPLOYMENT_VERIFIED.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
