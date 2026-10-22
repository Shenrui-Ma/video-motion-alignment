"""Freeze R86 media bindings and exact historical R73 Native/fixed assets."""
import argparse,shutil
from common import *
PRODUCER=Path('/Users/researcher/DevProjects/h3-timing-oxygen-online-r86-20261018')
PARENT=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018')
EXPECTED='918b4389897b47362b0a39d1c9dbe43bbe54f324491df7a316948f5b85fe49da'
def prepare():
 require(sha(PRODUCER/'deploy_manifest.json')==EXPECTED,'R86 seal differs')
 for name,row in read(PRODUCER/'deploy_manifest.json')['files'].items():require(sha(PRODUCER/name)==row['sha256'],'producer sealed file changed: '+name)
 science=read(PRODUCER/'configs/scientific_contract.json');protocol=read(PRODUCER/'configs/protocol.json');runtime=read(PRODUCER/'configs/runtime.json');case=science['cases'][0]
 require(len(science['cases'])==1 and case['run_id']==RUN and case['valid_frame_count']==98 and case['geometry']=={'width':1312,'height':736,'frames':107,'fps':24},'single oxygen contract differs')
 for src,dst in [('configs/scientific_contract.json','configs/producer_scientific_contract.json'),('configs/protocol.json','configs/producer_protocol.json'),('configs/runtime.json','configs/producer_runtime.json'),('deploy_manifest.json','configs/producer_deploy_manifest.json'),('configs/PARENT_PAIR_GATE.json','configs/PARENT_PAIR_GATE.json')]:shutil.copy2(PRODUCER/src,ROOT/dst)
 gate=read(ROOT/'configs/PARENT_PAIR_GATE.json');require(gate['passed'] is True and sha(ROOT/'configs/PARENT_PAIR_GATE.json')==science['parent_gate_sha256'],'parent gate differs');require(sha(PARENT/'incoming'/SOURCE/'PAIR_RUNTIME_GATE.json')==science['parent_gate_sha256'],'cached parent gate differs')
 assets={}
 for role,name in [('source',case['video']),('source_original',case['original_source']),('provenance',case['provenance'])]:
  src=PRODUCER/'inputs'/name;dst=ROOT/'inputs'/name
  if not dst.exists():shutil.copy2(src,dst)
  require(sha(dst)==sha(src),'input asset differs');assets[role]={'file':str(dst.relative_to(ROOT)),'sha256':sha(dst)}
 require(assets['source']['sha256']==case['video_sha256'] and assets['provenance']['sha256']==case['provenance_sha256'],'source contract hashes differ')
 for role in ('native','forced'):
  src=PARENT/'incoming'/SOURCE/(role+'.mp4');require(sha(src)==gate['runs'][role]['video']['sha256'],'actual R73 video differs');dst=ROOT/'inputs'/('r73_'+role+'.mp4')
  if not dst.exists():shutil.copy2(src,dst)
  require(sha(dst)==sha(src),'existing parent video differs');assets[role]={'file':str(dst.relative_to(ROOT)),'sha256':sha(dst),'run_id':gate['runs'][role]['run_id'],'historical_remote':gate['runs'][role]['video']['file']}
 save(ROOT/'configs/contract.json',{'schema':'r86-media-consumer-contract-v1','producer_local':str(PRODUCER),'producer_remote':runtime['remote_root'],'producer_seal_sha256':EXPECTED,'producer_contract_sha256':sha(PRODUCER/'configs/scientific_contract.json'),'protocol_sha256':sha(PRODUCER/'configs/protocol.json'),'producer_runtime_sha256':sha(PRODUCER/'configs/runtime.json'),'parent_gate_sha256':science['parent_gate_sha256'],'graph_sha256':sha(PRODUCER/'configs/graphs'/(RUN+'.json')),'source_id':SOURCE,'run_id':RUN,'case':case,'assets':assets,'spatial_selection':protocol['person_selection'],'only_media':True,'GPU_launches':False,'planned_denominator':1,'method':'actual online visible_only, manual adult xcenter.40-.75; temporal windows/start/stop automatic; allspatial attention queries; actual schedule pending'},replace=True)
def freeze():
 paths=[p for folder in ['scripts','configs','inputs','tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
 save(ROOT/'CONSUMER_FREEZE.json',{'schema':'r86-media-consumer-freeze-v1','producer_seal_sha256':EXPECTED,'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}},replace=True)
 return bound(ROOT/'CONSUMER_FREEZE.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--freeze-only',action='store_true');a=p.parse_args()
 if not a.freeze_only:prepare()
 print(json.dumps(freeze()))
