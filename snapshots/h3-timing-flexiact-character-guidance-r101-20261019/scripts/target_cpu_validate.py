"""Passive target-only checks; imports torch on CPU, never starts CUDA or services."""
import json,os,sys,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
from r101_contract import ROOT,read,sha,require
from execution_gate import atomic
from preflight import check

def main():
 runtime=read(ROOT/'configs/runtime.json');require(str(ROOT)==runtime['remote_root'] and os.getuid()==runtime['uid'],'wrong target root/UID')
 report={'created_unix':time.time(),'passed':False,'preflight':check(),'uid':os.getuid(),'CUDA_started':False}
 report['seal']={p:sha(ROOT/p)==row['sha256'] for p,row in read(ROOT/'deploy_manifest.json')['files'].items()};require(all(report['seal'].values()),'seal mismatch')
 report['actual_core']={p:sha(Path(runtime['core'])/p)==v for p,v in read(ROOT/'configs/parent_core_hashes.json').items()};require(all(report['actual_core'].values()),'actual core mismatch')
 sys.path.insert(0,runtime['dependencies']);sys.path.insert(0,runtime['core'])
 import torch
 from compatibility_bootstrap import install,install_video_compat
 install();install_video_compat()
 sys.argv=[sys.argv[0],'--cpu']
 from comfy.cli_args import args
 args.cpu=True
 from comfy.ldm.minimax.model import PackedLayout
 report['torch']=torch.__version__;report['PackedLayout_imported']=True;require(not torch.cuda.is_initialized(),'unexpected CUDA initialization')
 from parent_evidence import verify_parent
 report['actual_parent_evidence']=verify_parent(ROOT,include_snapshots=True)
 report['passed']=True;atomic(ROOT/'audit/TARGET_CPU_VALIDATION.json',report)
 print(json.dumps({'passed':True,'seal_files':len(report['seal']),'actual_core_files':len(report['actual_core']),'actual_parents':list(report['actual_parent_evidence']),'torch':report['torch'],'CUDA_started':False}))
if __name__=='__main__':main()
