"""Static exact-parent/full-support validation, no GPU/network/service."""
from pathlib import Path
import argparse,json
from r29_contract import ROOT,read,sha,registry,validate_job

def check(root=ROOT,live=False):
 root=Path(root);s=read(root/'configs/scientific_contract.json');jobs,order=registry(root)
 if s['seeds']!=[2026101701] or s['arms']!=['global_full_6to14'] or s['captures']!=list(range(20)) or s['single_CUDA_process'] is not True or s['root_gate_before_CUDA'] is not True:raise ValueError('science contract differs')
 want={'mode':'mass_preserve','alpha':1.0,'radius':0,'time_offset':0,'step_interval_half_open':[6,15],'block_interval_half_open':[0,50],'pixel_interval_inclusive':[0,140],'latent_bins':list(range(42))}
 if s['router']!=want or s['NFE_per_job']!=20 or s['callback_count']!=20 or s['blocks_per_job']!=1000 or s['routed_blocks_per_job']!=450:raise ValueError('scientific operator/cost differs')
 for run in order:validate_job(run,root)
 for rel,row in read(root/'configs/runtime_kernel_hashes.json').items():
  if sha(root/rel)!=row['current_sha256']:raise ValueError('frozen kernel changed '+rel)
 a=read(root/'configs/admission.json')
 if live and a.get('ready_for_launch') is not True:raise ValueError('root admission required')
 seal=root/'deploy_manifest.json'
 if seal.exists():
  for rel,row in read(seal)['files'].items():
   if sha(root/rel)!=row['sha256']:raise ValueError('sealed bytes changed '+rel)
 return {'passed':True,'jobs':order,'planned_NFE':40,'only_CUDA_PID':'gated service_entry -> runpy compatibility_bootstrap -> Comfy same process','actual_GPU_and_quality_pending':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
