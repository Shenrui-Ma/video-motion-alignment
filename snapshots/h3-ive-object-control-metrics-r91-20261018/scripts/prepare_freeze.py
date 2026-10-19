"""Bind final R91 two-source contract and original/reference assets."""
import argparse,shutil
from common import *
PRODUCER=Path('/Users/researcher/DevProjects/h3-timing-ive-object-control-r91-20261018')
EXPECTED='e6a43151e1e61d09ad2a68d7c9a40d20d9dc8c72e2ed399b9c316a246f9745b8'
def prepare():
 require(sha(PRODUCER/'deploy_manifest.json')==EXPECTED,'final producer seal differs')
 contract=read(PRODUCER/'configs/scientific_contract.json');runtime=read(PRODUCER/'configs/runtime.json')
 for name,record in read(PRODUCER/'deploy_manifest.json')['files'].items():require(sha(PRODUCER/name)==record['sha256'],'producer sealed source changed: '+name)
 require(contract['source_ids']==list(PAIRS),'producer source order differs')
 for src,dst in [('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/runtime.json','configs/producer_runtime.json'),('deploy_manifest.json','configs/producer_deploy_manifest.json')]:shutil.copy2(PRODUCER/src,ROOT/dst)
 rows=[]
 for pair in PAIRS:
  cases=[c for c in contract['cases'] if c['source_id']==pair];require(len(cases)==2,'two fresh runs required');native=next(c for c in cases if c['arm']=='native');forced=next(c for c in cases if c['arm']=='forced')
  require(native['reference_image_count']==forced['reference_image_count']==0,'unexpected reference image');require(native['reference_video_count']==forced['reference_video_count']==1,'reference video count differs')
  for k in ['prompt','video_sha256','provenance_sha256','geometry','valid_frame_count','evaluation_crop_xywh','original_task']:require(native[k]==forced[k],'pair metadata differs: '+k)
  row={'pair_key':pair,'source_id':pair,'prompt_version':native['prompt_version'],'prompt':native['prompt'],'original_task':native['original_task'],'reference_image_used':False,'reference_image_count':native['reference_image_count'],'evaluation_scope':native['evaluation_scope'],'clip':native['clip'],'display_task':{'short_0114':'将篮球替换为霓虹发光球，保留原球员、运球动作和球场。','long_0039':'将取放中的书改为蓝色，保留原人物、拿书动作和办公室。'}[pair],'valid_frames':native['valid_frame_count'],'geometry':native['geometry'],'evaluation_crop_xywh':native['evaluation_crop_xywh']}
  row['runs']={c['arm']:{'run_id':c['run_id'],'graph_sha256':sha(PRODUCER/'configs/graphs'/(c['run_id']+'.json'))} for c in cases}
  (ROOT/'configs/graphs').mkdir(exist_ok=True)
  for c in cases:
   src=PRODUCER/'configs/graphs'/(c['run_id']+'.json');g=read(src)
   require(g['5']['inputs']['prompt']==c['prompt'] and not any(n.get('class_type')=='LoadImage' for n in g.values()),'prompt or no-reference-image graph differs')
   shutil.copy2(src,ROOT/'configs/graphs'/src.name)
  for role,field,digestfield in [('source','video','video_sha256'),('provenance','provenance','provenance_sha256'),('source_original','original_source',None)]:
   src=PRODUCER/'inputs'/native[field];require(src.is_file(),'original/reference asset missing');digest=native[digestfield] if digestfield else sha(src);require(sha(src)==digest,'asset differs');dst=ROOT/'inputs'/src.name
   if not dst.exists():shutil.copy2(src,dst)
   require(sha(dst)==digest,'existing input differs');row[role]={'file':str(dst.relative_to(ROOT)),'sha256':digest}
  rows.append(row)
 save(ROOT/'configs/contract.json',{'schema':'r91-media-consumer-contract-v1','producer_local':str(PRODUCER),'producer_remote':runtime['remote_root'],'producer_seal_sha256':EXPECTED,'producer_contract_sha256':sha(PRODUCER/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(PRODUCER/'configs/runtime.json'),'pair_order':list(PAIRS),'pairs':rows,'only_media':True,'GPU_launches':False,'method':'fixed denoising steps6..14, alpha1, all50blocks; online_observer=false'},replace=True)
def freeze():
 paths=[p for folder in ['scripts','configs','inputs','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r91-media-consumer-freeze-v1','producer_seal_sha256':EXPECTED,'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}},replace=True)
 return bound(ROOT/'CONSUMER_FREEZE.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--freeze-only',action='store_true');a=p.parse_args()
 if not a.freeze_only:prepare()
 print(json.dumps(freeze()))
