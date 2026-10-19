"""Bind the final local producer seal once; no remote execution or inference."""
import argparse,shutil
from common import *

def prepare(expected):
 require(len(expected)==64,'explicit final producer SHA required')
 require(not (ROOT/'CONSUMER_FREEZE.json').exists(),'consumer already frozen')
 c=config();producer=Path(c['producer_local']);manifest=producer/'deploy_manifest.json'
 require(sha(manifest)==expected,'producer seal differs from final supplied SHA')
 seal=read(manifest)
 for rel,value in seal['files'].items():
  require(not Path(rel).is_absolute() and '..' not in Path(rel).parts,'unsafe producer seal path')
  digest=value['sha256'] if isinstance(value,dict) else value
  require(sha(producer/rel)==digest,'producer static file changed: '+rel)
 contract=read(producer/'configs/scientific_contract.json');runtime=read(producer/'configs/runtime.json')
 require(runtime['uid']==1016 and runtime['port']==8571,'unexpected .9 runtime')
 require(c['host']=='H3_SERVER_A' and c['producer_remote']=='/data5/researcher/h3_runs/timing_ive_fireplace_recovery_r108_20261019','host/root changed')
 require(contract['source_ids']==list(SOURCES),'producer source denominator changed')
 cases={x['run_id']:x for x in contract['cases']}
 for p in c['sources']:
  for mode in ('native','forced'):
   run=p['run_id'] if mode=='native' else p['forced_run_id'];case=cases[run]
   require(case['source_id']==p['source_id'] and case['arm']==mode,'case identity differs')
   require(case['geometry']==p['geometry'] and case['valid_frame_count']==p['valid_frames'] and case['evaluation_crop_xywh']==p['crop_xywh'],'timeline/crop differs')
   require(case['prompt']==p['prompt'] and case['original_task']==p['original_task'] and case['clip']==p['clip'],'source task differs')
   require(case['reference_image_count']==0 and case['reference_video_count']==1,'unexpected reference scope')
   field='graph_sha256' if mode=='native' else 'forced_graph_sha256';p[field]=sha(producer/'configs/graphs'/f'{run}.json')
   for kind,key in [('source','video_sha256'),('provenance','provenance_sha256')]:
    require(sha(ROOT/p[kind]['file'])==p[kind]['sha256']==case[key]==sha(producer/p[kind]['file']),'source bytes changed')
 for dest,src in [('producer_seal.json','deploy_manifest.json'),('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json')]:shutil.copyfile(producer/src,ROOT/'configs'/dest)
 c['producer_seal_sha256']=expected;c['producer_runtime_sha256']=sha(producer/'configs/runtime.json');c['producer_contract_sha256']=sha(producer/'configs/scientific_contract.json')
 (ROOT/'configs/contract.json').write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
 files={str(p.relative_to(ROOT)):sha(p) for folder in ('scripts','tests','configs','inputs') for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r108-cpu-consumer-freeze-v1','producer_seal_sha256':expected,'files':files,'scope':'CPU only; Native preview and actual paired media use separate incoming/showcase directories'})
 validate_static();return bound(ROOT/'CONSUMER_FREEZE.json')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--final-producer-seal',required=True);a=p.parse_args();print(json.dumps(prepare(a.final_producer_seal)))
