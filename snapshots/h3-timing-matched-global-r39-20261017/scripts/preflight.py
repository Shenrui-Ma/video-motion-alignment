"""Offline immutable science check; root separately admits GPU and inherited numerical evidence."""
from pathlib import Path
import argparse,json
from r39_contract import ROOT,RUN_ID,SEED,read,sha,registry,validate_job

def check(root=ROOT,live=False):
 root=Path(root);rt=read(root/'configs/runtime.json');s=read(root/'configs/scientific_contract.json');p=read(root/'PROTOCOL.json');jobs,order=registry(root)
 if rt['remote_root']!='/data5/researcher/h3_runs/timing_matched_global_r39_20261017' or rt['port']!=8501 or rt['gpu_uuid']!='GPU-REDACTED':raise ValueError('frozen resource location differs')
 if s['protocol_sha256']!=sha(root/'PROTOCOL.json') or p['case']['seed']!=SEED or p['operator']['bins']!=list(range(42)) or p['schedule']['active_indices']!=[2,4,5,6]:raise ValueError('frozen scientific design differs')
 if s['captures']!=list(range(20)) or s['NFE']!=24 or s['Euler_updates']!=20 or s['blocks']!=1200 or s['route_calls']!=200 or s['online_observations']!=0:raise ValueError('call/capture contract differs')
 if s['continuous']!={'idle_hold_seconds':1800,'max_service_seconds':43200,'job_timeout_seconds':7200}:raise ValueError('lifecycle bounds differ')
 for name in order:validate_job(name,root)
 for name,row in read(root/'configs/kernel_provenance.json').items():
  if sha(root/name)!=row['sha256']:raise ValueError('inherited numerical file changed '+name)
 if live:
  if read(root/'configs/admission.json')['ready_for_launch'] is not True:raise ValueError('root live admission pending')
  from prelaunch_gates import check as gpu_check
  gpu_check(root)
 if (root/'deploy_manifest.json').exists():
  for name,row in read(root/'deploy_manifest.json')['files'].items():
   if sha(root/name)!=row['sha256']:raise ValueError('sealed source changed '+name)
 return {'passed':True,'jobs':order,'NFE':24,'Euler_updates':20,'snapshots':21,'branch_PT':24,'online_observations':0,'GPU_pending':not live}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
