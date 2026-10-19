"""Prepare a three-case CPU consumer from the verified R103 consumer."""
from pathlib import Path
import hashlib,json,shutil

D=Path('/Users/researcher/DevProjects')
R=Path(__file__).resolve().parents[1]
P=D/'h3-flexiact-p1-repair-metrics-r103-20261019'
B=D/'h3-timing-flexiact-remaining-repair-r104-20261019'
KEYS=('fitness__game_man_4','human2animal_1__movie_man_11','crouch__movie_man_5')
TASKS=[
 '将绿披肩动漫男子参考图中的角色迁移到双臂侧举、过头合手、合手下落的动作，采用目标图白背景。',
 '将深蓝西装年长男子参考图中的角色迁移到低位屈肘、伸肘抬胸、低头拱背的支撑动作，采用目标图室外场景。',
 '将炭灰西装男子参考图中的角色迁移到两轮下蹲与起立动作，采用目标图白背景。',
]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
assert not (R/'CONSUMER_FREEZE.json').exists()
for folder in ['scripts','tests','configs','inputs','incoming','incoming_pairs','showcase','showcase_pairs','prepared']:(R/folder).mkdir(exist_ok=True)
for folder in ['scripts','tests']:
 for src in (P/folder).glob('*.py'):
  t=src.read_text()
  for old,new in [('R103','R104'),('r103','r104'),('human2animal_2__game_man_4',KEYS[0]),('chest__game_girl_1',KEYS[1]),('H3_SERVER_B','H3_SERVER_A'),('1004','1016'),('8567','8568'),('/data4/researcher/h3_runs/timing_flexiact_p1_repair_r104_20261019','/data5/researcher/h3_runs/timing_flexiact_remaining_repair_r104_20261019'),('unexpected .41 runtime','unexpected .9 runtime')]:t=t.replace(old,new)
  t=t.replace('SOURCES='+repr(KEYS[:2]).replace(', ',','),'SOURCES='+repr(KEYS))
  t=t.replace('self.assertEqual(len(c.SOURCES),2)','self.assertEqual(len(c.SOURCES),3)').replace('test_fixed_two_denominator','test_fixed_three_denominator')
  t=t.replace("'fixed_source_denominator':2","'fixed_source_denominator':3").replace('固定2个动作来源','固定3个动作来源').replace('2个原动作；分别为公开配对和原素材交叉配对','3个原动作；公开配对与原素材交叉配对逐项注明')
  t=t.replace('Human2animal is an official-assets crosspair; chest is an official CSV pair.','Official pairing or crosspair is retained in the per-case task group.')
  (R/folder/src.name).write_text(t)
s=read(B/'configs/scientific_contract.json');runtime=read(B/'configs/runtime.json')
assert tuple(s['source_ids'])==KEYS
c={'schema':'r104-native-and-paired-media-consumer-v1','producer_local':str(B),'producer_remote':runtime['remote_root'],'producer_seal_sha256':sha(B/'deploy_manifest.json'),'producer_contract_sha256':sha(B/'configs/scientific_contract.json'),'producer_runtime_sha256':sha(B/'configs/runtime.json'),'host':runtime['host'],'source_order':list(KEYS),'sources':[],'scope':'CPU one-shot intake after actual Native or paired gate; three retained original failed tasks.','method':'固定时序引导：去噪步骤索引6–14，α=1，全部有效参考时间位置。'}
for i,key in enumerate(KEYS):
 a=next(x for x in s['cases'] if x['source_id']==key and x['arm']=='native');b=next(x for x in s['cases'] if x['source_id']==key and x['arm']=='forced')
 row={'source_id':key,'run_id':a['run_id'],'forced_run_id':b['run_id'],'graph_sha256':sha(B/'configs/graphs'/(a['run_id']+'.json')),'forced_graph_sha256':sha(B/'configs/graphs'/(b['run_id']+'.json')),'geometry':a['geometry'],'valid_frames':a['valid_frame_count'],'crop_xywh':a['evaluation_crop_xywh'],'evaluation_indices':a['evaluation_indices'],'evaluation_fps':8,'prompt_version':a['prompt_version'],'prompt':a['prompt'],'display_task':TASKS[i],'original_task':{'pair_id':a['original_pair_id'],'group':a['group'],'motion_source_id':a['motion_source_id'],'target_identity':a['identity'],'edit_prompt':TASKS[i],'prompt_scope':'Explicit six-section prompt for unchanged official assets; pairing scope retained per case.'},'reference_image_expected':a['reference_image_expected']}
 for k,n in [('source',a['video']),('provenance',a['provenance']),('portrait',a['portrait'])]:
  shutil.copy2(B/'inputs'/n,R/'inputs'/n);row[k]={'file':'inputs/'+n,'sha256':sha(R/'inputs'/n),'bytes':(R/'inputs'/n).stat().st_size}
 c['sources'].append(row)
put(R/'configs/contract.json',c)
for dst,src in [('producer_runtime.json','configs/runtime.json'),('producer_scientific_contract.json','configs/scientific_contract.json'),('producer_seal.json','deploy_manifest.json')]:shutil.copy2(B/src,R/'configs'/dst)
f=R/'tests/test_flex_scope.py';t=f.read_text()
t=t.replace("self.assertEqual(c.info('fitness__game_man_4')['original_task']['group'],'official_assets_crosspair_extension')", "self.assertEqual(c.info('fitness__game_man_4')['original_task']['group'],'original_official_pair')\n  self.assertEqual(c.info('human2animal_1__movie_man_11')['original_task']['group'],'official_assets_crosspair')\n  self.assertEqual(c.info('crouch__movie_man_5')['original_task']['group'],'original_official_pair')")
expected=c['sources'][1]['reference_image_expected']['expected_DiT_visual_patch_tokens']
t=t.replace("self.assertEqual(c.info('human2animal_1__movie_man_11')['reference_image_expected']['expected_DiT_visual_patch_tokens'],135)", f"self.assertEqual(c.info('human2animal_1__movie_man_11')['reference_image_expected']['expected_DiT_visual_patch_tokens'],{expected})")
f.write_text(t)
put(R/'audit/PREPARATION_ORIGIN.json',{'parent_consumer':str(P),'parent_consumer_freeze_sha256':sha(P/'CONSUMER_FREEZE.json'),'producer':str(B),'producer_seal_sha256':sha(B/'deploy_manifest.json'),'GPU_started':False,'watcher_started':False})
print(json.dumps({'prepared':str(R),'cases':list(KEYS),'producer_seal':c['producer_seal_sha256']}))
