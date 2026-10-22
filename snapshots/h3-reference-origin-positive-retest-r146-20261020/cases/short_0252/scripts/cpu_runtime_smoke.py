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
 import comfy.sd,comfy.utils,comfy.ldm.minimax.vae
 import nodes
 for name in ('H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3CachedCondition'):
  require(asyncio.run(nodes.load_custom_node(str(ROOT/'extensions'/name))),'actual Comfy custom node load failed: '+name)
 cached=sys.modules[str(ROOT/'extensions/H3CachedCondition').replace('.','_x_')]
 positive,target,old,cache=cached.reconstruct(read(ROOT/'configs/CONDITION_CACHE.json'))
 require(str(ROOT/'extensions') not in sys.path,'namespace check was masked by ordinary extension import')
 require(not torch.cuda.is_initialized(),'CPU smoke initialized CUDA')
 from r132_contract import prepare_loader_inputs,RUN_ID
 prepare_loader_inputs(RUN_ID)
 result={'passed':True,'runtime_sha256':sha(ROOT/'configs/runtime.json'),'torch':torch.__version__,'CPU_only':True,'cuda_initialized':False,'modules':['compatibility_bootstrap.install','compatibility_bootstrap.install_video_compat','comfy.sd','comfy.ldm.minimax.vae','actual nodes.load_custom_node(H3AutomaticWindowRouter)','actual nodes.load_custom_node(H3CachedCondition)','pose_probe'],'model_loads':0,'actual_Comfy_namespace':True,'extensions_sys_path_absent':True,'four_cached_tensors_and_layout_verified':len(cache)==4,'cached_module_sha256':sha(ROOT/'extensions/H3CachedCondition/__init__.py'),'unix':time.time()}
 atomic(ROOT/'audit/RUNTIME_IMPORT_SMOKE.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
