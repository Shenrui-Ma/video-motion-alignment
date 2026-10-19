"""Offline immutable science and parent verification; root separately admits hardware."""
from pathlib import Path
import argparse,json
from r30_contract import ROOT,RUN_ID,SEED,read,sha,registry,validate_job

def check(root=ROOT,live=False):
 root=Path(root);runtime=read(root/'configs/runtime.json')
 if runtime['remote_root']!='/data5/researcher/h3_runs/timing_forward_reverse_r30_20261017' or runtime['port']!=8493 or runtime['gpu_uuid']!='GPU-REDACTED':raise ValueError('frozen resource location differs')
 s=read(root/'configs/scientific_contract.json');p=read(root/'design/PROTOCOL.json');jobs,order=registry(root)
 if s['protocol_sha256']!=sha(root/'design/PROTOCOL.json') or p['seed']!=SEED or p['physical_window_inclusive']!=[50,65] or p['denoising_indices_half_open']!=[6,15] or p['blocks_half_open']!=[0,50] or p['alpha']!=1. or p['radius']!=0:raise ValueError('frozen protocol differs')
 if s['captures']!=list(range(20)) or s['NFE']!=20 or s['Euler_updates']!=20 or s['blocks']!=1000 or s['joint_calls']!=450 or s['component_calls']!={'forward':450,'reverse':450}:raise ValueError('call/capture contract differs')
 if s['continuous']!={'idle_hold_seconds':1800,'max_service_seconds':43200,'job_timeout_seconds':7200}:raise ValueError('lifecycle bounds differ')
 for name in order:validate_job(name,root)
 for rel,row in read(root/'configs/kernel_provenance.json').items():
  if sha(root/rel)!=row['sha256']:raise ValueError('frozen inherited numerical file changed '+rel)
 if live and read(root/'configs/admission.json')['ready_for_launch'] is not True:raise ValueError('root live admission pending')
 if (root/'deploy_manifest.json').exists():
  for rel,row in read(root/'deploy_manifest.json')['files'].items():
   if sha(root/rel)!=row['sha256']:raise ValueError('sealed source changed '+rel)
 return {'passed':True,'jobs':order,'NFE':20,'snapshots':21,'extra_full_Flash_per_active_block':1,'GPU_pending':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
