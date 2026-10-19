from pathlib import Path
import json,hashlib,datetime,collections
B=Path('/Users/researcher/DevProjects'); O=B/'h3-benchmark-all-results-showcase-20261018'; A=O/'audit/flexiact_inventory'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verified(p,expected=None):
 p=Path(p);assert p.is_file(),p
 if expected:assert sha(p)==expected,(p,expected,sha(p))
 return str(p)
def evidence(paths):return [verified(x) for x in paths]
items=[]
fixed='固定时序引导：采样第6–14步（从0计数），mass-preserving same-bin routing，alpha=1，50层'
actions={'chest':'扩胸','crouch':'下蹲','fitness':'举臂健身','one_leg':'单腿举臂','rotate':'转身','human2animal_1':'俯卧支撑动作','human2animal_2':'坐姿前屈','human2animal_3':'倒立转换'}
motion_tasks={'chest':'扩胸器练习中的双臂收放','crouch':'两次下蹲和起立、胸前手势','fitness':'双臂展开、上举和下放','one_leg':'单腿抬膝与双臂上举','rotate':'转身与回转','human2animal_1':'低伏、撑起和拱背','human2animal_2':'坐姿前屈','human2animal_3':'由低支撑向倒立转换'}
def row(id,source,variant,target,ref,native,guided,comparison,review,status,ev,kind='guided_pair',method=fixed,activation='active',group='官方CSV配对',alternative=None,labels=None):
 return {'id':id,'benchmark':'FlexiAct','source_id':source,'variant':variant,'title':actions.get(source,source)+' · '+target,'task':'将目标参考图人物的外观用于动作迁移，复现参考视频的动作顺序与时刻；场景按该次实际提示词指定。','reference_image_used':True,'reference_image_path':None,'reference_video_path':verified(ref),'ordinary_video_path':verified(native),'guided_video_path':verified(guided) if guided else None,'alternative_video_path':verified(alternative) if alternative else None,'comparison_video_path':verified(comparison) if comparison else None,'review_summary':review,'review_status':status,'evidence_paths':evidence(ev),'valid_frames':147,'fps':24,'method_label':method,'comparison_kind':kind,'column_labels':labels or (['参考视频','普通编辑','时序引导'] if kind=='guided_pair' else ['参考视频','普通编辑']),'guidance_activation':activation,'pair_group':group,'source_time_precision':'原素材49帧/8fps，每帧重复3次得到24fps；原始动作时间精度为0.125秒，展示只取147有效帧。','generated_frames':158}
def bind_input(x,case,root,contract):
 x['reference_image_path']=verified(root/'inputs'/case['portrait'],case['portrait_sha256'])
 assert sha(x['reference_video_path'])==case['video_sha256']
 x['reference_image_id']=Path(case.get('identity',case['portrait'])).stem
 x['prompt']=case.get('prompt','')
 x['input_contract_path']=verified(contract);x['evidence_paths'].append(str(contract))
 x['input_reference_image_sha256']=case['portrait_sha256'];x['input_reference_video_sha256']=case['video_sha256']
 return x
# Earlier five: actual original Native + only one completed zero-activation Auto.
r49=B/'h3-timing-flexiact-native-r49-20261017';ct49=r49/'configs/scientific_contract.json';c49={x['source_id']:x for x in read(ct49)['cases']}
mf=B/'h3-flexiact-five-full-showcase-20261018/MEDIA_MANIFEST.json';m=read(mf)
notes={'chest':('早期固定六帧审阅：目标图为铠甲女性，成片仍保留原男性和蓝色背心，身份替换失败。自动版20次观测均未触发，成片与本轮普通编辑逐帧相同。','任务失败'),'crouch':('早期固定六帧审阅：普通编辑的下蹲、手臂和构图发生明显变化，不能归纳成纯时延。自动运行未生成完整成片。','任务失败'),'fitness':('早期固定六帧审阅：目标铠甲女性及暗背景出现，举臂和合掌的大阶段保留，前段抬臂较慢；此条只有普通编辑。','待成对结果'),'one_leg':('早期固定六帧审阅：目标西装人物及汽车场景出现，前段手臂较低，脚和下腿多在画外；此条只有普通编辑。','待成对结果'),'rotate':('早期固定六帧审阅：铠甲女性外观与全身构图大体保留，转身随源动作变化，未建立明显持续时差；此条只有普通编辑。','待成对结果')}
for c in m['cases']:
 s=c['source_id'];inputs=c['source_and_completed_outputs'];[verified(x['file'],x['sha256']) for x in inputs];out=c['output'];verified(out['file'],out['sha256']);auto=len(inputs)==3;rv=r49/f'audit/root_visual_{s}/REVIEW.json'
 x=row('flex_r50_chest_auto' if auto else f'flex_r49_{s}_native',s,'R49原提示 + R50自动策略' if auto else 'R49原提示',Path(c49[s]['identity']).stem,inputs[0]['file'],inputs[1]['file'],inputs[2]['file'] if auto else None,out['file'] if auto else None,*notes[s],[mf,rv]+[v['file'] for v in c['completion_evidence']],kind='guided_pair' if auto else 'native_only',method='自动策略（实际0次干预；与本轮R49普通编辑逐帧相同）' if auto else '普通编辑；自动版尚无完整成片',activation='zero' if auto else 'unknown',labels=c['columns'])
 if not auto:x['native_comparison_video_path']=out['file']
 items.append(bind_input(x,c49[s],r49,ct49))
# Two fixed intervention pairs.
r65=B/'h3-flexiact-forced-metrics-r65-20261018';ct65=r65/'configs/producer_scientific_contract.json';cs65={x['source_id']:x for x in read(ct65)['cases'] if x['arm']=='native'};con65=r65/'audit/consumer_execution_20261018/CASE_CONCLUSIONS.json'
for s,c in cs65.items():
 gate=r65/f'incoming/{s}/PAIR_RUNTIME_GATE.json';assert read(gate)['passed'];pm=r65/f'showcase/{s}_PRESENTATION.json';pr=read(pm);v=pr['videos'][-1]['video'];verified(v['file'],v['sha256'])
 x=row(f'flex_r65_{s}_fixed',s,'R65 · R49原提示',Path(c['identity']).stem,r65/'inputs'/c['video'],r65/f'incoming/{s}/native.mp4',r65/f'incoming/{s}/forced.mp4',v['file'],'已有成对结论：'+read(con65)[s]['text']+' 姿态相关性估计只描述可见手臂，不等同事件精确起点。','无明显改善',[pm,gate,con65,r65/f'scores/physical/{s}.json'])
 items.append(bind_input(x,c,r65,ct65))
# Eight pairs, including six new cross-pair extensions, with all outcomes.
r66=B/'h3-flexiact-expanded-evaluation-r66-20261018';prod66=B/'h3-timing-flexiact-expanded-r66-20261018';ct66=r66/'configs/producer_scientific_contract.json';cs66={x['source_id']:x for x in read(ct66)['cases'] if x['arm']=='native'};final66=r66/'reports/FINAL_EIGHT_PAIR_EVIDENCE.json';rv66=r66/'audit/root_visual_review_20261018/OBSERVATIONS.json';note66=r66/'reports/visual_notes/human2animal_1__movie_man_11.json'
n66={'human2animal_1__movie_man_11':('固定六时刻审阅：普通编辑和引导版在2.5秒已撑起、5.75秒低伏，与参考阶段相反；两版保留原人物长辫，未见改善。','任务失败'), 'human2animal_1__game_man_4':('角色替换失败：普通编辑保留源人物的脸和长辫；引导版中段出现较接近目标的动漫脸与短刘海，但后侧长辫持续残留，身份混合。两版主要借用了绿披肩和棕袖服装，仍保留原墙面与地板，目标图白背景未实现。动作大阶段接近，未见清楚时序修复。','任务失败'),'human2animal_3__movie_man_11':('固定源动作时刻审阅：两版均向倒立转换，前段肘部/身体姿态和构图有变化；普通与引导很接近，未见清楚时序修复。','无明显改善'),'human2animal_3__game_man_4':('固定源动作时刻审阅：参考由低支撑转倒立，两版却先倒立再回低支撑；目标人物替换也不明显。动作次序和内容均改变。','任务失败'),'human2animal_2__movie_man_11':('固定源动作时刻审阅：参考盘腿坐姿前屈，两版从俯卧支撑转跪姿，原动作序列未保留；两版彼此很接近。','任务失败'),'human2animal_2__game_man_4':('固定源动作时刻审阅：两版仍像原人物，目标动漫外观未完成；两版前屈均延后，局部手势变化不足以构成任务成功的时序修复。','任务失败')}
recent66=r66/'audit/two_pending_pair_visual_review_20261018'
reviewed66={
 'fitness__game_man_4':'完整49个原动作时刻及关键过渡区共91个输出帧已审阅：目标动漫人物外观出现，双臂展开、上举、接近合掌和下放序列保留，普通编辑已与源大致同相，固定引导无清楚时序收益。目标图白背景变为山地背景；部分高举手部在画外。',
 'one_leg__movie_man_11':'完整49个原动作时刻及关键过渡区共96个输出帧已审阅：目标金发西装人物和树木路灯背景保留，展开双臂、抬膝、上举的大阶段保留。普通与引导相近，未见清楚时序收益；脚部与高举手部部分裁切，末段手臂间距仍与源不同。'
}
for e in read(final66)['pairs']:
 key=e['pair'];c=cs66[key];s=c['motion_source_id'];gate=Path(e['gate']['file']);assert read(gate)['passed'];verified(gate,e['gate']['sha256']);pm=r66/f'showcase/{key}_PRESENTATION.json';v=e['video'];verified(v['file'],v['sha256']);ev=[pm,gate,final66,Path(e['physical_report']['file']),Path(e['guidance_summary']['file'])]
 if key in reviewed66:review,status=reviewed66[key],'无明显改善';ev.extend([recent66/key/'REVIEW.json',recent66/key/'LEDGER.json',recent66/'REPORT.txt'])
 elif key in n66:review,status=n66[key];ev.append(note66 if key=='human2animal_1__movie_man_11' else rv66)
 else:review=f"成对文件和指标已完成；官方MF {e['MF']['native']:.4f}→{e['MF']['forced']:.4f}。本清单尚未取得对应逐帧任务/时序审阅记录，指标变化不单独认定动作改善。";status='待人工复核'
 if key=='human2animal_1__game_man_4':ev.extend([A/'r66_human1_game4_task_recheck/REVIEW.json',A/'r66_human1_game4_task_recheck/FRAME_LEDGER.json'])
 x=row('flex_r66_'+key,s,'R66 · R49原提示',Path(c['identity']).stem,r66/'runtime/source_videos'/c['video'],r66/f'incoming/{key}/native.mp4',r66/f'incoming/{key}/forced.mp4',v['file'],review,status,ev,group='官方素材新交叉配对' if 'crosspair' in c['group'] else '官方CSV配对')
 items.append(bind_input(x,c,prod66,ct66))
# Prompt control: two Native runs, never label P1 as temporal guidance.
r72=B/'h3-timing-flexiact-prompt-pair-r72-20261018';ct72=r72/'configs/scientific_contract.json';cs72=read(ct72)['cases'];pm72=r72/'showcase/fitness__game_man_5/PRESENTATION.json';p=read(pm72);[verified(x['file'],x['sha256']) for x in p['inputs']];verified(p['video']['file'],p['video']['sha256']);assert read(p['gate']['file'])['passed'];c=next(x for x in cs72 if x['source_id']=='fitness__game_man_5' and x['arm']=='p0')
x=row('flex_r72_fitness_prompt_control','fitness','R72 · P0/P1提示诊断','game_man_5',p['inputs'][0]['file'],p['inputs'][1]['file'],None,p['video']['file'],'完整147帧审阅：P0/P1均完成金属机器人外观及黑背景，双臂展开、上举、合掌下放的大阶段保留。P1局部抬臂稍高，整体时序与P0接近；两版前段手臂仍较参考低，未见明确的提示词时序修复。高举时手部部分出画，接触时刻不作精确断言。两版均为普通编辑，时序干预次数为0。','无明显改善',[pm72,p['gate']['file'],A/'r72_fitness_promptcontrol_review/REVIEW.json',A/'r72_fitness_promptcontrol_review/FRAME_LEDGER.json'],kind='prompt_control',method='提示词适配对照：P0普通编辑 / P1普通编辑',activation='zero',alternative=p['inputs'][2]['file'],labels=p['labels']);items.append(bind_input(x,c,r72,ct72))
# Two explicitly archived unpaired successful single videos.
u=Path('/Users/researcher/Downloads/H3_Benchmark_完整对比归档_20261018/未成对结果/UNPAIRED_MANIFEST.json')
for e in read(u)['runs']:
 is72=e['batch']=='R72';root=r72 if is72 else B/'h3-timing-flexiact-official-six-r74-20261018';ct=root/'configs/scientific_contract.json';key='one_leg__movie_man_9' if is72 else 'chest__game_man_5';c=next(x for x in read(ct)['cases'] if x['source_id']==key and x['arm']==('p0' if is72 else 'native'));v=e['video'];verified(v['file'],v['sha256'])
 x=row('flex_'+e['batch'].lower()+'_'+key+'_native',key.split('__')[0],e['batch']+(' · P0' if is72 else ' · P1'),key.split('__')[1],root/'inputs'/c['video'],v['file'],None,None,'归档确认普通编辑成功写出；对应'+('P1提示对照' if is72 else '固定引导')+'成片尚未完成。本条不形成成对效果结论。','待成对结果',[u,e['unpaired_record']['file']],kind='native_only',method='普通编辑：'+('P0' if is72 else 'P1'),activation='zero');items.append(bind_input(x,c,root,ct))
# New R85: two actual completed pairs; retain the earlier crouch Native evidence.
r85=B/'h3-flexiact-expanded-metrics-r85-20261018';ct85=r85/'configs/producer_scientific_contract.json';cs85={x['source_id']:x for x in read(ct85)['cases'] if x['arm']=='native'};key='one_leg__movie_man_9';c=cs85[key];pm=r85/f'showcase/{key}/PRESENTATION.json';p=read(pm);gate=Path(p['gate']['file']);assert read(gate)['passed'];rv=r85/'audit/agent_first_pair_review/REVIEW.json';h=r85/f'results/{key}/HUMAN_REVIEW.json'
x=row('flex_r85_'+key+'_fixed','one_leg','R85 · P0新同机配对','movie_man_9',r85/'inputs'/c['video'],r85/f'incoming/{key}/native.mp4',r85/f'incoming/{key}/forced.mp4',r85/f'showcase/{key}/full_valid.mp4','完整147帧审阅：目标西装人物及场景保留；普通编辑和引导版均明显晚举臂，并插入源片没有的胸前合掌路径。固定引导未修复，早期构图拉远和下肢裁切单列。','无明显改善',[pm,gate,rv,h]);items.append(bind_input(x,c,r85,ct85))
key='crouch__movie_man_5';c=cs85[key];a=r85/'audit/crouch_native_preliminary';paired_review=r85/'audit/visual_review_crouch_movie5';pm=r85/f'showcase/{key}/PRESENTATION.json';p=read(pm);gate=Path(p['gate']['file']);assert read(gate)['passed'];verified(gate,p['gate']['sha256']);assert sha(a/'native.mp4')==sha(r85/f'incoming/{key}/native.mp4')
x=row('flex_r85_'+key+'_fixed','crouch','R85 · P1新同机配对','movie_man_5',r85/'inputs'/c['video'],r85/f'incoming/{key}/native.mp4',r85/f'incoming/{key}/forced.mp4',r85/f'showcase/{key}/full_valid.mp4','完整147帧审阅：两次下蹲与起立原本已大致同相，固定引导无清楚时序收益。普通编辑保留扎发，引导版短发更接近目标图，外观变化单列。两版均保留湖面栈桥，提示要求的目标图白背景未实现，场景任务部分失败。','无明显改善',[pm,gate,paired_review/'REVIEW.json',paired_review/'FRAME_LEDGER.json',r85/f'results/{key}/HUMAN_REVIEW.json',a/'NATIVE_ONLY_RECEIPT.json',a/'REVIEW.json',a/'FRAME_LEDGER.json']);items.append(bind_input(x,c,r85,ct85))
# R85 third completed pair: actual new P1 Native and fixed guidance.
key='rotate__game_girl_1';c=cs85[key];paired_review=r85/'audit/visual_review_rotate_gamegirl1';pm=r85/f'showcase/{key}/PRESENTATION.json';p=read(pm);gate=Path(p['gate']['file']);assert read(gate)['passed'];verified(gate,p['gate']['sha256'])
x=row('flex_r85_'+key+'_fixed','rotate','R85 · P1新同机配对','game_girl_1',r85/'inputs'/c['video'],r85/f'incoming/{key}/native.mp4',r85/f'incoming/{key}/forced.mp4',r85/f'showcase/{key}/full_valid.mp4','完整147帧审阅：两版均换成短棕发黑银铠甲女性，胸前合手、双脚固定、躯干往返转动保留。普通编辑已基本同相，固定引导未显示清楚时序收益。头部朝向和转幅有共有细差；深灰背景与目标图深青背景仅部分匹配，未见引导新增明显重影。','无明显改善',[pm,gate,paired_review/'REVIEW.json',paired_review/'FRAME_LEDGER.json',r85/f'results/{key}/HUMAN_REVIEW.json']);items.append(bind_input(x,c,r85,ct85))
display_acceptance_revision={'flex_r85_crouch__movie_man_5_fixed': {'review_status': '部分任务失败；时序接近', 'display_summary': '普通版身份替换不完整，引导版短发更贴目标；两版目标图白背景均未实现。下蹲起立已接近参考时序。', 'review_summary': '完整147帧审阅：普通版保留源人物扎发，身份替换仅部分完成；固定引导版短发更接近目标，细小侧脸不足以确认精细身份。两版仍在湖面栈桥，目标图白背景要求失败。两次下蹲起立和胸前手势保留，原本已大致同相，未见清楚的时序收益。'}, 'flex_r66_fitness__game_man_4': {'review_status': '身份完成，场景失败', 'display_summary': '目标短黑发动漫男性及服装已替换，白背景变成山地；动作时序原本接近，固定引导无清楚收益。', 'review_summary': '完整49个原动作时刻和关键过渡共91帧已审阅，并补查同一目标图：短黑发、动漫男性面孔、绿披肩和棕白服装出现，源人物长发和面部未保留，主要身份外观替换完成。目标图白背景却变为山地，场景要求失败。展开、上举、接近合掌和下放序列保留，普通版已大致同相，引导无清楚时序收益；高举手部部分出画。'}, 'flex_r85_one_leg__movie_man_9_fixed': {'review_status': '动作内容与时序保持失败', 'display_summary': '目标西装人物和场景完成；两版新增胸前合掌路径且显著晚举臂，固定引导未修复。', 'review_summary': '完整147帧审阅：目标人物面部、西装与图中场景保留，身份和场景迁移主要完成。两版都明显晚举臂，并插入源片没有的胸前合掌再向上举手路径，动作内容和时间保持均失败，固定引导未修复。开头构图拉远、下肢裁切影响腿部事件判断；不同举臂路径的时刻差不能当作整个动作的恒定延迟。'}, 'flex_r66_human2animal_3__movie_man_11': {'review_status': '身份与场景待核验', 'display_summary': '已有六时刻仅确认向倒立转换，前段姿态和构图有变化；目标身份与场景尚缺明确验收，未见清楚时序收益。', 'review_summary': '既有固定六时刻审阅确认两版均由低支撑向倒立发展，前段肘部、身体姿态和构图与参考不同；普通版与引导版接近，未见清楚时序修复。现有记录未分别验收目标人物身份和目标图场景，这两项保留未知，不计为完整任务成功。'}}
for item in items:
 if item["id"] in display_acceptance_revision:item.update(display_acceptance_revision[item["id"]])
# Validate actual file availability, bind SHA, and forbid duplicate output sets.
seen={};ledger=[]
for x in items:
 scene_quote=next((q for q in ["Preserve the subject's appearance and the scene shown in the reference image.","The subject's appearance and the scene come from <Picture 1>."] if q in x['prompt']),None)
 assert scene_quote is not None,('unverified scene requirement',x['id'])
 x['task']='用目标图人物完成参考视频中的'+motion_tasks[x['source_id']]+'，保持原动作顺序、时刻、方向和幅度；场景来自目标参考图。'
 x['scene_requirement']='目标参考图场景'
 x['scene_requirement_prompt_quote']=scene_quote
 fields=['reference_image_path','reference_video_path','ordinary_video_path','guided_video_path','alternative_video_path','comparison_video_path','native_comparison_video_path']
 x['media_sha256']={k:sha(verified(x[k])) for k in fields if x.get(k)}
 sig=(x['media_sha256']['ordinary_video_path'],x['media_sha256'].get('guided_video_path'),x['media_sha256'].get('alternative_video_path'))
 assert sig not in seen,(x['id'],seen.get(sig));seen[sig]=x['id']
 if x['comparison_kind']=='guided_pair':assert x['guided_video_path'] and x['comparison_video_path']
 if x['comparison_kind']=='prompt_control':assert x['guided_video_path'] is None and x['alternative_video_path']
 if x['comparison_kind']=='native_only':assert x['guided_video_path'] is None and x['comparison_video_path'] is None
 x['source_processing']='原片8 fps；每帧重复3次至24 fps；展示147有效帧'
 if x['comparison_kind']!='guided_pair':x['guidance_activation']='not_applicable'
 x['judgment_source']='引用已有审阅记录与实际媒体/成对校验；本轮清单盘点未新增效果判断。'
 if x['id']=='flex_r66_human2animal_1__game_man_4':x['judgment_source']='重新查看实际目标图与49个原动作时刻的三栏画面，依据身份、发型、服装、场景分别纠正任务完成判断；旧记录已保存。'
 ledger.append({'id':x['id'],'media_sha256':x['media_sha256'],'evidence_sha256':{p:sha(p) for p in x['evidence_paths']}})
from import_motion_fidelity import enrich
mf_ledger=enrich(items)
(A/'mf_import_20261019/METRIC_BINDING_VALIDATION.json').write_text(json.dumps({'passed':True,'items':mf_ledger},ensure_ascii=False,indent=2)+'\n')
counts=dict(collections.Counter(x['comparison_kind'] for x in items));out={'schema':'benchmark-all-results-inventory-v1','benchmark':'FlexiAct','snapshot_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'counts':counts,'distinct_motion_sources':len(set(x['source_id'] for x in items)),'scope':'实际本地已归档输出；不同提示/方法/目标图单列，同一输出跨页面副本合并。重复动作源不是独立动作样本；失败和中性结果均保留。','items':items}
(O/'inventory/flexiact.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(A/'PATH_AND_SHA_VALIDATION.json').write_text(json.dumps({'passed':True,'items':len(items),'counts':counts,'ledger':ledger},ensure_ascii=False,indent=2)+'\n')
(A/'SCOPE_NOTES.txt').write_text('R67/R70 是 VAE/离线重采样算子诊断，不是新 H3 编辑与干预成对输出，未计入此主清单。R59/60/61/62 无新增在线完整成片；R60/61/62 是冻结轨迹的 CPU replay。R50失败/未执行项无完整自动成片，不伪造第三列。R84未发现本地已完成的新配对成片；R90、R94尚无消费完成媒体。R85 crouch已完成实际Native/固定引导配对，完整147帧已审阅；之前Native单条条目被此配对覆盖，原审阅证据保留。R66 fitness/game_man_4和one_leg/movie_man_11补入已完成的全段及关键过渡审阅，均无清楚时序收益。R49源动作与R65/R66/R72/R85的重复源保留同source_id；R66六条使用官方素材自建目标交叉配对，不能混入官方CSV总分。\n')
print(json.dumps({'items':len(items),'counts':counts,'sources':out['distinct_motion_sources'],'file':str(O/'inventory/flexiact.json'),'sha256':sha(O/'inventory/flexiact.json')},ensure_ascii=False))
