"""Bound existing-source review to official rows and existing outputs. No task edits."""
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
DEV = Path('/Users/researcher/DevProjects')
SEL = DEV / 'h3-flexiact-expanded-selection-20261018'
R74 = DEV / 'h3-timing-flexiact-official-six-r74-20261018'
R49 = DEV / 'h3-timing-flexiact-native-r49-20261017'
R66 = DEV / 'h3-flexiact-expanded-evaluation-r66-20261018'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
defs = {r['pair_key']: r for r in json.loads((R74/'design/PAIR_DEFINITIONS.json').read_text())['pairs']}
specs = [
    ('rotate', 'game_girl_1.webp', 'existing_task_viable',
     'R49六时刻可见盔甲人物与左右转体动作；这是已完成换人的优先对照，精确时序仍需独立判读。',
     '目标图仅头肩上身，面部/肩臂清楚；下身由模型补出。现有成片已显示完整下肢，不能将目标图记作全身。'),
    ('crouch', 'movie_man_5.jpg', 'P1_task_feasibility_pending',
     '本配对尚无已归档Native。旧R49 crouch→movie_man_4前半站立/举臂，后半才蹲下且末帧回到源人物场景；新目标先检验完整两次蹲起和身份稳定。',
     '单人全身西装，头、双臂、双腿与脚完整；双手贴近裤袋，需生成运动后的清晰手臂。'),
    ('crouch', 'movie_man_9.webp', 'P1_task_feasibility_pending',
     '本配对尚无已归档Native；官方caption正确写squats，沿已准备P1即可，不能预言会修正旧配对失败。',
     '单人全身深色西装，头至双脚可见；深色裤装限制自动关节定位，人工可核膝髋下降与回升。'),
    ('rotate', 'game_man_4.jpg', 'P1_task_feasibility_pending',
     '本配对尚无已归档Native；同动作R49盔甲目标已成功，支持优先测试此完整人类比例目标。',
     '单个完整动漫人体，头、臂、腿、脚均见；斗篷和腰部装备可遮挡肘/躯干，需要保留UNKNOWN。'),
    ('chest', 'movie_man_7.jpg', 'P1_task_feasibility_pending',
     '本配对尚无已归档Native；R49盔甲女和R74红金盔甲目标均未换人。真实人体目标作为较简单外观迁移的任务诊断，成功尚待验证。',
     '头、双臂、手及上半身到大腿清楚，下腿缺失；源任务也主要为胸肩肘拉索，不依赖目标完整双脚。'),
    ('rotate', 'game_man_1.jpg', 'reserve_P1_task_feasibility_pending',
     '本配对尚无已归档Native；完整卡通人体可检验跨风格，但短肢比例使姿态幅度与pose比较更难，排序靠后。',
     '全身卡通人物、双臂和双脚清楚；人类比例差异明显，手套和头身比增加几何适配难度。'),
]
rows=[]
for rank, (source, target, status, prior, target_note) in enumerate(specs, 1):
    csv_path=SEL/'metadata'/f'flexiact_hf__benchmark__captions__human__{source}__val_image.csv'
    entries=list(csv.DictReader(csv_path.open()))
    found=[(i,r) for i,r in enumerate(entries) if r['path']==f'benchmark/target_images/human/{target}']
    assert len(found)==1
    row_index, official=found[0]
    source_path=SEL/'official_assets/benchmark/reference_videos/human'/f'{source}.mp4'
    target_path=SEL/'official_assets/benchmark/target_images/human'/target
    key=f'{source}__{Path(target).stem}'
    existing=R49/'audit'/f'root_visual_{source}'/'native_six_fixed_frames.png'
    row=dict(priority=rank, pair_key=key, status=status, source_id=source,
             official_csv=str(csv_path), official_row_zero_based=row_index,
             official_target_caption=official['caption'], source=str(source_path),
             source_sha256=sha(source_path), target=str(target_path), target_sha256=sha(target_path),
             prior_native_evidence=prior, target_visibility=target_note,
             same_source_previous_native_six_frames=str(existing), same_source_previous_image_sha256=sha(existing))
    if key in defs:
        entry=defs[key]
        row.update(prepared_P1_prompt=str(R74/entry['prompt_file']),
                   prepared_P1_sha256=sha(R74/entry['prompt_file']),
                   metadata_mismatch=entry.get('caption_review',[]))
    else:
        old=[r for r in json.loads((R49/'configs/scientific_contract.json').read_text())['cases'] if r['source_id']==source][0]
        assert old['identity']==official['path']
        row.update(existing_native_run_id=old['run_id'], existing_native_prompt=old['prompt'])
    rows.append(row)
result=dict(schema='flexiact-existing-source-candidate-review-v1', kind='read-only recommendation; no new scientific queue',
            official_human_sources_total=8, excluded_current_sources=['fitness','one_leg'],
            recommended_priority_pairs=5, reserve_pairs=1, independent_source_sequences=3,
            task_viable_by_existing_six_frame_review=1, new_exact_P1_native_results_pending=5,
            candidates=rows,
            official_revision='69d7747f93e1b913a3dca306bf8e91ee74fea7d4',
            other_source_decisions={
                'human2animal_1':'多阶段上肢/躯干动作适合扩展；官方验证目标为动物。既有人体crosspair存在原长发残留、相位不保留，P1修正效果待验，不列官方人体CSV主组。',
                'human2animal_3':'收腿到倒立有明显阶段；官方验证目标为动物。真人crosspair基本动作推进但形状不同；动漫crosspair顺序反转且身份未落实。手头靠下边缘。单列crosspair诊断。',
                'human2animal_2':'缓慢前屈后长时间静止；已有真人crosspair换成俯撑/跪姿，动漫crosspair身份失败；优先级低。',
                'chest__game_man_5':'实际R74 P1 Native六帧仍为源男子，红金盔甲目标未完成；保留失败，停止以同提示成功为假设继续固定引导。'},
            limitation='Six candidate pairs represent three motion sources. The current review confirms only one existing pair has visible identity+action plausibility; remaining five require first Native task review. No result-based failure cherry-picking as a new held-out benchmark is claimed.')
(OUT/'CANDIDATES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pairs':len(rows),'sources':len({r['source_id'] for r in rows}),'all_assets_exist':True}))
