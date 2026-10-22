"""Actual deployment import smoke in a fresh CPU-only process, no CUDA or model loads."""
import asyncio,json,os,subprocess,sys,time
from pathlib import Path
from r86_contract import ROOT,read,sha,require
from execution_gate import atomic

def main():
 runtime=read(ROOT/'configs/runtime.json');require(ROOT==Path(runtime['remote_root']),'actual deployment smoke only')
 require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','smoke must hide CUDA')
 sys.path=[p for p in sys.path if p!=str(ROOT/'extensions')]
 sys.path[:0]=[runtime['dependencies'],runtime['core'],str(ROOT/'scripts')]
 import torch
 require(not torch.cuda.is_initialized(),'CUDA already initialized')
 from compatibility_bootstrap import install,install_video_compat
 install();install_video_compat()
 import comfy.cli_args
 comfy.cli_args.args.cpu=True
 comfy.cli_args.args.use_pytorch_cross_attention=True
 import comfy.sd,comfy.utils,comfy.ldm.minimax.vae
 import nodes
 for name in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3CachedCondition'):
  require(asyncio.run(nodes.load_custom_node(str(ROOT/'extensions'/name))),'actual Comfy custom node load failed: '+name)
 cached=sys.modules[str(ROOT/'extensions/H3CachedCondition').replace('.','_x_')]
 positive,target,old,cache=cached.reconstruct(read(ROOT/'configs/CONDITION_CACHE.json'))
 # Exercise actual ModelPatcher.clone without loading a DiT/checkpoint.
 import tempfile
 import comfy.ldm.minimax.model as h3
 from comfy.model_patcher import ModelPatcher
 from r132_contract import science
 router_module=sys.modules[str(ROOT/'extensions/H3TemporalRouter').replace('.','_x_')]
 diffusion=h3.MiniMaxH3Model.__new__(h3.MiniMaxH3Model);torch.nn.Module.__init__(diffusion)
 diffusion.patch_size=(1,2,2);diffusion.latents_dim=24;diffusion.blocks=[None]*50
 holder=torch.nn.Module();holder.diffusion_model=diffusion
 base=ModelPatcher(holder,load_device=torch.device('cpu'),offload_device=torch.device('cpu'))
 original_validator=router_module.validate_run_contract;router_module.validate_run_contract=lambda *a:None
 states=[]
 try:
  with tempfile.TemporaryDirectory(dir=ROOT/'audit',prefix='cpu_patch_isolation_') as tmp:
   for c in science()['cases']:
    clone=router_module.H3FixedSchedule().apply(base,positive,c['arm'],'mass_preserve',c['alpha'],0,0,
         *c['physical_query_window'],0,50,0,20,'cpu_'+c['arm'],tmp,True)[0]
    patches=clone.model_options['transformer_options']['patches_replace']['dit']
    states.append(patches[('double_block',0)].state)
    require(len(patches)==50 and all(patches[('double_block',i)].state is states[-1] for i in range(50)),'patch state wiring differs')
    require(not base.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit',{}),'base loader contaminated')
   require(len({id(x) for x in states})==5 and all(x.forward_index==-1 for x in states),'arm state reused')
   try:
    router_module.H3FixedSchedule().apply(clone,positive,'early','mass_preserve',1.,0,0,*science()['cases'][0]['physical_query_window'],0,50,0,20,'must_reject',tmp,True)
   except ValueError as e:require('another DiT block patch' in str(e),'unexpected repatch rejection')
   else:raise ValueError('already patched model accepted')
 finally:router_module.validate_run_contract=original_validator
 require(str(ROOT/'extensions') not in sys.path,'namespace check was masked by ordinary extension import')
 require(not torch.cuda.is_initialized(),'CPU smoke initialized CUDA')
 from r132_contract import prepare_loader_inputs,RUN_ID
 [prepare_loader_inputs(name) for name in __import__("r132_contract").registry()[1]]
 result={'passed':True,'runtime_sha256':sha(ROOT/'configs/runtime.json'),'torch':torch.__version__,'CPU_only':True,'cuda_initialized':False,'modules':['compatibility_bootstrap.install','compatibility_bootstrap.install_video_compat','comfy.sd','comfy.ldm.minimax.vae','actual nodes.load_custom_node(H3EventAudit,H3PairAudit,H3TemporalRouter,H3X0Readout,H3CachedCondition)'],'model_loads':0,'actual_ModelPatcher_clone_count':5,'repatch_rejected':True,'actual_Comfy_namespace':True,'extensions_sys_path_absent':True,'four_cached_tensors_and_layout_verified':len(cache) in (4,5),'cached_module_sha256':sha(ROOT/'extensions/H3CachedCondition/__init__.py'),'unix':time.time()}
 atomic(ROOT/'audit/RUNTIME_IMPORT_SMOKE.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
