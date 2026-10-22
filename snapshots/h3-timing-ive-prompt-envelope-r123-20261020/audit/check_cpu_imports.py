"""Actual host import-only compatibility check; no checkpoint loads and CUDA hidden."""
from pathlib import Path
import os,json,sys,importlib,importlib.metadata as metadata,hashlib,time
assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
R=Path(__file__).resolve().parents[1];runtime=json.loads((R/'configs/runtime.json').read_text());assert str(R)==runtime['remote_root'];assert os.getuid()==runtime['uid']
sys.path[:0]=[str(R/'scripts'),str(R/'extensions'),runtime['core'],runtime['dependencies']]
import comfy.cli_args
comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True
import compatibility_bootstrap
compatibility_bootstrap.install();compatibility_bootstrap.install_video_compat()
import torch,av
assert not torch.cuda.is_initialized()
modules={}
for name in ['comfy_kitchen','comfy_extras.nodes_minimax_h3','H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout']:
 m=importlib.import_module(name);modules[name]=str(m.__file__)
assert not torch.cuda.is_initialized()
versions={}
for name in ['torch','av','torchvision','numpy','safetensors','transformers','triton','comfy-kitchen']:
 try:versions[name]=metadata.version(name)
 except metadata.PackageNotFoundError:versions[name]=None
models={}
for rel,value in json.loads((R/'configs/expected_checkpoint_hashes.json').read_text()).items():
 p=Path(runtime['models'])/rel;s=p.stat();models[rel]={'path':str(p),'resolved':str(p.resolve()),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'expected_previously_bound_sha256':value['sha256'],'rehash_performed':False};assert s.st_size>0
result={'passed':True,'uid':os.getuid(),'python':sys.executable,'versions':versions,'modules':modules,'models':models,'CUDA_VISIBLE_DEVICES':'','cuda_initialized':torch.cuda.is_initialized(),'no_models_loaded':True,'created_unix':time.time()}
(R/'audit/ACTUAL_CPU_IMPORTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
