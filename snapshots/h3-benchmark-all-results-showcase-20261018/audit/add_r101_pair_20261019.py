from pathlib import Path
import json,hashlib,copy,datetime,collections
R=Path(__file__).resolve().parents[1];P=R/'inventory/flexiact.json'
C=Path('/Users/researcher/DevProjects/h3-flexiact-character-guidance-metrics-r101-20261019')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,j):Path(p).write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
before=P.read_bytes();j=read(P);old=copy.deepcopy(j['items']);id='flex_r101_human2animal_1__game_man_4_fixed'
assert not any(x['id']==id for x in old)
g=read(C/'incoming/PAIR_RUNTIME_GATE.json');p=read(C/'showcase/PRESENTATION.json');c=read(C/'configs/contract.json');review=read(C/'audit/full147_review/REVIEW.json')
assert g['passed'] and all(g['checks'].values()) and review['coverage']==list(range(147))
evidence=[C/'configs/contract.json',C/'incoming/PAIR_RUNTIME_GATE.json',C/'incoming/COLLECTION.json',C/'showcase/PRESENTATION.json',C/'audit/ROOT_EVENT_PLAN.json',C/'audit/full147_review/MEDIA_BINDINGS.json',C/'audit/full147_review/REVIEW.json',C/'prepared/MF_INPUTS.json']
row={
 'id':id,'parent_record_id':'flex_r98_human2animal_1__game_man_4_task_repair','benchmark':'FlexiAct','source_id':'human2animal_1','reference_image_id':'game_man_4',
 'variant':'R98修复后普通编辑 + R101固定时序引导','title':'俯卧支撑动作 · game_man_4 · 修复身份后的引导对照',
 'task':'用目标图中的短黑发动漫男性和白色背景呈现参考视频的低伏、撑起、低头拱背动作，保持动作时刻、方向和幅度。',
 'display_task':'角色替换＋动作迁移；参考图提供人物和白色背景。','reference_image_used':True,
 'reference_image_path':c['media']['target']['file'],'reference_video_path':c['media']['source']['file'],'ordinary_video_path':c['media']['native']['file'],'guided_video_path':str(C/'incoming/forced.mp4'),'alternative_video_path':None,
 'comparison_video_path':str(C/'showcase'/p['video']['file']),
 'preview_html':c['default_output'],'review_status':'角色外观替换完成，动作迁移仍不完整',
 'review_summary':'全部147有效帧审阅：两版均实现目标男子和白背景；抬头抬胸转折仍较参考提前，末段参考直臂拱背而两版屈肘降胸。固定引导与普通编辑动作接近，尚无明确时序改善。约75–95帧头顶出画。',
 'display_summary':'角色外观替换完成，动作迁移仍不完整。两版转折提前、末段屈肘降胸的差异接近，本例无明确时序收益。',
 'count_as_complete_task_success':False,'clear_temporal_support':False,'identity_success':{'native':True,'guided':True},'motion_transfer':'partial',
 'evidence_paths':[str(x) for x in evidence],'evidence_sha256':{str(x):sha(x) for x in evidence},
 'valid_frames':147,'fps':24,'generated_frames':158,'method_label':c['method'],'comparison_kind':'guided_pair','comparison_subtype':'historical_native_same_host_matched_fixed_guidance',
 'column_labels':['1.参考视频','2.普通编辑','3.时序引导'],'guidance_activation':'active','routed_block_calls':450,
 'pair_group':'官方素材自建交叉配对；修复提示词后的同主机配对',
 'source_time_precision':'原素材49帧/8fps，每帧重复3次得到24fps；原始动作时间精度0.125秒，展示147有效帧。',
 'prompt':c['prompt'],'input_contract_path':str(C/'configs/contract.json'),
 'input_reference_image_sha256':c['media']['target']['sha256'],'input_reference_video_sha256':c['media']['source']['sha256'],
 'scene_requirement':'目标参考图纯白背景','scene_requirement_prompt_quote':'The target image determines the character and plain white environment.',
 'source_processing':'原片8 fps；每帧重复3次至24 fps；展示147有效帧',
 'judgment_source':'完整审阅25页三栏图，覆盖全部147有效帧；预先列出低伏、抬胸、低头、末段拱背事件。',
 'quantitative_metrics':{'motion_fidelity':{'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','protocol':'FlexiAct official MF (commit de9fe1d536732c4d1a384577b5ae54f8fc1730d7)','valid_frames':147,'evaluation_frames':49,'evaluation_fps':8,'source_files':[],'source_sha256':{},'scope':'配对guided轨迹与评分正在执行。动作任务完成度和时序事件按全帧审阅单列。'}},
 'runtime':{'guided_job_wall_seconds':g['runs']['forced']['job_wall_seconds'],'guided_capture_seconds':g['runs']['forced']['capture_seconds'],'NFE':20,'same_actual_eight_conditions':True,'AV_prefix_steps_0_5_bitwise_equal':True}
}
row['media_sha256']={k:sha(v) for k,v in row.items() if k in ['reference_image_path','reference_video_path','ordinary_video_path','guided_video_path','comparison_video_path']}
assert row['media_sha256']['guided_video_path']==g['runs']['forced']['video']['sha256']
assert row['media_sha256']['comparison_video_path']==p['video']['sha256']
j['items'].append(row);j['counts']=dict(collections.Counter(x['comparison_kind'] for x in j['items']));j['distinct_motion_sources']=len({x['source_id'] for x in j['items']});j['snapshot_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert j['items'][:-1]==old
A=R/'audit/r101_pair_20261019';A.mkdir(exist_ok=True);assert not (A/'BEFORE.json').exists();(A/'BEFORE.json').write_bytes(before)
assert P.read_bytes()==before
save(P,j);save(A/'RECEIPT.json',{'id':id,'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':sha(P),'old_records_unchanged':True,'new_record_count':len(j['items']),'counts':j['counts'],'review_sha256':sha(C/'audit/full147_review/REVIEW.json')})
print((A/'RECEIPT.json').read_text())
