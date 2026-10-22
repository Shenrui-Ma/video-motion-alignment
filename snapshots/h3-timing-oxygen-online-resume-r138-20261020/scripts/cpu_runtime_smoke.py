"""Actual deployment import smoke in a fresh CPU-only process, no CUDA or model loads."""
import json,os,subprocess,sys,time
from pathlib import Path
from r86_contract import ROOT,read,sha,require
from execution_gate import atomic

def main():
 runtime=read(ROOT/'configs/runtime.json');require(ROOT==Path(runtime['remote_root']),'actual deployment smoke only')
 require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','smoke must hide CUDA')
 sys.path[:0]=[runtime['dependencies'],runtime['core'],str(ROOT/'scripts'),str(ROOT/'extensions')]
 import torch
 require(not torch.cuda.is_initialized(),'CUDA already initialized')
 from compatibility_bootstrap import install,install_video_compat
 install();install_video_compat()
 import comfy.cli_args
 comfy.cli_args.args.cpu=True
 import comfy.sd,comfy.utils,comfy.ldm.minimax.vae
 import H3AutomaticWindowRouter
 import pose_probe
 require(not torch.cuda.is_initialized(),'CPU smoke initialized CUDA')
 result={'passed':True,'runtime_sha256':sha(ROOT/'configs/runtime.json'),'torch':torch.__version__,'CPU_only':True,'cuda_initialized':False,'modules':['compatibility_bootstrap.install','compatibility_bootstrap.install_video_compat','comfy.sd','comfy.ldm.minimax.vae','H3AutomaticWindowRouter','pose_probe'],'model_loads':0,'unix':time.time()}
 atomic(ROOT/'audit/RUNTIME_IMPORT_SMOKE.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
