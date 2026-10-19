from pathlib import Path
import copy, json, hashlib, time
R=Path(__file__).resolve().parents[1];D=R.parent
C=D/'h3-flexiact-p1-control-metrics-r90-20261019'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=R/'inventory/flexiact.json';before=sha(p);doc=read(p);old=copy.deepcopy(doc['items'])
ID='flex_r90_one_leg__movie_man_9_prompt_control';assert not any(x['id']==ID for x in old)
parent=next(x for x in old if x['id']=='flex_r72_fitness_prompt_control')
config=read(C/'configs/contract.json');pres=read(C/'showcase/PRESENTATION.json')
reviewfile=C/'audit/full147_review/REVIEW.json';review=read(reviewfile)
assert review['frames_reviewed']==list(range(147)) and pres['guidance_routed_calls']==[0,0]
assert read(C/'incoming/NATIVE_RUNTIME_GATE.json')['passed'] and read(C/'incoming/ROOT_EXIT_RECEIPT.json')['passed']
row=copy.deepcopy(parent)
summary='完整147帧审阅：P1普通编辑恢复了随参考展开和上举双臂、抬膝的动作；P0前约2.3秒几乎静止，后续手部路线也改变。P1可见上肢的阶段更接近参考，但脚部与另一膝的接触出框，完整单腿姿势无法核验。两版均0次时序引导，本条记录提示词影响。'
row.update(id=ID,source_id='one_leg',variant='R90 · R85 P0 / R90 P1提示词对照',title='单腿站立 · movie_man_9 · 提示词恢复可见上肢动作',task='用目标图深色西装男子和庭院长廊场景，复现参考视频中双臂侧向展开、举过头顶并抬腿平衡的完整动作。',reference_image_path=config['media']['target']['file'],reference_video_path=config['media']['source']['file'],ordinary_video_path=config['media']['old_native']['file'],alternative_video_path=str(C/'incoming/native.mp4'),comparison_video_path=str(C/'showcase'/pres['video']['file']),review_summary=summary,display_summary=summary,review_status='提示词改善可见动作，脚部出框',review_status_code='prompt_control_task_partial',column_labels=pres['columns'],reference_image_id='movie_man_9',prompt=config['prompt'],input_contract_path=str(C/'configs/contract.json'),input_reference_image_sha256=config['media']['target']['sha256'],input_reference_video_sha256=config['media']['source']['sha256'],scene_requirement='目标参考图庭院长廊场景',scene_requirement_prompt_quote="The subject's appearance and the scene come from <Picture 1>.",judgment_source='完整147帧已审阅；49个原始动作时刻，源时间精度0.125秒。',cross_host_limit=config['cross_host_limit'],count_as_complete_task_success=False,support_for_clear_whole_event_repair=False,preview_html=config['default_output'],event_review={'file':str(reviewfile),'sha256':sha(reviewfile)},parent_inventory_id='flex_r85_one_leg__movie_man_9_fixed')
evidence=[C/'configs/contract.json',C/'incoming/NATIVE_RUNTIME_GATE.json',C/'incoming/COLLECTION.json',C/'incoming/ROOT_EXIT_RECEIPT.json',C/'showcase/PRESENTATION.json',reviewfile,C/'audit/full147_review/MEDIA_BINDINGS.json']
row['evidence_paths']=[str(x) for x in evidence];row['evidence_sha256']={str(x):sha(x) for x in evidence}
row['media_sha256']={k:sha(row[k]) for k in ['reference_image_path','reference_video_path','ordinary_video_path','alternative_video_path','comparison_video_path']}
row['quantitative_metrics']['motion_fidelity']['status']='pending_prompt_control'
row['quantitative_metrics']['motion_fidelity']['scope']='R85 P0与R90 P1普通编辑的提示词对照；官方FlexiAct MF待评分，guidance不适用。'
doc['items'].append(row);assert doc['items'][:-1]==old
doc['counts']={k:sum(x['comparison_kind']==k for x in doc['items']) for k in ['guided_pair','native_only','prompt_control']}
doc['previous_inventory_sha256']=before;doc['updated_unix']=time.time();assert sha(p)==before
a=R/'audit/r90_prompt_20261019';a.mkdir(exist_ok=False);(a/'PREVIOUS_INVENTORY.json').write_bytes(p.read_bytes())
p.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
receipt={'before_sha256':before,'after_sha256':sha(p),'added':ID,'other_rows_unchanged':True,'counts':doc['counts']}
(a/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
