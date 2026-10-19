"""Select one explicit host/memory profile before any capacity probe or service."""
import argparse,json,os
from pathlib import Path
from r63_contract import ROOT,read,sha,require,expected_graph

def prepare(profile,root=ROOT):
 root=Path(root);require(not (root/'deploy_manifest.json').exists() and not (root/'processes/service.json').exists(),'sealed/launched producer cannot change profile')
 runtime=read(root/'configs/profiles'/(profile+'.json'))
 require(runtime['memory_mode'] in ('normal','lowvram','novram') and runtime['reserve_vram']==8,'runtime policy differs')
 (root/'configs/runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
 for case in read(root/'configs/scientific_contract.json')['cases']:
  path=root/'configs/graphs'/(case['run_id']+'.json');path.write_text(json.dumps(expected_graph(root,case),indent=2,ensure_ascii=False)+'\n')
 return runtime
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--profile',required=True);a=p.parse_args();print(json.dumps(prepare(a.profile),indent=2))
