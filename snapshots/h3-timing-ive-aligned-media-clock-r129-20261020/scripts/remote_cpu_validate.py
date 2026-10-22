"""Validate the deployed immutable package and existing inputs without CUDA."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import json,subprocess,sys,time
from pathlib import Path
from r129_contract import ROOT,read,sha,require,registry,prepare_loader_inputs
from preflight import check
from execution_gate import atomic

def main():
 runtime=read(ROOT/'configs/runtime.json');require(ROOT==Path(runtime['remote_root']),'target path differs')
 checks=check(ROOT)
 files=read(ROOT/'deploy_manifest.json')['files']
 require(all(sha(ROOT/p)==d['sha256'] for p,d in files.items()),'deployed bytes differ')
 cores={p:sha(Path(runtime['core'])/p)==v for p,v in read(ROOT/'configs/parent_core_hashes.json').items()};require(all(cores.values()),'actual core hash mismatch')
 weights={p:sha(Path(runtime['models'])/p)==v['sha256'] for p,v in read(ROOT/'configs/expected_checkpoint_hashes.json').items()};require(all(weights.values()),'actual weight hash mismatch')
 for run in registry()[1]:prepare_loader_inputs(run)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONPATH=runtime['dependencies'],PYTHONDONTWRITEBYTECODE='1')
 result=subprocess.run([runtime['python'],'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],env=env,capture_output=True,text=True,timeout=300)
 (ROOT/'audit/TARGET_CPU_TESTS.txt').write_text(result.stdout+result.stderr);require(result.returncode==0,'target CPU tests failed')
 atomic(ROOT/'audit/TARGET_CPU_VALIDATION.json',{'passed':True,'cuda_visible_devices':'','producer_seal_sha256':sha(ROOT/'deploy_manifest.json'),'files':len(files),'preflight':checks,'core_checks':cores,'weight_checks':weights,'parent_actual_AV_noise_sha256':sha(ROOT/'audit/r129_long_0039_seed2026101701_noise.pt'),'test_log_sha256':sha(ROOT/'audit/TARGET_CPU_TESTS.txt'),'created_unix':time.time()})
 print(json.dumps({'passed':True,'receipt':str(ROOT/'audit/TARGET_CPU_VALIDATION.json'),'sha256':sha(ROOT/'audit/TARGET_CPU_VALIDATION.json')}))
if __name__=='__main__':main()
