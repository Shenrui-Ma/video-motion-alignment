"""Validate only small code, caches and CPU reconstruction; no weight scan."""
import os,subprocess
os.environ['CUDA_VISIBLE_DEVICES']=''
from r132_contract import ROOT,read,sha,require
from preflight import check
from execution_gate import atomic
r=read(ROOT/'configs/runtime.json');require(all(sha(ROOT/p)==v['sha256'] for p,v in read(ROOT/'deploy_manifest.json')['files'].items()),'deployed seal mismatch')
core={p:sha(__import__('pathlib').Path(r['core'])/p)==v for p,v in read(ROOT/'configs/parent_core_hashes.json').items()};require(all(core.values()),'core differs')
subprocess.run([r['python'],str(ROOT/'scripts/cpu_runtime_smoke.py')],check=True,env=dict(os.environ,PYTHONPATH=r['dependencies'],PYTHONDONTWRITEBYTECODE='1'))
atomic(ROOT/'audit/TARGET_CPU_VALIDATION.json',{'passed':True,'preflight':check(),'core_checks':core,'weights':'existing verified hash records reused; no full weights reread','producer_seal_sha256':sha(ROOT/'deploy_manifest.json')})
