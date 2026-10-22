"""CPU exact actual-noise materialization; historical tensors remain on host41."""
from pathlib import Path
import json,shutil,sys
from r86_contract import ROOT,RUN,read,sha,require,registry
from execution_gate import atomic

def materialize(root=ROOT):
 root=Path(root);registry(root);require(str(root)==read(root/'configs/runtime.json')['remote_root'],'actual root required')
 spec=read(root/'configs/ACTUAL_NOISE.json');source=Path(spec['source_file']);meta=Path(spec['source_noise_manifest'])
 require(sha(source)==spec['source_sha256'] and sha(meta)==spec['source_noise_manifest_sha256'],'registered original noise files differ')
 noise=read(meta);require(noise['signature']==spec['signature'] and noise['actual_noise_streams']==spec['actual_noise_streams'],'noise metadata differs')
 import torch
 torch.set_num_threads(4);saved=torch.load(source,map_location='cpu',weights_only=True)
 sys.path.insert(0,str(root/'extensions'));from H3X0Readout.core import tensor_signature
 actual=[{k:v for k,v in tensor_signature(t).items() if k in ('shape','dtype','sha256')} for t in saved['tensors']]
 require(saved['signature']==spec['signature'] and actual==spec['actual_noise_streams'],'actual AV tensor bytes differ')
 require(not torch.cuda.is_initialized(),'materialization initialized CUDA')
 dest=root/'audit/r113_short_0252_seed2026101703_noise.pt'
 if not dest.exists():shutil.copyfile(source,dest)
 require(sha(dest)==spec['source_sha256'],'copied actual noise differs')
 folder=root/'prepared_parent';folder.mkdir(exist_ok=True)
 shutil.copyfile(meta,folder/'noise.json');shutil.copyfile(root/'design/r113_short_0252_seed2026101703_native_conditioning.json',folder/'conditioning.json')
 atomic(folder/'FILE_INVENTORY.json',{'noise':{'sha256':sha(dest),'bytes':dest.stat().st_size},'historical_tensor_intake':False})
 required=['prepared_parent/noise.json','prepared_parent/conditioning.json','prepared_parent/FILE_INVENTORY.json','configs/PARENT_CAPTURES.json','configs/PARENT_PAIR_GATE.json','configs/source.pose.json','audit/r113_short_0252_seed2026101703_noise.pt']
 case=read(root/'configs/protocol.json')['cases'][0]
 closure={'ready':True,'status':'READY','cases':{'short_0252':{'ready':True,'parent_run':case['parent_run'],'required_actual_files':required,'actual_file_sha256':{n:sha(root/n) for n in required}}},'historical_scope':'Source/prompt/sigma/actual noise strict. Host41 historical Qwen/VAE/prefix hashes diagnostic only.'}
 atomic(root/'configs/PARENT_CLOSURE.json',closure)
 binding=read(root/'configs/observer_external_bindings.json');seal=read(root/'deploy_manifest.json')
 binding['local_files']={p:v['sha256'] for p,v in seal['files'].items() if p.startswith(('scripts/','extensions/','configs/'))};binding['local_files']['configs/PARENT_CLOSURE.json']=sha(root/'configs/PARENT_CLOSURE.json');atomic(root/'configs/observer_bindings.json',binding)
 atomic(root/'audit/PARENT_MATERIALIZED.json',{'passed':True,'noise_sha256':sha(dest),'noise_tensor_signatures':actual,'closure_sha256':sha(root/'configs/PARENT_CLOSURE.json'),'cuda_initialized':False,'historical_tensor_copy_bytes':0})
 return closure
if __name__=='__main__':print(json.dumps(materialize(),indent=2))
