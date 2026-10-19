"""Static source/queue/graph checks; no GPU or automatic service action."""
from pathlib import Path
import argparse,json
from r24_contract import ROOT,read,sha,registry,validate_job

def check(root=ROOT,live=False):
 root=Path(root);science=read(root/'configs/scientific_contract.json')
 if science['seeds']!=[2026101610,2026101611] or science['arms']!=['native','full_6to14']:raise ValueError('frozen seed/arm changed')
 jobs,order=registry(root)
 for run in order:validate_job(run,root)
 for rel,row in read(root/'configs/original_extension_hashes.json').items():
  if rel in ('extensions/H3TemporalRouter/core.py','extensions/H3TemporalRouter/layout.py','extensions/H3X0Readout/core.py') and sha(root/rel)!=row['parent_sha256']:raise ValueError('frozen mathematical kernel changed')
 a=read(root/'configs/admission.json')
 if live and not a.get('ready_for_launch'):raise ValueError('root resource admission required')
 seal=root/'deploy_manifest.json'
 if seal.exists():
  for rel,row in read(seal)['files'].items():
   if sha(root/rel)!=row['sha256']:raise ValueError('sealed file changed: '+rel)
 return {'passed':True,'job_count':len(order),'jobs':order,'planned_NFE':20*len(order),'scope':'static only; actual pair/hardware/prefix005 pending'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(a.root,a.live),indent=2))
