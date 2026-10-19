"""Bind final R89 seven-source contract and original/reference assets."""
import argparse,shutil
from common import *
PRODUCER=Path('/Users/researcher/DevProjects/h3-timing-ive-subject-capacity-r89-20261018')
EXPECTED='b3b25e8a00270a333762723d9f19c66bf6b64862790fcaa6438e898740be126b'
def prepare():
 require(sha(PRODUCER/'deploy_manifest.json')==EXPECTED,'final producer seal differs')
 contract=read(PRODUCER/'configs/scientific_contract.json');runtime=read(PRODUCER/'configs/runtime.json')
 for name,record in read(PRODUCER/'deploy_manifest.json')['files'].items():require(sha(PRODUCER/name)==record['sha256'],'producer sealed source changed: '+name)
 require(contract['source_ids']==list(PAIRS),'producer source order differs')
 for src,dst in [('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/runtime.json','configs/producer_runtime.json'),('deploy_manifest.json','configs/producer_deploy_manifest.json')]:shutil.copy2(PRODUCER/src,ROOT/dst)
 rows=[]
 for pair in PAIRS:
  cases=[c for c in contract['cases'] if c['source_id']==pair];require(len(cases)==2,'two fresh runs required');native=next(c for c in cases if c['arm']=='native');forced=next(c for c in cases if c['arm']=='forced')
  for k in ['prompt','video_sha256','provenance_sha256','geometry','valid_frame_count','evaluation_crop_xywh','original_task']:require(native[k]==forced[k],'pair metadata differs: '+k)
  row={'pair_key':pair,'source_id':pair,'prompt_version':native['prompt_version'],'prompt':native['prompt'],'original_task':native['original_task'],'valid_frames':native['valid_frame_count'],'geometry':native['geometry'],'evaluation_crop_xywh':native['evaluation_crop_xywh']}
  row['runs']={c['arm']:{'run_id':c['run_id'],'graph_sha256':sha(PRODUCER/'configs/graphs'/(c['run_id']+'.json'))} for c in cases}
  for role,field,digestfield in [('source','video','video_sha256'),('provenance','provenance','provenance_sha256'),('source_original','original_source',None)]:
   src=PRODUCER/'inputs'/native[field];require(src.is_file(),'original/reference asset missing');digest=native[digestfield] if digestfield else sha(src);require(sha(src)==digest,'asset differs');dst=ROOT/'inputs'/src.name
   if not dst.exists():shutil.copy2(src,dst)
   require(sha(dst)==digest,'existing input differs');row[role]={'file':str(dst.relative_to(ROOT)),'sha256':digest}
  rows.append(row)
 save(ROOT/'configs/contract.json',{'schema':'r89-media-consumer-contract-v1','producer_local':str(PRODUCER),'producer_remote':runtime['remote_root'],'producer_seal_sha256':EXPECTED,'producer_contract_sha256':sha(PRODUCER/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(PRODUCER/'configs/runtime.json'),'pair_order':list(PAIRS),'pairs':rows,'only_media':True,'GPU_launches':False,'method':'fixed denoising steps6..14, alpha1, all50blocks; online_observer=false'},replace=True)
def freeze():
 paths=[p for folder in ['scripts','configs','inputs','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r89-media-consumer-freeze-v1','producer_seal_sha256':EXPECTED,'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}},replace=True)
 return bound(ROOT/'CONSUMER_FREEZE.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--freeze-only',action='store_true');a=p.parse_args()
 if not a.freeze_only:prepare()
 print(json.dumps(freeze()))
