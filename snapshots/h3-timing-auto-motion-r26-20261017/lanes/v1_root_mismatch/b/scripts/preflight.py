"""Static source/queue/graph checks; no GPU or automatic service action."""
from pathlib import Path
import argparse,json
from r26_contract import ROOT,read,sha,registry,validate_job

def check(root=ROOT,live=False):
 root=Path(root);science=read(root/'configs/scientific_contract.json')
 if science['seeds']!=[2026101701] or science['arms']!=['native']:raise ValueError('frozen seed/arm changed')
 jobs,order=registry(root)
 for run in order:validate_job(run,root)
 if science['captures']!=list(range(20)) or science.get('no_intervention') is not True:raise ValueError('Native all-step capture policy changed')
 for rel,row in read(root/'configs/runtime_kernel_hashes.json').items():
  if sha(root/rel)!=row['current_sha256']:raise ValueError('frozen numeric/capture kernel changed')
 a=read(root/'configs/admission.json')
 if live and not a.get('ready_for_launch'):raise ValueError('root resource admission required')
 seal=root/'deploy_manifest.json'
 if seal.exists():
  for rel,row in read(seal)['files'].items():
   if sha(root/rel)!=row['sha256']:raise ValueError('sealed file changed: '+rel)
 return {'passed':True,'job_count':len(order),'jobs':order,'planned_NFE':20*len(order),'scope':'static only; actual hardware/20NFE/all-step archive pending'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
