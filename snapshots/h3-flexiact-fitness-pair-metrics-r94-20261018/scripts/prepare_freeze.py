"""Bind finalized R94 scientific files and small local reference assets."""
import argparse,shutil
from common import *
PRODUCER=Path('/Users/researcher/DevProjects/h3-timing-flexiact-fitness-pair-r94-20261018')
EXPECTED='ce0f3f802bd6a4fd65ddd299cf859b831945e52510f769a40dccdc0d37ed5a09'
def prepare():
 require(sha(PRODUCER/'deploy_manifest.json')==EXPECTED,'final producer seal differs')
 contract=read(PRODUCER/'configs/scientific_contract.json');runtime=read(PRODUCER/'configs/runtime.json')
 for name,record in read(PRODUCER/'deploy_manifest.json')['files'].items():require(sha(PRODUCER/name)==record['sha256'],'producer sealed source changed: '+name)
 require(contract['pair_keys']==list(PAIRS),'producer pair order differs')
 for src,dst in [('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/runtime.json','configs/producer_runtime.json'),('deploy_manifest.json','configs/producer_deploy_manifest.json')]:shutil.copy2(PRODUCER/src,ROOT/dst)
 rows=[]
 for pair in PAIRS:
  cases=[c for c in contract['cases'] if c['pair_key']==pair];require(len(cases)==2,'two fresh runs required');native=next(c for c in cases if c['arm']=='native');forced=next(c for c in cases if c['arm']=='forced')
  for k in ['prompt','prompt_sha256','video_sha256','portrait_sha256','provenance_sha256']:require(native[k]==forced[k],'pair conditioning metadata differs')
  row={k:native[k] for k in ['pair_key','motion_source_id','original_pair_id','group','prompt_version','prompt','prompt_sha256']}
  row['runs']={c['arm']:{'run_id':c['run_id'],'graph_sha256':sha(PRODUCER/'configs/graphs'/(c['run_id']+'.json'))} for c in cases}
  for role,field,digestfield in [('source','video','video_sha256'),('target','portrait','portrait_sha256'),('provenance','provenance','provenance_sha256')]:
   src=PRODUCER/'inputs'/native[field];require(sha(src)==native[digestfield],'source asset differs');dst=ROOT/'inputs'/src.name
   if not dst.exists():shutil.copy2(src,dst)
   require(sha(dst)==native[digestfield],'existing input differs');row[role]={'file':str(dst.relative_to(ROOT)),'sha256':sha(dst)}
  original=PRODUCER/'inputs'/f'source_{native["motion_source_id"]}_original.mp4';dst=ROOT/'inputs'/original.name
  if not dst.exists():shutil.copy2(original,dst)
  require(sha(dst)==sha(original),'original video differs');row['source_original_8fps']={'file':str(dst.relative_to(ROOT)),'sha256':sha(dst)}
  rows.append(row)
 save(ROOT/'configs/contract.json',{'schema':'r94-media-consumer-contract-v1','producer_local':str(PRODUCER),'producer_remote':runtime['remote_root'],'producer_seal_sha256':EXPECTED,'producer_contract_sha256':sha(PRODUCER/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(PRODUCER/'configs/runtime.json'),'pair_order':list(PAIRS),'pairs':rows,'only_media':True,'GPU_launches':False},replace=True)

def freeze():
 paths=[p for folder in ['scripts','configs','inputs','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r94-media-consumer-freeze-v1','producer_seal_sha256':EXPECTED,'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}},replace=True)
 return bound(ROOT/'CONSUMER_FREEZE.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--freeze-only',action='store_true');a=p.parse_args()
 if not a.freeze_only:prepare()
 print(json.dumps(freeze()))
