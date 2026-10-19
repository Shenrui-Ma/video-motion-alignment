from pathlib import Path
import json,hashlib,datetime,collections
R=Path('/Users/researcher/DevProjects/h3-flexiact-character-repair-metrics-r98-20261019');A=R/'audit/agent_task_repair_review';S=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018');I=S/'inventory/flexiact.json'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
c=read(R/'configs/contract.json');p=read(R/'showcase/PRESENTATION.json');rv=read(A/'REVIEW.json');old=read(I)
assert len(old['items'])==21 and not any(x['id']=='flex_r98_human2animal_1__game_man_4_task_repair' for x in old['items'])
assert rv['task_acceptance']['new_identity']=='pass' and rv['guidance_routed_calls']=={'old_native':0,'new_native':0}
(A/'flexiact.before_r98.json').write_bytes(I.read_bytes())
item={
'id':'flex_r98_human2animal_1__game_man_4_task_repair','benchmark':'FlexiAct','source_id':'human2animal_1','variant':'R98 · P1-reference-v1普通编辑修复；旧R66跨主机对照','title':'俯卧支撑动作 · game_man_4 · 角色替换修复',
'task':'将源人物换成目标图的短黑发动漫男性，在目标图纯白背景完成低伏、撑起和拱背动作，保留动作顺序、时刻、方向与幅度。',
'display_task':'角色替换＋动作迁移；目标图人物与纯白背景；低伏、撑起、拱背。',
'reference_image_used':True,'reference_image_path':c['media']['target']['file'],'reference_video_path':p['inputs'][0]['file'],'ordinary_video_path':p['inputs'][1]['file'],'guided_video_path':None,'alternative_video_path':p['inputs'][2]['file'],'comparison_video_path':str(R/'showcase'/p['video']['file']),
'review_status':'身份与背景修复，动作部分保留','review_summary':'完整147帧审阅：新版实现短黑发动漫男性脸及服装装备，纯白背景完成；旧版源人物脸/长辫和室内场景残留消失。低伏、撑起、低头拱背顺序保留，膝肘支撑与伸背幅度仍不同，部分转折提前。两版均为普通编辑，0次时序引导；旧.41与新.9软件环境不同，不能把差异全部归因于提示词。',
'display_summary':'新版目标身份与白背景已修复，动作顺序保留，姿态幅度和转折时刻仍有差异。两版均0次时序引导。',
'evidence_paths':[str(R/'configs/contract.json'),str(R/'incoming/NATIVE_RUNTIME_GATE.json'),str(R/'incoming/COLLECTION.json'),str(R/'showcase/PRESENTATION.json'),str(A/'REVIEW_PLAN.json'),str(A/'REVIEW.json'),str(A/'FRAME_LEDGER.json')],
'valid_frames':147,'fps':24,'method_label':'普通编辑修复：官方结构化提示词，两版均0次时序引导','comparison_kind':'prompt_control','comparison_subtype':'task_repair_cross_host','column_labels':['1.参考动作','2.旧普通编辑','3.新版普通编辑'],'guidance_activation':'not_applicable','pair_group':'官方素材自建交叉配对；普通编辑修复对照','source_time_precision':'原素材49帧/8fps，每帧重复3次得到24fps；原始动作时间精度0.125秒，展示147有效帧。','generated_frames':158,'reference_image_id':'game_man_4',
'prompt':c['prompt'],'input_contract_path':str(R/'configs/contract.json'),'input_reference_image_sha256':c['media']['target']['sha256'],'input_reference_video_sha256':c['media']['source']['sha256'],'scene_requirement':'目标参考图纯白背景','scene_requirement_prompt_quote':'The target image determines the character and plain white environment.','source_processing':'原片8 fps；每帧重复3次至24 fps；展示147有效帧','judgment_source':'按预先冻结的基础任务验收项核对目标图，并逐帧审阅147有效帧；输出事件区间为探索性标注。','cross_host_limit':c['cross_host_limit'],
'quantitative_metrics':{'motion_fidelity':{'native':None,'guided':None,'delta':None,'higher_is_better':True,'status':'pending','protocol':'FlexiAct official MF (commit de9fe1d536732c4d1a384577b5ae54f8fc1730d7)','source_files':[],'source_sha256':{},'valid_frames':147,'scope':'此条为旧普通/新版普通的任务修复展示；新R98实际输出尚未评分。引导成片尚未生成，guided与delta不适用，旧R66分数未移植到新输出。'}}}
fields=['reference_image_path','reference_video_path','ordinary_video_path','alternative_video_path','comparison_video_path']
item['media_sha256']={k:sha(item[k]) for k in fields}
assert item['media_sha256']['alternative_video_path']==p['inputs'][2]['sha256']
assert item['media_sha256']['comparison_video_path']==p['video']['sha256']
write(A/'INVENTORY_ITEM.json',item)
out=dict(old);out['items']=old['items']+[item];out['counts']=dict(collections.Counter(x['comparison_kind'] for x in out['items']));out['snapshot_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();out['distinct_motion_sources']=len({x['source_id'] for x in out['items']})
assert out['items'][:21]==old['items']
write(I,out)
write(A/'INVENTORY_APPEND_VALIDATION.json',{'passed':True,'old_21_entries_unchanged':True,'old_count':21,'new_count':22,'new_id':item['id'],'inventory_sha256':sha(I),'before_sha256':sha(A/'flexiact.before_r98.json'),'new_item_sha256':sha(A/'INVENTORY_ITEM.json'),'old_failed_entry_preserved':next(x for x in out['items'] if x['id']=='flex_r66_human2animal_1__game_man_4')['review_status'],'evidence_sha256':{f:sha(f) for f in item['evidence_paths']}})
print(json.dumps({'new_id':item['id'],'items':22,'counts':out['counts'],'inventory_sha256':sha(I)},ensure_ascii=False))
