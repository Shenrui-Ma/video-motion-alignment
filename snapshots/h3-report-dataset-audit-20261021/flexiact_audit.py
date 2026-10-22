from pathlib import Path
from collections import Counter
import csv,json,hashlib
ROOT=Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/sources')
OUT=Path('/Users/researcher/DevProjects/h3-report-dataset-audit-20261021')
info=json.loads((ROOT/'flexiact_hf_info.json').read_text()); paths={r['rfilename'] for r in info['siblings']}
expected={p for p in paths if p.startswith('benchmark/captions/') and p.endswith('.csv')}
files=sorted(ROOT.glob('flexiact_hf__benchmark__captions__*.csv'))
assert len(files)==len(expected)==30
rows=[];actions=[];source_hashes={}
for f in sorted(ROOT.glob('flexiact_hf__benchmark__captions__*__val_image.csv')):
 _,_,_,cat,action,_=f.name.split('__')
 meta=list(csv.DictReader(f.open()))
 cf=ROOT/f.name.replace('__val_image.csv','__crop.csv'); crops=list(csv.DictReader(cf.open()))
 source=f'benchmark/reference_videos/{cat}/{action}.mp4'
 assert source in paths
 source_caption=crops[0]['caption']
 group='camera' if cat=='camera' else 'animal_to_animal' if cat=='animal' else 'human_to_animal' if action.startswith('human2animal_') else 'human_to_human_or_humanoid'
 for n,r in enumerate(meta,1):
  is_monster=action in ['chest','fitness'] and Path(r['path']).name=='game_man_5.jpeg'
  caption_mismatch=action=='crouch' and 'resistance machine' in r['caption']
  rows.append(dict(action=action,source_category=cat,group=group,source_video=source,target_image=r['path'],val_row=n,source_caption=source_caption,target_caption=r['caption'],human_or_humanoid_candidate=group=='human_to_human_or_humanoid',strict_person_candidate=group=='human_to_human_or_humanoid' and not is_monster,subject_motion_candidate=group!='camera',humanoid_monster=is_monster,caption_source_conflict=caption_mismatch,caption_note='源动作与crop caption为下蹲；目标caption误写阻力器械训练，运行前核对并记录修正' if caption_mismatch else '',asset_paths_present=source in paths and r['path'] in paths,visually_reviewed_in_this_audit=False,metadata_file=str(f)))
 actions.append(dict(action=action,group=group,source_video=source,pairs=len(meta),unique_target_images=len({r['path'] for r in meta}),crop_csv_rows=len(crops),crop_video_files=sum(p.startswith(f'benchmark/reference_videos/{cat}/{action}_crop/') and p.endswith('.mp4') for p in paths),source_caption=source_caption,caption_conflicts=sum(x['caption_source_conflict'] for x in rows if x['action']==action)))
for f in files+[ROOT/'flexiact_hf_info.json',ROOT/'flexiact_readme.txt']:
 source_hashes[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
assert len(rows)==len({(r['source_video'],r['target_image']) for r in rows})==89
assert all(r['asset_paths_present'] for r in rows)
assert sum(a['crop_csv_rows'] for a in actions)==177
summary={
 'audit_date':'2026-10-21','classification_basis':'完整扫描公开文件清单和所有caption CSV；依据源/目标类别及动作描述人工核对分组，未声称逐视频视觉审核。',
 'official_repository':'https://huggingface.co/datasets/shiyi0408/FlexiAct',
 'official_code':'https://github.com/TencentARC/FlexiAct',
 'official_paper':'https://arxiv.org/html/2505.03730v1#S4.SS1',
 'dataset_commit':info['sha'],'dataset_last_modified':info['lastModified'],
 'current_version_check':{'date':'2026-10-21','url':'https://huggingface.co/datasets/shiyi0408/FlexiAct/tree/main','method':'web工具读取官方仓库文件页','visible_head_commit':'69d7747','matches_local_commit':True,'page_crawl_age':'4 days','api_direct_status':'直连HF和hf-mirror的小JSON请求TLS EOF；未下载任何视频/图像'},
 'paper_reported_evaluation':{'action_categories':25,'video_image_pairs':250},
 'public_snapshot':{'source_videos':15,'caption_files':30,'source_video_target_image_pairs':89,'unique_target_images_in_pairs':42,'target_image_files_total':43,'source_crop_csv_rows':177,'augmentation_video_files':207},
 'counting_unit':'一条源视频与val_image.csv中一张目标图构成一对动作迁移任务；不将同一源视频的crop增强重复计为独立样本，不把任意重新配对当作官方任务。',
 'scope_counts':{
  'source_human_regardless_of_target':{'source_videos':8,'pairs':46},
  'human_to_person_including_animated_person_excluding_monster':{'source_videos':5,'pairs':37,'caption_conflict_pairs':5,'caption_consistent_pairs':32},
  'human_to_human_or_humanoid':{'source_videos':5,'pairs':39,'humanoid_monster_pairs':2,'caption_conflict_pairs':5,'caption_consistent_pairs':34},
  'human_to_animal':{'source_videos':3,'pairs':7},
  'animal_to_animal':{'source_videos':3,'pairs':11},
  'all_subject_motion':{'source_videos':11,'pairs':57,'caption_conflict_pairs':5,'caption_consistent_pairs':52},
  'excluded_camera_only':{'source_videos':4,'pairs':32}
 },
 'notes':[
  '人体/人形运动口径包含现实人物和人形动漫角色；game_man_5的两个任务被caption明确称作humanoid cartoon monster，严格人物口径单列排除。',
  'human2animal_*源视频是人体动作，但官方val_image目标为动物；共3条源视频7对，只计扩展主体口径。',
  'human2animal_*与game_man_4等人物图的既往实验属于自行重新配对，不能增加官方39对或89对。',
  '公开集合中的广义运动主体包括人形与动物，未发现独立非生物物体运动任务。4类camera任务虽然画面中可有物体，但要求是镜头运动，单列排除。',
  'crouch的5条target caption与源视频动作定义冲突；该源动作下蹲本身符合研究任务，运行时需要核对提示词，不能照误写caption直接跑。',
  'rotate有28个crop视频但只有9条crop CSV；human2animal_2有23个crop视频但只有12条crop CSV。这些是源视频增强，均不扩充源视频或任务对数。',
  '当前公开15条/89对与论文25类/250对属于不同可获取范围；本次统计覆盖当前公开仓库的全部caption。'
 ],'actions':actions,'source_sha256':source_hashes}
(OUT/'flexiact_suitability_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
with (OUT/'flexiact_suitability_pairs.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (OUT/'flexiact_suitability_actions.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(actions[0]));w.writeheader();w.writerows(actions)
text='''推荐报告写法：

FlexiAct 将参考视频动作迁移到目标图像主体。我们扫描了公开仓库全部30个caption文件，共15条独立参考视频、89个视频—图像任务对。按人体与人形角色计，有5条参考视频、39对任务；扩展到动物及跨物种迁移后，有11条参考视频、57对任务。另4条参考视频、32对任务只要求镜头运动，单列排除。同一视频的裁剪增强不重复计数。

表下注：人体39对含2个人形怪物任务；若严格只计现实及动漫人物则为37对。5条下蹲任务的目标caption误写成器械训练，提示词核对后再运行。以上是公开数据的任务适用性统计，实际编辑完成情况在生成后另行记录。论文报告25类/250对，本次按公开可获取15条/89对统计。

最简统计表：
- 人体/人形：5条参考视频，39对任务（严格人物37对）。
- 有运动主体：11条参考视频，57对任务。
- 纯镜头运动：4条参考视频，32对任务，排除。

官方版本核对：2026-10-21读取HF主分支文件页，显示69d7747，与本地完整metadata快照69d7747f93e1b913a3dca306bf8e91ee74fea7d4一致。
'''
(OUT/'flexiact_recommended_text.txt').write_text(text)
print(json.dumps(summary['scope_counts'],ensure_ascii=False,indent=2));print('WROTE',OUT)
